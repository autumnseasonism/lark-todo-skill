#!/usr/bin/env python3
"""Run lark-cli with JSON-valued flags without shell quoting issues.

Examples:

python scripts/lark_cli_json.py \
  --json-arg filter='{"only_comment":true}' \
  -- docs +search --query "Alice" --format json

python scripts/lark_cli_json.py \
  --json-arg params='{"topic":"1"}' \
  -- approval tasks query --format json

PowerShell-friendly pattern:

$env:LARK_JSON='{"topic":"1"}'
python scripts/lark_cli_json.py \
  --json-env params=LARK_JSON \
  -- approval tasks query --format json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys


def _find_cli() -> str:
    return (
        shutil.which("lark-cli.cmd")
        or shutil.which("lark-cli")
        or shutil.which("lark-cli.ps1")
        or "lark-cli"
    )


def _parse_json_arg(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError(
            f"invalid --json-arg {raw!r}; expected name=<json>"
        )
    name, value = raw.split("=", 1)
    if not name:
        raise argparse.ArgumentTypeError("JSON flag name cannot be empty")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid JSON for {name!r}: {exc.msg}"
        ) from exc
    return name, json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))


def _parse_json_env(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError(
            f"invalid --json-env {raw!r}; expected name=ENV_VAR"
        )
    name, env_var = raw.split("=", 1)
    if not name or not env_var:
        raise argparse.ArgumentTypeError("JSON env spec cannot be empty")
    if env_var not in os.environ:
        raise argparse.ArgumentTypeError(f"environment variable {env_var!r} is not set")
    try:
        parsed = json.loads(os.environ[env_var])
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid JSON in environment variable {env_var!r}: {exc.msg}"
        ) from exc
    return name, json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Run lark-cli with JSON args passed safely as argv."
    )
    parser.add_argument(
        "--json-arg",
        action="append",
        default=[],
        metavar="NAME=JSON",
        help="append a JSON-valued CLI flag such as filter={...} or params={...}",
    )
    parser.add_argument(
        "--json-env",
        action="append",
        default=[],
        metavar="NAME=ENV_VAR",
        help="read JSON for a CLI flag from an environment variable",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="command to pass to lark-cli; prefix with -- to stop option parsing",
    )
    args = parser.parse_args(argv)

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("missing lark-cli command after --")

    json_specs: list[tuple[str, str]] = []
    for raw in args.json_arg:
        json_specs.append(_parse_json_arg(raw))
    for raw in args.json_env:
        json_specs.append(_parse_json_env(raw))

    full_cmd = [_find_cli()]
    for name, value in json_specs:
        full_cmd.extend([f"--{name}", value])
    full_cmd.extend(command)

    # JSON flags belong next to the subcommand, not before the root binary.
    cli = full_cmd[0]
    json_pairs = full_cmd[1 : 1 + len(json_specs) * 2]
    rest = full_cmd[1 + len(json_specs) * 2 :]
    run_cmd = [cli] + rest[:]
    insert_at = len(run_cmd)
    for idx, token in enumerate(run_cmd):
        if token.startswith("--"):
            insert_at = idx
            break
    run_cmd[insert_at:insert_at] = json_pairs

    result = subprocess.run(run_cmd)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
