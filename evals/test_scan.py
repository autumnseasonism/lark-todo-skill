"""scan.py 的单元测试。

测试目标（不依赖真实 lark-cli，不连飞书）：
- 命令构造正确（参数齐全、JSON filter 可解析、时区拼接成 +HH:MM）
- 并行执行能正确聚合多个 profile × 多个数据源的结果
- 失败路径归一化为 {ok: false, error: ...} 而非抛异常
- stdout 输出是合法 JSON，结构符合 SKILL.md 里"归一化 JSON 结构"定义

用 shim 替换 `lark-cli` 可执行文件：在 PATH 最前面插一个返回预置 JSON 的假 lark-cli，
避免真的调用飞书 API。

运行：
    pytest evals/test_scan.py -v
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "scan.py"


# ─────────────────────────────────────────────
# 单元测试：纯函数逻辑（import scan 模块）
# ─────────────────────────────────────────────

@pytest.fixture
def scan_module():
    sys.path.insert(0, str(SCRIPT.parent))
    import scan
    yield scan
    sys.path.remove(str(SCRIPT.parent))


def test_tz_colon_format(scan_module):
    tz = scan_module._local_tz_colon()
    assert len(tz) == 6
    assert tz[0] in ("+", "-")
    assert tz[3] == ":"
    assert tz[1:3].isdigit() and tz[4:6].isdigit()


def test_today_str_format(scan_module):
    today = scan_module._today_str()
    assert len(today) == 10
    assert today[4] == "-" and today[7] == "-"


def test_today_start_end_same_date(scan_module):
    start = scan_module._today_start_iso()
    end = scan_module._today_end_iso()
    assert start[:10] == end[:10]
    assert "T00:00:00" in start
    assert "T23:59:59" in end


def test_build_commands_covers_all_sources(scan_module):
    cmds = scan_module.build_commands(
        profile="cli_test", open_id="ou_test", name="张三",
        scan_start="2026-04-21T00:00:00+08:00",
        scan_end="2026-04-21T23:59:59+08:00",
        today="2026-04-21",
    )
    assert set(cmds.keys()) == set(scan_module.ALL_SOURCES)


def test_build_commands_all_have_profile(scan_module):
    cmds = scan_module.build_commands(
        "cli_x", "ou_x", "Name",
        "2026-04-21T00:00:00+08:00", "2026-04-21T23:59:59+08:00", "2026-04-21",
    )
    for source, cmd in cmds.items():
        assert "--profile" in cmd, f"{source} 缺 --profile"
        assert cmd[cmd.index("--profile") + 1] == "cli_x"


def test_build_commands_json_filters_are_valid(scan_module):
    """docs/mail 的 --filter 必须是合法 JSON，否则 lark-cli 会 400。"""
    cmds = scan_module.build_commands(
        "p", "ou_xyz", "Alice",
        "2026-04-21T00:00:00+08:00", "2026-04-21T23:59:59+08:00", "2026-04-21",
    )
    for source in ("docs_mine", "docs_at_me", "mail"):
        cmd = cmds[source]
        filter_idx = cmd.index("--filter")
        filter_json = cmd[filter_idx + 1]
        parsed = json.loads(filter_json)
        assert isinstance(parsed, dict)


def test_build_commands_docs_mine_filters_by_creator(scan_module):
    cmds = scan_module.build_commands(
        "p", "ou_mine", "Bob",
        "2026-04-21T00:00:00+08:00", "2026-04-21T23:59:59+08:00", "2026-04-21",
    )
    filter_json = cmds["docs_mine"][cmds["docs_mine"].index("--filter") + 1]
    filter_obj = json.loads(filter_json)
    assert filter_obj["creator_ids"] == ["ou_mine"]
    assert filter_obj["sort_type"] == "OPEN_TIME"


def test_build_commands_docs_at_me_uses_name_as_query(scan_module):
    cmds = scan_module.build_commands(
        "p", "ou_abc", "李四",
        "2026-04-21T00:00:00+08:00", "2026-04-21T23:59:59+08:00", "2026-04-21",
    )
    cmd = cmds["docs_at_me"]
    assert "--query" in cmd
    assert cmd[cmd.index("--query") + 1] == "李四"
    filter_obj = json.loads(cmd[cmd.index("--filter") + 1])
    assert filter_obj["only_comment"] is True


def test_build_commands_approval_two_topics(scan_module):
    cmds = scan_module.build_commands(
        "p", "ou", "N", "2026-04-21T00:00:00+08:00",
        "2026-04-21T23:59:59+08:00", "2026-04-21",
    )
    pending = cmds["approval_pending"][cmds["approval_pending"].index("--params") + 1]
    initiated = cmds["approval_initiated"][cmds["approval_initiated"].index("--params") + 1]
    assert json.loads(pending)["topic"] == "1"
    assert json.loads(initiated)["topic"] == "3"


# ─────────────────────────────────────────────
# 端到端：用 shim 替换 lark-cli 执行 scan.py
# ─────────────────────────────────────────────

def _write_shim(tmp_path, response_map):
    """在 tmp_path 下创建假的 lark-cli，根据命令参数返回预设 JSON。

    response_map: dict of {match_substring: json_string} — 只要命令里出现
    match_substring 就返回对应 JSON。未命中返回 {"ok": true, "data": []}.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir()

    if sys.platform == "win32":
        shim = bindir / "lark-cli.cmd"
        # Windows batch shim
        matchers = "\n".join(
            f'echo %* | findstr /C:"{k}" >nul && (echo {v.replace("%", "%%")}& exit /b 0)'
            for k, v in response_map.items()
        )
        shim.write_text(
            "@echo off\n"
            f"{matchers}\n"
            'echo {"ok": true, "data": []}\n'
            "exit /b 0\n",
            encoding="utf-8",
        )
    else:
        shim = bindir / "lark-cli"
        py_map = json.dumps(response_map)
        shim.write_text(textwrap.dedent(f"""\
            #!/usr/bin/env python3
            import json, sys
            args = " ".join(sys.argv[1:])
            mapping = {py_map}
            for key, val in mapping.items():
                if key in args:
                    print(val)
                    sys.exit(0)
            print(json.dumps({{"ok": True, "data": []}}))
            """))
        shim.chmod(0o755)

    return bindir


