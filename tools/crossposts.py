#!/usr/bin/env python3
"""自动匹配同时发布在博客与知乎归档的文章，生成双向跳转数据。"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

BLOG_SECTIONS = ("posts", "android-guide")
ARCHIVE_KINDS = ("articles",)
BLOG_BASE = "https://visionjam.github.io/"
ARCHIVE_BASE = "https://visionjam.github.io/zhihu-archive/"
FRONT_MATTER = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.S)


def _front_matter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER.match(text)
    return match.group(1) if match else ""


def _field(front: str, name: str) -> str:
    match = re.search(rf"^{name}:\s*(.*)$", front, re.M)
    if not match:
        return ""
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1]
    return value


def normalize_title(value: str) -> str:
    """NFKC + 去掉空白和标点，只保留文字与数字。"""
    value = unicodedata.normalize("NFKC", value or "").casefold()
    return "".join(ch for ch in value if ch.isalnum())


def scan_blog(root: Path, sections: tuple[str, ...] = BLOG_SECTIONS) -> list[dict]:
    root = Path(root)
    records: list[dict] = []
    for section in sections:
        for path in sorted((root / "content" / section).glob("*/index.md")):
            front = _front_matter(path)
            title = _field(front, "title")
            if not title or _field(front, "draft").lower() == "true":
                continue
            relative = path.parent.relative_to(root / "content").as_posix()
            records.append(
                {
                    "title": title,
                    "permalink": f"/{relative}/",
                    "url": BLOG_BASE + relative + "/",
                    "summary": normalize_title(_field(front, "summary")),
                    "path": str(path),
                }
            )
    return records


def scan_archive(
    root: Path, kinds: tuple[str, ...] = ARCHIVE_KINDS
) -> list[dict]:
    root = Path(root)
    records: list[dict] = []
    for kind in kinds:
        for path in sorted((root / "content" / kind).glob("*/index.md")):
            front = _front_matter(path)
            title = _field(front, "title")
            zhihu_id = _field(front, "zhihu_id")
            if not title or not zhihu_id:
                continue
            records.append(
                {
                    "title": title,
                    "zhihu_id": zhihu_id,
                    "kind": kind,
                    "url": f"{ARCHIVE_BASE}{kind}/{zhihu_id}/",
                    "summary": normalize_title(_field(front, "summary")),
                    "path": str(path),
                }
            )
    return records


def _title_index(records: list[dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for record in records:
        index.setdefault(normalize_title(record["title"]), []).append(record)
    return index


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _best_archive(blog: dict, candidates: list[dict]) -> dict | None:
    if len(candidates) == 1:
        return candidates[0]
    ranked = sorted(
        candidates,
        key=lambda item: _similarity(blog["summary"], item["summary"]),
        reverse=True,
    )
    top = _similarity(blog["summary"], ranked[0]["summary"])
    if len(ranked) > 1 and abs(
        top - _similarity(blog["summary"], ranked[1]["summary"])
    ) < 1e-9:
        return None
    if top >= 0.5:
        return ranked[0]
    return None


def match_records(
    blog_records: list[dict], archive_records: list[dict]
) -> tuple[list[tuple[dict, dict]], list[tuple[list[dict], list[dict]]]]:
    blog_index = _title_index(blog_records)
    archive_index = _title_index(archive_records)
    pairs: list[tuple[dict, dict]] = []
    ambiguous: list[tuple[list[dict], list[dict]]] = []
    for key, blogs in blog_index.items():
        archives = archive_index.get(key, [])
        if not archives:
            continue
        if len(blogs) == 1:
            best = _best_archive(blogs[0], archives)
            if best:
                pairs.append((blogs[0], best))
            else:
                ambiguous.append((blogs, archives))
        else:
            ambiguous.append((blogs, archives))
    return pairs, ambiguous


def build_mappings(
    blog_records: list[dict],
    archive_records: list[dict],
    existing: dict | None = None,
) -> tuple[dict, dict, list[tuple[list[dict], list[dict]]]]:
    """生成归档侧和博客侧的映射；保留 URL 仍有效的既有手动条目。"""
    existing = existing or {}
    pairs, ambiguous = match_records(blog_records, archive_records)
    blogs_by_url = {record["url"].rstrip("/"): record for record in blog_records}
    archives_by_id = {record["zhihu_id"]: record for record in archive_records}

    archive_map: dict[str, dict] = {}
    for blog, archive in pairs:
        archive_map[archive["zhihu_id"]] = {
            "url": blog["url"],
            "title": archive["title"],
            "blog_title": blog["title"],
        }

    for zhihu_id, entry in existing.items():
        if zhihu_id in archive_map:
            continue
        blog = blogs_by_url.get(str(entry.get("url") or "").rstrip("/"))
        archive = archives_by_id.get(str(zhihu_id))
        if not blog or not archive:
            continue
        archive_map[zhihu_id] = {
            "url": blog["url"],
            "title": archive["title"],
            "blog_title": blog["title"],
        }

    blog_map: dict[str, dict] = {}
    for zhihu_id, entry in archive_map.items():
        archive = archives_by_id.get(zhihu_id)
        blog = blogs_by_url.get(str(entry["url"]).rstrip("/"))
        if not archive or not blog:
            continue
        blog_map[blog["permalink"]] = {
            "archive_url": archive["url"],
            "zhihu_id": zhihu_id,
            "title": archive["title"],
        }
    return archive_map, blog_map, ambiguous


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def run(
    blog_root: Path,
    archive_root: Path,
    kinds: tuple[str, ...] = ARCHIVE_KINDS,
    dry_run: bool = False,
) -> tuple[list[dict], list[dict], dict, dict, list]:
    blog_records = scan_blog(blog_root)
    archive_records = scan_archive(archive_root, kinds)
    existing = _load_json(Path(archive_root) / "data" / "crossposts.json")
    archive_map, blog_map, ambiguous = build_mappings(
        blog_records, archive_records, existing
    )
    if not dry_run:
        _write_json(Path(archive_root) / "data" / "crossposts.json", archive_map)
        _write_json(Path(blog_root) / "data" / "zhihu_crossposts.json", blog_map)
    return blog_records, archive_records, archive_map, blog_map, ambiguous


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="自动匹配博客与知乎归档中的同一篇文章，生成双向跳转数据。"
    )
    parser.add_argument(
        "--blog-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="博客仓库根目录（默认：本脚本所在仓库）",
    )
    parser.add_argument(
        "--archive-root",
        default="",
        help="归档仓库根目录（默认：博客仓库同级的 zhihu-archive）",
    )
    parser.add_argument(
        "--include-answers",
        action="store_true",
        help="同时匹配知乎回答（默认只匹配知乎文章）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    blog_root = Path(args.blog_root).resolve()
    archive_root = (
        Path(args.archive_root).resolve()
        if args.archive_root
        else (blog_root.parent / "zhihu-archive").resolve()
    )
    kinds = ("articles", "answers") if args.include_answers else ARCHIVE_KINDS
    blog_records, archive_records, archive_map, blog_map, ambiguous = run(
        blog_root, archive_root, kinds=kinds, dry_run=args.dry_run
    )

    print(
        f"博客 {len(blog_records)} 篇 / 归档 {len(archive_records)} 篇 / "
        f"互链 {len(archive_map)} 组 / 歧义 {len(ambiguous)} 组"
    )
    for entry in archive_map.values():
        print(f"  {entry['blog_title']}  <->  {entry['title']}")
    for blogs, archives in ambiguous:
        print(
            "  歧义："
            + " / ".join(item["title"] for item in blogs)
            + "  <->  "
            + " / ".join(item["title"] for item in archives)
        )
    unmatched_blog = [
        record["title"]
        for record in blog_records
        if record["permalink"] not in blog_map
    ]
    if unmatched_blog:
        print("  博客未匹配：" + "；".join(unmatched_blog))
    if args.dry_run:
        print("（dry-run，未写文件）")
    else:
        print(
            f"已写入 {blog_root / 'data/zhihu_crossposts.json'} 与 "
            f"{archive_root / 'data/crossposts.json'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
