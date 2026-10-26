#!/usr/bin/env python3
"""仓库级隐私扫描。

与 publish 时的 content/ 扫描不同，这里默认扫描整个仓库的文本文件，
用于在 CI、pre-push 或发布前发现工具、测试、文档里的本机路径、密钥等。

用法：
    python tools/check_privacy.py
    python tools/check_privacy.py --changed
    python tools/check_privacy.py --json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import blog

REPO_ROOT = Path(__file__).resolve().parents[1]

# 说明：这些文件里的命中是规则本身或公开文档中的通用示例，不是泄露。
ALLOW = {
    "tools/blog.py": {"*"},
    "tools/check_privacy.py": {"*"},
    "README.md": {"local_address"},
}


def git_paths(root: Path, *args: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if result.returncode != 0:
        return []
    return [path for path in result.stdout.split("\0") if path]


def repo_paths(root: Path, changed: bool = False) -> list[str]:
    if changed:
        tracked = git_paths(root, "diff", "--name-only", "-z", "HEAD")
        untracked = git_paths(root, "ls-files", "--others", "--exclude-standard", "-z")
        return list(dict.fromkeys(tracked + untracked))
    return git_paths(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")


def allowed(path: str, kind: str) -> bool:
    kinds = ALLOW.get(path)
    return bool(kinds and ("*" in kinds or kind in kinds))


def scan_repo(root: Path = REPO_ROOT, changed: bool = False) -> list[blog.Finding]:
    paths = repo_paths(root, changed)
    findings, _ = blog.scan_files(root, paths)
    return [finding for finding in findings if not allowed(finding.path, finding.kind)]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="仓库级隐私扫描")
    parser.add_argument("--changed", action="store_true", help="只扫描改动和未跟踪文件")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--root", help="仓库根目录（默认自动识别）")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else REPO_ROOT
    findings = scan_repo(root, changed=args.changed)

    if args.json:
        print(
            json.dumps(
                {"ok": not findings, "findings": [asdict(finding) for finding in findings]},
                ensure_ascii=False,
            )
        )
    else:
        for finding in findings:
            print(f"{finding.path}:{finding.line} [{finding.kind}] {finding.text}")
        print(f"隐私扫描：{'未发现可疑内容' if not findings else f'{len(findings)} 处可疑内容'}。")

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
