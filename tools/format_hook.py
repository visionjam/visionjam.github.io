#!/usr/bin/env python3
"""Claude Code PreToolUse hook：发布前检查文章格式。

只在命令涉及 git push 或 publish 时运行：
- publish 命令：检查 content/ 下的改动（含草稿，发布工具会先把草稿改为正式）。
- git push：检查全部已发布文章，避免提交后才发现问题。

格式错误时输出 permissionDecision=deny，阻止本次命令。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISH_CMD_RE = re.compile(r"(?:\bblog\.py\s+publish\b|\bpublish\.(?:bat|sh)\b)", re.IGNORECASE)
GIT_PUSH_RE = re.compile(r"\bgit\b[^\n;&|]*\bpush\b", re.IGNORECASE)
PUBLISH_RE = re.compile(PUBLISH_CMD_RE.pattern + r"|" + GIT_PUSH_RE.pattern, re.IGNORECASE)


def read_command(stream=None) -> str:
    stream = stream or sys.stdin
    try:
        payload = json.load(stream)
    except (json.JSONDecodeError, OSError, ValueError):
        return ""
    if not isinstance(payload, dict):
        return ""
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return ""
    return str(tool_input.get("command") or "")


def is_publish_command(command: str) -> bool:
    return bool(PUBLISH_RE.search(command or ""))


def is_direct_push(command: str) -> bool:
    return bool(GIT_PUSH_RE.search(command or "")) and not PUBLISH_CMD_RE.search(command or "")


def run_check(command: str) -> subprocess.CompletedProcess[str]:
    args = [sys.executable, str(ROOT / "tools" / "check_format.py"), "--json"]
    if not is_direct_push(command):
        args.extend(["--changed", "--include-drafts"])
    return subprocess.run(
        args,
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


def format_issue(issue: dict) -> str:
    return f"{issue.get('path', '')}:{issue.get('line', 1)} [{issue.get('code', '')}] {issue.get('message', '')}"


def deny(reason: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
        "systemMessage": "文章格式检查未通过，已阻止发布。",
    }
    print(json.dumps(payload, ensure_ascii=True))


def main() -> int:
    command = read_command()
    if not is_publish_command(command):
        return 0

    result = run_check(command)
    try:
        report = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        report = None

    if report is None:
        if result.returncode == 0:
            return 0
        output = (result.stdout or "").strip()
        if result.stderr and result.stderr.strip():
            output = (output + "\n" + result.stderr.strip()).strip()
        deny("文章格式检查未通过，已阻止本次发布：\n" + (output or "检查器返回非零退出码。"))
        return 0

    issues = report.get("issues") or []
    errors = [issue for issue in issues if issue.get("severity") == "error"]
    warnings = [issue for issue in issues if issue.get("severity") != "error"]

    if errors:
        lines = "\n".join(format_issue(issue) for issue in errors)
        deny("文章格式检查未通过，已阻止本次发布：\n" + lines)
        return 0

    if warnings:
        lines = "\n".join(format_issue(issue) for issue in warnings)
        print(
            json.dumps(
                {
                    "systemMessage": f"格式检查通过，有 {len(warnings)} 个警告：\n{lines}",
                },
                ensure_ascii=True,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