def _run_scan(tmp_path, response_map, extra_args=None):
    bindir = _write_shim(tmp_path, response_map)
    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env["PATH"]

    profiles = [{"profile": "cli_a", "open_id": "ou_a", "name": "Alice"}]
    cmd = [
        sys.executable, str(SCRIPT),
        "--profiles-json", json.dumps(profiles),
        "--mode", "full",
    ]
    if extra_args:
        cmd.extend(extra_args)

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)
    return proc


def test_e2e_full_scan_returns_valid_json(tmp_path):
    proc = _run_scan(tmp_path, {"messages-search": '{"ok": true, "data": {"messages": []}}'})
    assert proc.returncode == 0, f"stderr: {proc.stderr}"
    output = json.loads(proc.stdout)
    assert output["mode"] == "full"
    assert len(output["profiles"]) == 1
    assert output["profiles"][0]["profile"] == "cli_a"


def test_e2e_all_9_sources_present(tmp_path):
    proc = _run_scan(tmp_path, {})
    assert proc.returncode == 0
    output = json.loads(proc.stdout)
    sources = output["profiles"][0]["sources"]
    expected = {"im", "vc_search", "calendar", "docs_mine", "docs_at_me",
                "approval_pending", "approval_initiated", "tasks", "mail"}
    assert set(sources.keys()) == expected


def test_e2e_multi_profile_parallel(tmp_path):
    bindir = _write_shim(tmp_path, {})
    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env["PATH"]

    profiles = [
        {"profile": "cli_a", "open_id": "ou_a", "name": "A"},
        {"profile": "cli_b", "open_id": "ou_b", "name": "B"},
    ]
    proc = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--profiles-json", json.dumps(profiles),
         "--mode", "full"],
        capture_output=True, text=True, env=env, timeout=60,
    )
    assert proc.returncode == 0
    output = json.loads(proc.stdout)
    assert len(output["profiles"]) == 2
    assert {p["profile"] for p in output["profiles"]} == {"cli_a", "cli_b"}


def test_e2e_incremental_requires_since(tmp_path):
    bindir = _write_shim(tmp_path, {})
    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env["PATH"]

    proc = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--profiles-json", '[{"profile":"p","open_id":"o","name":"n"}]',
         "--mode", "incremental"],
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert proc.returncode == 2


def test_e2e_incremental_with_since(tmp_path):
    bindir = _write_shim(tmp_path, {})
    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env["PATH"]

    proc = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--profiles-json", '[{"profile":"p","open_id":"o","name":"n"}]',
         "--mode", "incremental",
         "--since", "2026-04-21T12:00:00+08:00"],
        capture_output=True, text=True, env=env, timeout=60,
    )
    assert proc.returncode == 0
    output = json.loads(proc.stdout)
    assert output["mode"] == "incremental"
    assert output["scan_start"] == "2026-04-21T12:00:00+08:00"


def test_e2e_invalid_profiles_json_exits_2(tmp_path):
    bindir = _write_shim(tmp_path, {})
    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env["PATH"]

    proc = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--profiles-json", "[]",
         "--mode", "full"],
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert proc.returncode == 2


def test_e2e_missing_field_exits_2(tmp_path):
    bindir = _write_shim(tmp_path, {})
    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env["PATH"]

    proc = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--profiles-json", '[{"profile":"p"}]',  # 缺 open_id / name
         "--mode", "full"],
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert proc.returncode == 2
