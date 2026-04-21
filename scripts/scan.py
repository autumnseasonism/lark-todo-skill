#!/usr/bin/env python3
"""lark-todo 加速器：并行执行 8 个数据源的 lark-cli 命令。

SKILL.md 的 Step A/B/C 通过后，Agent 可选择调用本脚本一次性采集所有数据源。
本脚本只做「并行扫描 + JSON 归一化」——不做过滤、优先级、去重、行动，
那些判断仍在 SKILL.md 的 Agent 侧进行。

使用方式：

    python scripts/scan.py \\
        --profiles-json '<JSON array of {profile,open_id,name}>' \\
        --mode full|incremental \\
        [--since <ISO-8601 timestamp>] \\
        [--concurrency <N>]

退出码：
    0 = 脚本成功执行（单个数据源的失败在返回 JSON 里体现）
    1 = 脚本本身崩溃 / 依赖缺失，Agent 应降级到纯 SKILL.md 流程
    2 = 参数错误
"""

import argparse
import asyncio
import json
import shutil
import sys
from datetime import datetime


ALL_SOURCES = [
    "im", "vc_search", "calendar", "docs_mine", "docs_at_me",
    "approval_pending", "approval_initiated", "tasks", "mail",
]


# 在 Windows 上，asyncio.create_subprocess_exec 走 CreateProcess，不会自动加 .cmd/.exe
# 后缀去 PATH 里找，裸命令名 "lark-cli" 会失败。用 shutil.which 先解析成完整路径。
# Linux/Mac 上 which 结果直接就是 "lark-cli" 或绝对路径，同样可用。
LARK_CLI = shutil.which("lark-cli") or "lark-cli"


def _local_tz_colon() -> str:
    """本地时区偏移，形如 +08:00（非 +0800）。"""
    offset = datetime.now().astimezone().strftime("%z")
    return f"{offset[:3]}:{offset[3:]}" if offset else "+00:00"


def _today_str() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def _today_start_iso() -> str:
    now = datetime.now().astimezone()
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")


def _today_end_iso() -> str:
    now = datetime.now().astimezone()
    return now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat(timespec="seconds")


def build_commands(profile: str, open_id: str, name: str,
                   scan_start: str, scan_end: str, today: str) -> dict:
    """为单个 profile 构建 9 条命令：8 数据源里"文档评论"走两路搜索（mine + at_me），其余 7 源各一条。"""
    tz = _local_tz_colon()
    filter_mine = json.dumps({
        "creator_ids": [open_id],
        "open_time": {"start": f"{today}T00:00:00{tz}"},
        "sort_type": "OPEN_TIME",
    }, ensure_ascii=False)
    filter_atme = json.dumps({
        "only_comment": True,
        "open_time": {"start": f"{today}T00:00:00{tz}"},
    }, ensure_ascii=False)
    filter_mail = json.dumps({
        "folder": "inbox",
        "is_unread": True,
        "time_range": {"start_time": scan_start, "end_time": scan_end},
    }, ensure_ascii=False)

    return {
        "im": [
            LARK_CLI, "im", "+messages-search",
            "--is-at-me", "--start", scan_start, "--end", scan_end,
            "--page-all", "--format", "json", "--profile", profile,
        ],
        "vc_search": [
            LARK_CLI, "vc", "+search",
            "--start", today, "--end", today,
            "--format", "json", "--page-size", "30", "--profile", profile,
        ],
        "calendar": [
            LARK_CLI, "calendar", "+agenda",
            "--format", "json", "--profile", profile,
        ],
        "docs_mine": [
            LARK_CLI, "docs", "+search",
            "--filter", filter_mine,
            "--format", "json", "--profile", profile,
        ],
        "docs_at_me": [
            LARK_CLI, "docs", "+search",
            "--query", name,
            "--filter", filter_atme,
            "--format", "json", "--profile", profile,
        ],
        "approval_pending": [
            LARK_CLI, "approval", "tasks", "query",
            "--params", '{"topic":"1"}',
            "--format", "json", "--profile", profile,
        ],
        "approval_initiated": [
            LARK_CLI, "approval", "tasks", "query",
            "--params", '{"topic":"3"}',
            "--format", "json", "--profile", profile,
        ],
        "tasks": [
            LARK_CLI, "task", "+get-my-tasks",
            "--complete=false",
            "--due-end", f"{today}T23:59:59{tz}",
            "--format", "json", "--profile", profile,
        ],
        "mail": [
            LARK_CLI, "mail", "+triage",
            "--filter", filter_mail,
            "--max", "20", "--format", "json", "--profile", profile,
        ],
    }


