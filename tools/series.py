#!/usr/bin/env python3
"""系列文章生成与导航同步。

用法：
    python tools/series.py new --slug next-topic --title "下一篇的标题"
    python tools/series.py sync --check
    python tools/series.py sync --write
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import blog
import check_format

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SECTION = "android-guide"
DEFAULT_TAGS = ["Android", "Android优化"]
CN_DIGITS = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
LIST_LINE_RE = re.compile(r"^\s*\d+\.\s+")
NAV_LINK_RE = re.compile(r"^\s*\d+\.\s+\[([^\]]+)\]\(\.\./([^/)]+)/\)")
NAV_CURRENT_RE = re.compile(r"^\s*\d+\.\s+\*\*(.+?)\*\*（本篇）")
PREV_NEXT_RE = re.compile(r"^>\s*(?:上一篇|下一篇|本篇完)")


@dataclass
class SeriesInfo:
    name: str
    section: str
    articles: list[check_format.Article]
    index_path: Path


def cn_numeral(number: int) -> str:
    if number < 10:
        return CN_DIGITS[number]
    if number < 20:
        return "十" + (CN_DIGITS[number - 10] if number > 10 else "")
    if number < 100:
        tens, ones = divmod(number, 10)
        return CN_DIGITS[tens] + "十" + (CN_DIGITS[ones] if ones else "")
    return str(number)


def article_series(article: check_format.Article) -> str | None:
    raw = article.fields.get("series", ("", 0))[0]
    names = check_format.parse_list(raw) if raw else None
    return names[0] if names else None


def article_weight(article: check_format.Article) -> int | None:
    raw = article.fields.get("weight", ("", 0))[0].strip()
    return int(raw) if raw.isdigit() else None


def short_title(title: str, series: str) -> str:
    prefix = f"{series}（"
    if title.startswith(prefix) and "）：" in title:
        return title.split("）：", 1)[1]
    return title


def load_series(root: Path, section: str, name: str | None = None) -> SeriesInfo:
    section_dir = root / "content" / section
    articles = [
        check_format.read_article(path, root)
        for path in sorted(section_dir.glob("*/index.md"))
    ]
    groups: dict[str, list[check_format.Article]] = {}
    for article in articles:
        series_name = article_series(article)
        if series_name:
            groups.setdefault(series_name, []).append(article)
    if not groups:
        raise ValueError(f"{section} 下没有带 series 字段的文章。")
    if name:
        if name not in groups:
            raise ValueError(f"找不到系列：{name}")
        series_name = name
    elif len(groups) == 1:
        series_name = next(iter(groups))
    else:
        raise ValueError("栏目下有多个系列，请用 --series 指定。")
    grouped = groups[series_name]
    weights = [article_weight(article) for article in grouped]
    if any(weight is None for weight in weights):
        raise ValueError("系列文章需要整数 weight。")
    if len(set(weights)) != len(weights):
        raise ValueError("系列文章的 weight 有重复。")
    ordered = sorted(grouped, key=lambda article: article_weight(article) or 0)
    return SeriesInfo(
        name=series_name,
        section=section,
        articles=ordered,
        index_path=section_dir / "_index.md",
    )


def collect_labels(info: SeriesInfo) -> dict[str, str]:
    labels: dict[str, str] = {}
    for article in info.articles:
        marker = article.text.find("**系列导航**")
        if marker == -1:
            continue
        for line in article.text[marker:].splitlines():
            link = NAV_LINK_RE.match(line)
            if link:
                labels.setdefault(link.group(2), link.group(1))
                continue
            current = NAV_CURRENT_RE.match(line)
            if current:
                labels.setdefault(article.slug, current.group(1))
    return labels


def top_nav(text: str, series: str, weight: int, total: int) -> str:
    pattern = re.compile(
        r"(本文是\[《"
        + re.escape(series)
        + r"》\]\(\.\./\)系列第\s*)\d+(\s*篇[，,]\s*共\s*)\d+(\s*篇)"
    )
    return pattern.sub(rf"\g<1>{weight}\g<2>{total}\g<3>", text, count=1)


def nav_lines(info: SeriesInfo, current: check_format.Article, labels: dict[str, str]) -> list[str]:
    lines: list[str] = []
    for index, article in enumerate(info.articles, 1):
        label = labels.get(article.slug) or short_title(
            article.fields.get("title", ("", 0))[0], info.name
        )
        if article.slug == current.slug:
            lines.append(f"{index}. **{label}**（本篇）")
        else:
            lines.append(f"{index}. [{label}](../{article.slug}/)")
    return lines


def prev_next_label(label: str) -> str:
    """上一页/下一页沿用短标题，去掉导航里的「（第 X 节）」。"""
    return re.sub(r"（第[^）]*节）$", "", label)


def prev_next_line(
    info: SeriesInfo, current: check_format.Article, labels: dict[str, str]
) -> str:
    position = info.articles.index(current)
    total = len(info.articles)

    def label(article: check_format.Article) -> str:
        value = labels.get(article.slug) or short_title(
            article.fields.get("title", ("", 0))[0], info.name
        )
        return prev_next_label(value)

    if position == 0:
        nxt = info.articles[1]
        return f"> 下一篇：[《{label(nxt)}》](../{nxt.slug}/)。"
    if position == total - 1:
        prev = info.articles[position - 1]
        return f"> 上一篇：[《{label(prev)}》](../{prev.slug}/) · 本篇完。"
    prev = info.articles[position - 1]
    nxt = info.articles[position + 1]
    return (
        f"> 上一篇：[《{label(prev)}》](../{prev.slug}/) · "
        f"下一篇：[《{label(nxt)}》](../{nxt.slug}/)。"
    )


def sync_article(
    info: SeriesInfo, article: check_format.Article, labels: dict[str, str]
) -> str:
    weight = article_weight(article) or 0
    text = top_nav(article.text, info.name, weight, len(info.articles))
    marker = "**系列导航**"
    position = text.find(marker)
    generated = nav_lines(info, article, labels)
    tail_line = prev_next_line(info, article, labels)

    if position == -1:
        return text.rstrip() + "\n\n" + marker + "\n\n" + "\n".join(generated) + "\n\n" + tail_line + "\n"

    head = text[: position + len(marker)]
    tail = text[position + len(marker) :]
    lines = tail.splitlines()

    list_start = None
    list_end = None
    for index, line in enumerate(lines):
        if LIST_LINE_RE.match(line):
            if list_start is None:
                list_start = index
            list_end = index + 1
        elif list_start is not None and not LIST_LINE_RE.match(line):
            break

    if list_start is None:
        insert_at = 1 if lines and not lines[0].strip() else 0
        lines[insert_at:insert_at] = [""] + generated + [""]
        list_start = insert_at + 1
        list_end = list_start + len(generated)
    else:
        lines[list_start:list_end] = generated
        list_end = list_start + len(generated)

    tail_index = None
    for index in range(list_end, len(lines)):
        if PREV_NEXT_RE.match(lines[index].strip()):
            tail_index = index
            break
    if tail_index is None:
        lines[list_end:list_end] = ["", tail_line]
    else:
        lines[tail_index] = tail_line

    result = head + "\n".join(lines)
    if text.endswith("\n") and not result.endswith("\n"):
        result += "\n"
    return result


def table_columns(lines: list[str]) -> int:
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and set(stripped.replace("|", "").replace(" ", "")) <= {"-", ":"}:
            return len([cell for cell in stripped.strip("|").split("|")])
    return 4


def sync_index(info: SeriesInfo) -> str | None:
    if not info.index_path.is_file():
        return None
    text = info.index_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    columns = table_columns(lines)

    row_re = re.compile(r"^\|\s*(\d+)\s*\|\s*\[([^\]]+)\]\(([^)/]+)/\)\s*\|")
    row_indices = [index for index, line in enumerate(lines) if row_re.match(line)]
    existing: dict[str, tuple[str, list[str]]] = {}
    for index in row_indices:
        cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
        match = re.search(r"\[([^\]]+)\]\(([^)/]+)/\)", cells[1])
        if match:
            existing[match.group(2)] = (match.group(1), cells[2:])

    labels = collect_labels(info)
    new_rows: list[str] = []
    for weight, article in enumerate(info.articles, 1):
        if article.slug in existing:
            label = existing[article.slug][0]
        else:
            label = labels.get(article.slug) or short_title(
                article.fields.get("title", ("", 0))[0], info.name
            )
        extra = existing.get(article.slug, ("", []))[1]
        cells = [f"{weight:02d}", f"[{label}]({article.slug}/)"]
        for offset in range(2, columns):
            value = extra[offset - 2].strip() if offset - 2 < len(extra) else ""
            cells.append(value or "（待补）")
        new_rows.append("| " + " | ".join(cells) + " |")

    if row_indices:
        start, end = min(row_indices), max(row_indices) + 1
        lines[start:end] = new_rows
    else:
        lines.append("")
        lines.append("| 篇 | 文章 | 内容 | 适合 |")
        lines.append("| --- | --- | --- | --- |")
        lines.extend(new_rows)
    result = "\n".join(lines)
    if text.endswith("\n"):
        result += "\n"
    return result


def sync(
    root: Path,
    section: str = DEFAULT_SECTION,
    series_name: str | None = None,
    write: bool = False,
) -> tuple[list[str], list[str]]:
    info = load_series(root, section, series_name)
    labels = collect_labels(info)
    changed: list[str] = []
    errors: list[str] = []

    for article in info.articles:
        new_text = sync_article(info, article, labels)
        if new_text != article.text:
            changed.append(f"content/{section}/{article.slug}/index.md")
            if write:
                blog.write_text_lf(article.path, new_text)

    new_index = sync_index(info)
    if new_index is not None:
        old_index = info.index_path.read_text(encoding="utf-8")
        if new_index != old_index:
            changed.append(f"content/{section}/_index.md")
            if write:
                blog.write_text_lf(info.index_path, new_index)
        if "（待补）" in new_index:
            errors.append("栏目页目录里有「（待补）」，请补充内容说明和适合人群。")

    return changed, errors


def new_article(
    root: Path,
    section: str,
    slug: str,
    title: str,
    date: dt.date,
    tags: list[str],
    published: bool,
    series_name: str | None = None,
    do_sync: bool = True,
) -> Path:
    blog.validate_slug(slug)
    info = load_series(root, section, series_name)
    weight = max(article_weight(article) or 0 for article in info.articles) + 1
    total = len(info.articles) + 1
    if title.startswith(f"{info.name}（"):
        full_title = title
    else:
        full_title = f"{info.name}（{cn_numeral(weight)}）：{title}"
    labels = collect_labels(info)
    labels[slug] = short_title(full_title, info.name)

    path = root / "content" / section / slug / "index.md"
    if path.parent.exists():
        raise FileExistsError(f"文件夹已存在：{path.parent}")
    path.parent.mkdir(parents=True)

    article = check_format.Article(
        path=path,
        rel=path.relative_to(root).as_posix(),
        text="",
        fields={},
        body_lines=[],
        body_start=1,
        frontmatter="missing",
        draft=not published,
    )
    generated = nav_lines(
        SeriesInfo(info.name, section, info.articles + [article], info.index_path),
        article,
        labels,
    )
    tail = prev_next_line(
        SeriesInfo(info.name, section, info.articles + [article], info.index_path),
        article,
        labels,
    )
    body = (
        f"> 本文是[《{info.name}》](../)系列第 {weight} 篇，共 {total} 篇。  \n"
        f"> 对应第 {weight} 节（待补）。  \n"
        "> 适合：（待补）。  \n\n"
        "在这里开始写作。\n\n"
        "**系列导航**\n\n"
        + "\n".join(generated)
        + f"\n\n{tail}\n"
    )
    frontmatter = [
        "---",
        f"title: {json.dumps(full_title, ensure_ascii=False)}",
        f"date: {date.isoformat()}",
        f"draft: {'false' if published else 'true'}",
        f"weight: {weight}",
        f"tags: {json.dumps(tags, ensure_ascii=False)}",
        f"series: {json.dumps([info.name], ensure_ascii=False)}",
        'summary: ""',
        "---",
        "",
    ]
    blog.write_text_lf(path, "\n".join(frontmatter) + body)
    if do_sync:
        sync(root, section, info.name, write=True)
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="系列文章生成与导航同步")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="新建一篇系列文章")
    new_parser.add_argument("--section", default=DEFAULT_SECTION)
    new_parser.add_argument("--series", help="系列名（栏目下有多个系列时指定）")
    new_parser.add_argument("--slug", required=True, help="文章目录名")
    new_parser.add_argument("--title", required=True, help="标题（不用带系列前缀）")
    new_parser.add_argument("--date", default=dt.date.today().isoformat())
    new_parser.add_argument("--tags", default=",".join(DEFAULT_TAGS))
    new_parser.add_argument("--published", action="store_true", help="直接设为 draft: false")
    new_parser.add_argument("--no-sync", action="store_true", help="不更新其他文章和栏目页")
    new_parser.add_argument("--root", help="仓库根目录（默认自动识别）")

    sync_parser = subparsers.add_parser("sync", help="同步系列导航和栏目页目录")
    sync_parser.add_argument("--section", default=DEFAULT_SECTION)
    sync_parser.add_argument("--series", help="系列名（栏目下有多个系列时指定）")
    sync_parser.add_argument("--check", action="store_true", help="只检查（默认行为）")
    sync_parser.add_argument("--write", action="store_true", help="写入改动（默认只检查）")
    sync_parser.add_argument("--root", help="仓库根目录（默认自动识别）")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else REPO_ROOT

    try:
        if args.command == "new":
            date = dt.date.fromisoformat(args.date)
            tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]
            path = new_article(
                root=root,
                section=args.section,
                slug=args.slug,
                title=args.title,
                date=date,
                tags=tags,
                published=args.published,
                series_name=args.series,
                do_sync=not args.no_sync,
            )
            print(f"已创建：{path.relative_to(root).as_posix()}")
            print("请补充 summary、正文，并检查导航里的「（待补）」占位。")
            return 0

        changed, errors = sync(
            root, args.section, args.series, write=args.write
        )
        for path in changed:
            print(("已写入：" if args.write else "需要更新：") + path)
        for error in errors:
            print(f"提示：{error}")
        if not changed:
            print("系列导航和栏目页目录已是最新。")
        elif not args.write:
            print("这是检查模式；加 --write 写入改动。")
            return 1
        return 0
    except (ValueError, FileExistsError) as exc:
        print(f"失败：{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
