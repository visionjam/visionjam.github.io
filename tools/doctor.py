#!/usr/bin/env python3
"""博客环境与数据自检。

用法：
    python tools/doctor.py
    python tools/doctor.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import blog
import check_format

REPO_ROOT = Path(__file__).resolve().parents[1]
MIN_HUGO = (0, 158, 0)
GENERATED_ROUTES = {
    "/",
    "/about/",
    "/archives/",
    "/ranking/",
    "/search/",
    "/stats/",
    "/tags/",
}


@dataclass
class Issue:
    level: str
    message: str


def issue(level: str, message: str) -> Issue:
    return Issue(level=level, message=message)


def check_hugo() -> list[Issue]:
    hugo = shutil.which("hugo")
    if not hugo:
        return [issue("error", "未找到 Hugo；请安装 Hugo Extended。")]
    result = subprocess.run(
        [hugo, "version"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if result.returncode != 0:
        return [issue("error", "hugo version 执行失败。")]
    output = result.stdout.strip()
    if not blog.is_extended_version(output):
        return [issue("error", f"Hugo 不是 extended 版：{output}")]
    match = re.search(r"hugo v(\d+)\.(\d+)\.(\d+)", output)
    if match:
        version = tuple(int(part) for part in match.groups())
        if version < MIN_HUGO:
            return [issue("error", f"Hugo 版本过低：{output}，至少需要 0.158.0。")]
    return []


def check_theme(root: Path) -> list[Issue]:
    theme = root / "themes" / "PaperMod"
    if not theme.is_dir() or not any(theme.iterdir()):
        return [issue("error", "themes/PaperMod 为空；运行 git submodule update --init --recursive。")]
    status = subprocess.run(
        ["git", "-C", str(root), "submodule", "status", "themes/PaperMod"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if status.returncode == 0 and status.stdout.lstrip().startswith("-"):
        return [issue("error", "PaperMod submodule 未初始化。")]
    return []


def check_python() -> list[Issue]:
    if sys.version_info < (3, 8):
        return [issue("error", f"Python 版本过低：{sys.version.split()[0]}，需要 3.8+。")]
    return []


def check_sections(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for section in check_format.load_main_sections(root):
        if not (root / "content" / section).is_dir():
            issues.append(issue("error", f"mainSections 里的栏目不存在：content/{section}"))
    return issues


def check_hook(root: Path) -> list[Issue]:
    path = root / ".claude" / "settings.json"
    if not path.is_file():
        return [issue("warning", "缺少 .claude/settings.json，发布 hook 未配置。")]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [issue("error", f".claude/settings.json 无法解析：{exc}")]
    hooks = data.get("hooks") or {}
    commands: list[str] = []
    for entries in hooks.values():
        for entry in entries or []:
            for hook in entry.get("hooks") or []:
                if hook.get("command"):
                    commands.append(hook["command"])
    if not any("format_hook.py" in command for command in commands):
        return [issue("warning", "hook 配置里没有调用 tools/format_hook.py。")]
    return []


def check_likes(root: Path) -> list[Issue]:
    path = root / "data" / "likes.json"
    if not path.is_file():
        return [issue("warning", "缺少 data/likes.json。")]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [issue("error", f"data/likes.json 无法解析：{exc}")]
    items = data.get("items")
    if not isinstance(items, dict):
        return [issue("error", "data/likes.json 缺少 items 对象。")]
    known = {
        f"/{article.section}/{article.slug}/"
        for article in (
            check_format.read_article(path, root)
            for path in check_format.article_paths(root, check_format.load_main_sections(root))
        )
    }
    issues: list[Issue] = []
    for key in items:
        if not key.startswith("/"):
            issues.append(issue("error", f"likes 路径必须以 / 开头：{key}"))
        elif key not in known:
            issues.append(issue("warning", f"likes 里有找不到对应文章的路径：{key}"))
    return issues


def check_pinned(root: Path) -> list[Issue]:
    path = root / "data" / "pinned.yml"
    if not path.is_file():
        return [issue("warning", "缺少 data/pinned.yml。")]
    issues: list[Issue] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not re.match(r"^\s*url\s*:", line):
            continue
        value = line.split(":", 1)[1].strip().strip("\"'")
        if value.startswith(("http://", "https://")):
            continue
        if value in GENERATED_ROUTES:
            continue
        match = re.fullmatch(r"/([^/]+)/([^/]+)/", value)
        if match and match.group(1) in check_format.load_main_sections(root):
            index = root / "content" / match.group(1) / match.group(2) / "index.md"
            if not index.is_file():
                issues.append(issue("error", f"pinned.yml:{line_number} 指向不存在的文章：{value}"))
            continue
        issues.append(issue("warning", f"pinned.yml:{line_number} 不是已知的站内路径：{value}"))
    return issues


def run(root: Path = REPO_ROOT) -> list[Issue]:
    issues: list[Issue] = []
    issues.extend(check_hugo())
    issues.extend(check_theme(root))
    issues.extend(check_python())
    issues.extend(check_sections(root))
    issues.extend(check_hook(root))
    issues.extend(check_likes(root))
    issues.extend(check_pinned(root))
    return issues


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="博客环境与数据自检")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--root", help="仓库根目录（默认自动识别）")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else REPO_ROOT
    issues = run(root)
    errors = [item for item in issues if item.level == "error"]
    warnings = [item for item in issues if item.level == "warning"]

    if args.json:
        print(
            json.dumps(
                {
                    "ok": not errors,
                    "issues": [asdict(item) for item in issues],
                },
                ensure_ascii=False,
            )
        )
    else:
        for item in issues:
            prefix = "错误" if item.level == "error" else "警告"
            print(f"{prefix} {item.message}")
        print(f"环境自检：{len(errors)} 个错误，{len(warnings)} 个警告。")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
