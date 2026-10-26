#!/usr/bin/env python3
"""线上验收：检查关键路径、搜索索引与文章页渲染。

用法：
    python tools/verify_site.py
    python tools/verify_site.py --proxy http://proxy.example:8080
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import check_format

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "https://visionjam.github.io"
KEY_PATHS = (
    "/",
    "/posts/",
    "/android-guide/",
    "/tags/",
    "/archives/",
    "/search/",
    "/about/",
    "/stats/",
    "/ranking/",
    "/index.xml",
    "/index.json",
)


def published_articles(root: Path) -> list[check_format.Article]:
    articles = []
    for path in check_format.article_paths(root, check_format.load_main_sections(root)):
        article = check_format.read_article(path, root)
        if not article.draft:
            articles.append(article)
    return articles


def site_paths(root: Path) -> list[str]:
    paths = list(KEY_PATHS)
    for article in published_articles(root):
        paths.append(f"/{article.section}/{article.slug}/")
    return paths


def opener(proxy: str | None):
    if proxy:
        handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    else:
        handler = urllib.request.ProxyHandler()
    return urllib.request.build_opener(handler)


def fetch(
    client, url: str, retries: int, delay: int
) -> tuple[int | None, str, str]:
    last_error = ""
    for attempt in range(retries):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "visionjam-blog-verify/1.0", "Cache-Control": "no-cache"},
        )
        try:
            with client.open(request, timeout=20) as response:
                return response.status, response.read().decode("utf-8", "replace"), ""
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            if exc.code == 404 and attempt < retries - 1:
                time.sleep(delay)
                continue
            return exc.code, "", last_error
        except Exception as exc:  # noqa: BLE001 - 网络错误类型较多
            last_error = str(exc)
            if attempt < retries - 1:
                time.sleep(delay)
    return None, "", last_error


def run(
    root: Path,
    base_url: str,
    proxy: str | None,
    retries: int,
    delay: int,
) -> tuple[list[str], list[str]]:
    base = base_url.rstrip("/")
    client = opener(proxy)
    errors: list[str] = []
    warnings: list[str] = []
    bodies: dict[str, str] = {}
    articles = published_articles(root)

    for path in site_paths(root):
        status, body, error = fetch(client, base + path, retries, delay)
        if status == 200:
            bodies[path] = body
        elif status is None:
            errors.append(f"{path} 请求失败：{error}")
        else:
            errors.append(f"{path} 返回 {status}" + (f"（{error}）" if error else ""))

    index_body = bodies.get("/index.json")
    if index_body:
        try:
            items = json.loads(index_body)
        except json.JSONDecodeError as exc:
            errors.append(f"/index.json 无法解析：{exc}")
        else:
            permalinks = {
                str(item.get("permalink") or "")
                for item in items
                if isinstance(item, dict)
            }
            for article in articles:
                suffix = f"/{article.section}/{article.slug}/"
                if not any(link.endswith(suffix) for link in permalinks):
                    errors.append(f"线上搜索索引缺少：{suffix}")

    for article in articles:
        path = f"/{article.section}/{article.slug}/"
        body = bodies.get(path)
        if body is None:
            continue
        if "站内赞" not in body:
            errors.append(f"{path} 缺少站内赞")
        if article.section == "android-guide":
            if "字 · 约" not in body:
                errors.append(f"{path} 缺少字数/阅读时长")
            if "giscus.app" not in body:
                errors.append(f"{path} 缺少评论脚本")

    if not articles:
        warnings.append("没有找到已发布文章。")
    return errors, warnings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="博客线上验收")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--proxy", help="代理地址，例如 http://proxy.example:8080")
    parser.add_argument("--retries", type=int, default=6, help="每个路径的重试次数")
    parser.add_argument("--delay", type=int, default=10, help="重试间隔秒数")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--root", help="仓库根目录（默认自动识别）")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else REPO_ROOT
    errors, warnings = run(root, args.base_url, args.proxy, args.retries, args.delay)

    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings}, ensure_ascii=False))
    else:
        for warning in warnings:
            print(f"警告 {warning}")
        for error in errors:
            print(f"错误 {error}")
        print(f"线上验收：{len(errors)} 个错误，{len(warnings)} 个警告。")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