async def run_cmd(source: str, cmd: list, sem: asyncio.Semaphore,
                  timeout: float = 30.0) -> dict:
    """执行单条命令并归一化结果为 {source, ok, data|error, elapsed_ms}。

    通过 sem 限流，避免 N profile × 9 源同时起子进程打爆本地或触发 lark-cli 限流。
    """
    async with sem:
        start = datetime.now()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            return {"source": source, "ok": False, "error": "timeout",
                    "elapsed_ms": int((datetime.now() - start).total_seconds() * 1000)}
        except FileNotFoundError:
            return {"source": source, "ok": False, "error": "lark-cli not found on PATH",
                    "elapsed_ms": 0}

        elapsed_ms = int((datetime.now() - start).total_seconds() * 1000)
        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            return {"source": source, "ok": False,
                    "error": (err or out)[:500],
                    "exit_code": proc.returncode,
                    "elapsed_ms": elapsed_ms}

        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            return {"source": source, "ok": False, "error": "invalid json",
                    "raw": out[:500], "elapsed_ms": elapsed_ms}

        return {"source": source, "ok": True, "data": data, "elapsed_ms": elapsed_ms}


async def scan_profile(p: dict, scan_start: str, scan_end: str, today: str,
                       sem: asyncio.Semaphore) -> dict:
    cmds = build_commands(p["profile"], p["open_id"], p["name"],
                          scan_start, scan_end, today)
    assert set(cmds) == set(ALL_SOURCES), \
        f"build_commands/ALL_SOURCES out of sync: {set(cmds) ^ set(ALL_SOURCES)}"
    start = datetime.now()
    results = await asyncio.gather(*[run_cmd(s, c, sem) for s, c in cmds.items()])
    elapsed_ms = int((datetime.now() - start).total_seconds() * 1000)
    return {
        "profile": p["profile"],
        "user_name": p["name"],
        "open_id": p["open_id"],
        "sources": {r["source"]: r for r in results},
        "elapsed_ms": elapsed_ms,
    }


async def main_async(args: argparse.Namespace) -> dict:
    profiles = json.loads(args.profiles_json)
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("--profiles-json 必须是非空 JSON 数组")
    for p in profiles:
        for k in ("profile", "open_id", "name"):
            if not p.get(k):
                raise ValueError(f"每个 profile 必须包含字段 {k}")

    today = _today_str()
    scan_end = _today_end_iso()
    if args.mode == "incremental":
        if not args.since:
            raise ValueError("--since 在 incremental 模式下必填")
        scan_start = args.since
    else:
        scan_start = _today_start_iso()

    sem = asyncio.Semaphore(max(1, args.concurrency))
    start = datetime.now()
    profile_results = await asyncio.gather(
        *[scan_profile(p, scan_start, scan_end, today, sem) for p in profiles]
    )
    total_ms = int((datetime.now() - start).total_seconds() * 1000)

    return {
        "accelerator_version": "1.0.0",
        "mode": args.mode,
        "scan_start": scan_start,
        "scan_end": scan_end,
        "today": today,
        "profiles": profile_results,
        "total_elapsed_ms": total_ms,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="lark-todo 并行数据源采集加速器")
    parser.add_argument("--profiles-json", required=True,
                        help='Profiles 列表，JSON array of {profile, open_id, name}')
    parser.add_argument("--mode", choices=["full", "incremental"], required=True)
    parser.add_argument("--since", help="增量扫描起始时间（ISO 8601），mode=incremental 时必填")
    parser.add_argument("--concurrency", type=int, default=10,
                        help="全局并发上限（同时跑的 lark-cli 子进程数），默认 10")
    args = parser.parse_args()

    if not shutil.which("lark-cli"):
        print(json.dumps({"error": "lark-cli not found on PATH"}), file=sys.stderr)
        sys.exit(1)

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Windows 上 stdout/stderr 默认用系统代码页（如 cp936），遇到中文名会乱码或抛
    # UnicodeEncodeError。强制 utf-8，避免给下游 Agent 喂乱码 JSON。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    try:
        output = asyncio.run(main_async(args))
    except ValueError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(json.dumps({"error": f"accelerator crashed: {e}"}, ensure_ascii=False),
              file=sys.stderr)
        sys.exit(1)

    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
