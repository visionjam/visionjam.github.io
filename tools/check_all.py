#!/usr/bin/env python3
"""一站式检查：格式 + 隐私 + Hugo 构建 + 输出一致性。

用法：
    python tools/check_all.py
    python tools/check_all.py --skip-build
    python tools/check_all.py --json
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import blog
import check_format
import check_privacy

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://visionjam.github.io"
LINK_RE = re.compile(r'(?:href|src)="([^"]+)"')
EXTERNAL_PREFIXES = ("/zhihu-archive/",)


@dataclass
class Summary:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked: dict[str, int] = field(default_factory=dict)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def base_url(root: Path) -> str:
    try:
        text = (root / "hugo.yml").read_text(encoding="utf-8")
    except OSError:
        return SITE_URL
    match = re.search(r'(?m)^baseURL:\s*"([^"]+)"', text)
    return match.group(1).rstrip("/") if match else SITE_URL


def published_articles(root: Path) -> list[check_format.Article]:
    sections = check_format.load_main_sections(root)
    articles: list[check_format.Article] = []
    for path in check_format.article_paths(root, sections):
        article = check_format.read_article(path, root)
        if not article.draft:
            articles.append(article)
    return articles


def check_format_step(root: Path, summary: Summary) -> None:
    result = check_format.check_paths(root)
    summary.checked["format"] = result.files
    for issue in result.errors:
        summary.error(f"格式 {issue.path}:{issue.line} [{issue.code}] {issue.message}")
    for issue in result.warnings:
        summary.warn(f"格式 {issue.path}:{issue.line} [{issue.code}] {issue.message}")


def check_privacy_step(root: Path, summary: Summary) -> None:
    findings = check_privacy.scan_repo(root)
    summary.checked["privacy"] = len(findings)
    for finding in findings:
        summary.error(
            f"隐私 {finding.path}:{finding.line} [{finding.kind}] {finding.text}"
        )


def build_site(root: Path, summary: Summary) -> bool:
    if shutil.which("hugo") is None:
        summary.warn("未找到 Hugo，跳过构建和输出检查。")
        return False
    if not blog.hugo_build(root):
        summary.error("Hugo 构建失败。")
        return False
    return True


def check_search_index(root: Path, articles: list[check_format.Article], summary: Summary) -> None:
    path = root / "public" / "index.json"
    if not path.is_file():
        summary.error("缺少 public/index.json（搜索索引）。")
        return
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        summary.error(f"public/index.json 无法解析：{exc}")
        return
    permalinks = {
        str(item.get("permalink") or item.get("url") or "")
        for item in items
        if isinstance(item, dict)
    }
    missing = [
        f"/{article.section}/{article.slug}/"
        for article in articles
        if not any(link.endswith(f"/{article.section}/{article.slug}/") for link in permalinks)
    ]
    summary.checked["search"] = len(articles)
    for suffix in missing:
        summary.error(f"搜索索引缺少文章：{suffix}")


def check_sitemap(root: Path, articles: list[check_format.Article], summary: Summary) -> None:
    path = root / "public" / "sitemap.xml"
    if not path.is_file():
        summary.error("缺少 public/sitemap.xml。")
        return
    text = path.read_text(encoding="utf-8")
    summary.checked["sitemap"] = len(articles)
    for article in articles:
        if f"/{article.section}/{article.slug}/" not in text:
            summary.error(f"sitemap 缺少文章：/{article.section}/{article.slug}/")


def check_feed(root: Path, articles: list[check_format.Article], summary: Summary) -> None:
    path = root / "public" / "index.xml"
    if not path.is_file():
        summary.error("缺少 public/index.xml（RSS）。")
        return
    text = html.unescape(path.read_text(encoding="utf-8"))
    latest = sorted(articles, key=lambda item: item.fields.get("date", ("", 0))[0], reverse=True)[:5]
    summary.checked["feed"] = len(latest)
    for article in latest:
        title = article.fields.get("title", ("", 0))[0]
        if title and title not in text:
            summary.error(f"RSS 缺少最近文章：{title}")


def target_path(public: Path, html_file: Path, raw: str) -> Path | None:
    target = html.unescape(raw).split("#", 1)[0].split("?", 1)[0]
    if not target or target.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return None
    if target.startswith(("http://", "https://", "//")):
        base = base_url(public.parent)
        if not target.startswith(base):
            return None
        target = target[len(base) :] or "/"
    if any(target.startswith(prefix) for prefix in EXTERNAL_PREFIXES):
        return None
    target = urllib.parse.unquote(target)
    if target.startswith("/"):
        resolved = public / target.lstrip("/")
    else:
        resolved = html_file.parent / target
    try:
        resolved = resolved.resolve()
        resolved.relative_to(public.resolve())
    except (OSError, ValueError):
        return None
    if resolved.is_dir():
        return resolved / "index.html"
    return resolved


def check_links(root: Path, summary: Summary) -> None:
    public = root / "public"
    if not public.is_dir():
        summary.error("缺少 public/ 构建产物。")
        return
    missing: dict[str, tuple[str, str]] = {}
    pages = 0
    for html_file in sorted(public.rglob("*.html")):
        pages += 1
        text = html_file.read_text(encoding="utf-8", errors="replace")
        for raw in LINK_RE.findall(text):
            target = target_path(public, html_file, raw)
            if target is None:
                continue
            if not target.exists():
                key = target.relative_to(public).as_posix()
                missing.setdefault(
                    key,
                    (
                        html.unescape(raw),
                        html_file.relative_to(public).as_posix(),
                    ),
                )
    summary.checked["html_pages"] = pages
    for _, (raw, source) in sorted(missing.items()):
        summary.error(f"内部链接目标不存在：{raw}（来自 /{source}）")


def comments_enabled(root: Path) -> bool:
    try:
        text = (root / "hugo.yml").read_text(encoding="utf-8")
    except OSError:
        return False
    match = re.search(r"(?m)^\s*categoryId:\s*\"([^\"]*)\"", text)
    return bool(match and match.group(1).strip())


def check_article_pages(
    root: Path, articles: list[check_format.Article], summary: Summary
) -> None:
    public = root / "public"
    with_comments = comments_enabled(root)
    summary.checked["article_pages"] = len(articles)
    for article in articles:
        page = public / article.section / article.slug / "index.html"
        if not page.is_file():
            summary.error(f"缺少文章页：/{article.section}/{article.slug}/")
            continue
        text = page.read_text(encoding="utf-8", errors="replace")
        if "站内赞" not in text:
            summary.error(f"文章页缺少站内赞：/{article.section}/{article.slug}/")
        if with_comments and "giscus.app" not in text:
            summary.error(f"文章页缺少评论脚本：/{article.section}/{article.slug}/")
        if article.section == "android-guide" and "字 · 约" not in text:
            summary.error(f"安卓文章页缺少字数/阅读时长：/{article.section}/{article.slug}/")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="博客一站式检查")
    parser.add_argument("--skip-build", action="store_true", help="跳过 Hugo 构建和输出检查")
    parser.add_argument("--skip-privacy", action="store_true", help="跳过隐私扫描")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--root", help="仓库根目录（默认自动识别）")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else REPO_ROOT
    summary = Summary()
    articles = published_articles(root)

    check_format_step(root, summary)
    if not args.skip_privacy:
        check_privacy_step(root, summary)

    built = False if args.skip_build else build_site(root, summary)
    if built:
        check_search_index(root, articles, summary)
        check_sitemap(root, articles, summary)
        check_feed(root, articles, summary)
        check_links(root, summary)
        check_article_pages(root, articles, summary)

    if args.json:
        print(
            json.dumps(
                {
                    "ok": not summary.errors,
                    "errors": summary.errors,
                    "warnings": summary.warnings,
                    "checked": summary.checked,
                },
                ensure_ascii=False,
            )
        )
    else:
        for message in summary.warnings:
            print(f"警告 {message}")
        for message in summary.errors:
            print(f"错误 {message}")
        detail = "，".join(f"{key} {value}" for key, value in summary.checked.items())
        print(
            f"一站式检查：{len(summary.errors)} 个错误，"
            f"{len(summary.warnings)} 个警告（{detail}）。"
        )

    return 1 if summary.errors else 0


if __name__ == "__main__":
    sys.exit(main())
