#!/usr/bin/env python3
"""生成博客与知乎归档的跨站发布统计快照。"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from datetime import datetime
from html import unescape
from pathlib import Path

import check_format

SCHEMA_VERSION = 1
READING_SPEED = 400

_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_FENCE_RE = re.compile(r"^\s*```.*$", re.MULTILINE)
_HTML_RE = re.compile(r"<[^>]*>")
_MD_CHARS_RE = re.compile(r"[#*_~`>]")
_LIST_RE = re.compile(r"^\s*[-+]\s+", re.MULTILINE)
_BASE_URL_RE = re.compile(r'(?m)^baseURL:\s*"([^"]+)"')


def count_text(markdown: str) -> int:
    """统计正文可见字符数：去掉 Markdown 标记、图片与链接地址，保留文字和标点。"""
    text = _FENCE_RE.sub("", markdown or "")
    text = _IMAGE_RE.sub("", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _HTML_RE.sub("", text)
    text = _LIST_RE.sub("", text)
    text = _MD_CHARS_RE.sub("", text)
    text = unescape(text)
    return sum(1 for char in text if not char.isspace())


def reading_minutes(words: int) -> int:
    if words <= 0:
        return 0
    return max(1, math.ceil(words / READING_SPEED))


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_document(path: Path) -> dict:
    return _load_json(Path(path))


def _base_url(root: Path) -> str:
    try:
        text = (root / "hugo.yml").read_text(encoding="utf-8")
    except OSError:
        return ""
    match = _BASE_URL_RE.search(text)
    return match.group(1).rstrip("/") if match else ""


def _site_likes(root: Path) -> dict:
    items = _load_json(root / "data" / "likes.json").get("items") or {}
    return items if isinstance(items, dict) else {}


def _like_count(likes: dict, rel_path: str) -> int:
    entry = likes.get(rel_path)
    if not isinstance(entry, dict):
        return 0
    try:
        return int(entry.get("likes") or 0)
    except (TypeError, ValueError):
        return 0


def _git_lastmod(root: Path, rel_path: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--format=%cs", "--", rel_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _field(article: check_format.Article, name: str) -> str:
    value = article.fields.get(name)
    return value[0] if value else ""


def _sort_items(items: list[dict]) -> list[dict]:
    return sorted(
        items,
        key=lambda item: (
            str(item.get("source", "")),
            str(item.get("date", "")),
            str(item.get("id", "")),
        ),
    )


def blog_items(root: Path) -> list[dict]:
    root = Path(root).resolve()
    sections = check_format.load_main_sections(root)
    base_url = _base_url(root)
    likes = _site_likes(root)
    items: list[dict] = []
    for path in check_format.article_paths(root, sections):
        article = check_format.read_article(path, root)
        if article.draft:
            continue
        title = _field(article, "title")
        date = _field(article, "date")
        if not title or not date:
            continue
        section = article.section
        slug = article.slug
        rel_path = f"/{section}/{slug}/"
        words = count_text("\n".join(article.body_lines))
        items.append(
            {
                "source": "blog",
                "kind": section,
                "id": f"{section}/{slug}",
                "title": title,
                "url": (base_url + rel_path) if base_url else rel_path,
                "rel_path": rel_path,
                "date": date,
                "lastmod": _git_lastmod(
                    root, f"content/{section}/{slug}/index.md"
                )
                or date,
                "words": words,
                "minutes": reading_minutes(words),
                "votes": 0,
                "comments": 0,
                "site_likes": _like_count(likes, rel_path),
                "duplicate": False,
            }
        )
    return _sort_items(items)


def merge_source(
    existing: list[dict], new_items: list[dict], source: str
) -> list[dict]:
    kept = [item for item in existing if item.get("source") != source]
    return _sort_items(kept + list(new_items))


def write_document(
    path: Path, items: list[dict], generated_at: str | None = None
) -> bool:
    path = Path(path)
    old = load_document(path)
    if old.get("items") == items and old.get("generated_at"):
        return False
    stamp = generated_at or datetime.now().astimezone().isoformat(timespec="seconds")
    document = {"version": SCHEMA_VERSION, "generated_at": stamp, "items": items}
    text = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def check_blog(root: Path) -> list[str]:
    root = Path(root).resolve()
    path = root / "data" / "output_stats.json"
    if not path.is_file():
        return ["缺少 data/output_stats.json（运行 python tools/output_stats.py --side blog）"]
    document = load_document(path)
    issues: list[str] = []
    if document.get("version") != SCHEMA_VERSION:
        issues.append(f"快照 version 不是 {SCHEMA_VERSION}")
    items = document.get("items")
    if not isinstance(items, list):
        return issues + ["快照缺少 items 列表"]
    sources = {item.get("source") for item in items if isinstance(item, dict)}
    if "blog" not in sources:
        issues.append("快照缺少博客条目")
    if "zhihu" not in sources:
        issues.append("快照缺少知乎条目")
    actual = blog_items(root)
    stored = {
        item.get("id"): item
        for item in items
        if isinstance(item, dict) and item.get("source") == "blog"
    }
    if set(stored) != {item["id"] for item in actual}:
        issues.append(
            "快照的博客条目与当前内容不一致（运行 python tools/output_stats.py --side blog）"
        )
        return issues
    fields = (
        "kind",
        "id",
        "title",
        "url",
        "rel_path",
        "date",
        "words",
        "minutes",
        "duplicate",
        "votes",
        "comments",
    )
    for item in actual:
        old = stored.get(item["id"])
        differing = [
            field for field in fields if old is None or old.get(field) != item.get(field)
        ]
        if differing:
            issues.append(
                f"快照的博客条目 {item['id']} 与当前内容不一致："
                + ", ".join(differing)
            )
    return issues


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成跨站发布统计快照。")
    parser.add_argument("--side", choices=("blog",), default="blog")
    parser.add_argument(
        "--blog-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="博客仓库根目录（默认：本脚本所在仓库）",
    )
    parser.add_argument("--check", action="store_true", help="只校验，不写文件")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不写文件")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.blog_root).resolve()
    if args.check:
        issues = check_blog(root)
        for issue in issues:
            print(f"问题：{issue}")
        return 1 if issues else 0
    items = blog_items(root)
    if args.dry_run:
        print(f"博客 {len(items)} 条（dry run，未写入）")
        return 0
    path = root / "data" / "output_stats.json"
    existing = load_document(path).get("items") or []
    merged = merge_source(existing, items, "blog")
    changed = write_document(path, merged)
    suffix = "" if changed else "（无变化）"
    print(f"博客 {len(items)} 条 -> {path}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
