#!/usr/bin/env python3
"""Claude Code 发布/编辑 hook。

两种事件共用这个脚本：
- PreToolUse(Bash)：命令涉及 git push 或 publish 时检查格式，错误直接 deny。
- PostToolUse(Write|Edit)：编辑 content/ 下的文章后立即检查，错误通过
  decision=block 反馈给 Claude，让它当场修正。
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
EDIT_TOOLS = {"Write", "Edit", "MultiEdit"}


def read_payload(stream=None) -> dict:
    stream = stream or sys.stdin
    try:
        payload = json.load(stream)
    except (json.JSONDecodeError, OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_command(stream=None) -> str:
    payload = read_payload(stream)
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return ""
    return str(tool_input.get("command") or "")


def is_publish_command(command: str) -> bool:
    return bool(PUBLISH_RE.search(command or ""))


def is_direct_push(command: str) -> bool:
    return bool(GIT_PUSH_RE.search(command or "")) and not PUBLISH_CMD_RE.search(command or "")


def is_content_path(path: str, root: Path | None = None) -> bool:
    if not path:
        return False
    root = root or ROOT
    try:
        Path(path).resolve().relative_to((root / "content").resolve())
        return True
    except (OSError, ValueError):
        return False


def run_check(*extra: str) -> subprocess.CompletedProcess[str]:
    args = [sys.executable, str(ROOT / "tools" / "check_format.py"), "--json", *extra]
    return subprocess.run(
        args,
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


def split_issues(report: dict) -> tuple[list[dict], list[dict]]:
    issues = report.get("issues") or []
    errors = [issue for issue in issues if issue.get("severity") == "error"]
    warnings = [issue for issue in issues if issue.get("severity") != "error"]
    return errors, warnings


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


def post_write_check(payload: dict) -> int:
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0
    file_path = str(tool_input.get("file_path") or tool_input.get("path") or "")
    if not is_content_path(file_path):
        return 0

    result = run_check("--changed", "--include-drafts")
    try:
        report = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        report = None

    if report is None:
        if result.returncode == 0:
            return 0
        detail = (result.stdout or result.stderr or "检查器返回非零退出码。").strip()
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": "文章格式检查失败：\n" + detail,
                },
                ensure_ascii=True,
            )
        )
        return 0

    errors, warnings = split_issues(report)
    if errors:
        lines = "\n".join(format_issue(issue) for issue in errors)
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": "文章格式有问题，请修正：\n" + lines,
                },
                ensure_ascii=True,
            )
        )
        return 0
    if warnings:
        lines = "\n".join(format_issue(issue) for issue in warnings)
        print(
            json.dumps(
                {"systemMessage": f"格式检查通过，有 {len(warnings)} 个警告：\n{lines}"},
                ensure_ascii=True,
            )
        )
    return 0


def main() -> int:
    payload = read_payload()
    tool_name = str(payload.get("tool_name") or "")
    if tool_name in EDIT_TOOLS:
        return post_write_check(payload)

    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command") or "") if isinstance(tool_input, dict) else ""
    if not is_publish_command(command):
        return 0

    extra = [] if is_direct_push(command) else ["--changed", "--include-drafts"]
    result = run_check(*extra)
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

    errors, warnings = split_issues(report)
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
