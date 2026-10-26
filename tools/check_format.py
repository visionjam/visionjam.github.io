#!/usr/bin/env python3
"""博客文章格式检查。

规则来源：CLAUDE.md、README.md、archetypes/posts.md，以及
content/android-guide 系列文章的既有结构。

用法：
    python tools/check_format.py              # 检查全部已发布文章
    python tools/check_format.py --changed    # 只检查 content/ 下改动涉及的文章
    python tools/check_format.py --strict     # 警告也视为失败
    python tools/check_format.py --json       # 机器可读输出
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SECTIONS = ("posts", "android-guide")
REQUIRED_FIELDS = ("title", "date", "draft", "tags", "summary")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
H1_RE = re.compile(r"^#(?!#)\s+\S")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\n]+)\)")
LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\n]+)\)")
FENCE_RE = re.compile(r"^(`{3,}|~{3,})")

CN_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


@dataclass(frozen=True)
class Issue:
    path: str
    line: int
    code: str
    message: str
    severity: str = "error"

    @property
    def is_error(self) -> bool:
        return self.severity == "error"


@dataclass
class CheckResult:
    issues: list[Issue] = field(default_factory=list)
    files: int = 0

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.is_error]

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if not issue.is_error]

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class Article:
    path: Path
    rel: str
    text: str
    fields: dict[str, tuple[str, int]]
    body_lines: list[str]
    body_start: int
    frontmatter: str
    draft: bool

    @property
    def slug(self) -> str:
        return self.path.parent.name

    @property
    def section(self) -> str:
        return self.path.parent.parent.name


def cn_number(value: str) -> int | None:
    """把「一」「十二」这类序号转成整数；无法识别时返回 None。"""
    value = value.strip()
    if value.isdigit():
        return int(value)
    if not value or any(char not in CN_DIGITS and char != "十" for char in value):
        return None
    if "十" not in value:
        return CN_DIGITS[value] if len(value) == 1 else None
    head, _, tail = value.partition("十")
    tens = CN_DIGITS.get(head, 1) if head else 1
    ones = CN_DIGITS.get(tail, 0) if tail else 0
    return tens * 10 + ones


def load_main_sections(root: Path) -> tuple[str, ...]:
    try:
        config = (root / "hugo.yml").read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_SECTIONS
    match = re.search(r"(?m)^  mainSections:\n((?:    - \S+\n?)+)", config)
    if not match:
        return DEFAULT_SECTIONS
    sections = tuple(re.findall(r"(?m)^    - (\S+)$", match.group(1)))
    return sections or DEFAULT_SECTIONS


def split_frontmatter(text: str) -> tuple[list[str] | None, list[str], int, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, lines, 1, "missing"
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines[1:index], lines[index + 1 :], index + 2, "ok"
    return None, lines, 1, "unclosed"


def parse_fields(fm_lines: list[str], first_line: int = 2) -> dict[str, tuple[str, int]]:
    fields: dict[str, tuple[str, int]] = {}
    for offset, line in enumerate(fm_lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            quote = value[0]
            value = value[1:-1]
            if quote == '"':
                value = value.replace('\\"', '"').replace("\\\\", "\\")
        fields[key] = (value, first_line + offset)
    return fields


def parse_list(value: str) -> list[str] | None:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return None
    inner = value[1:-1].strip()
    if not inner:
        return []
    quoted = re.findall(r'"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'', inner)
    if quoted:
        return [left or right for left, right in quoted]
    return [item.strip().strip("\"'") for item in inner.split(",") if item.strip()]


def read_article(path: Path, root: Path) -> Article:
    text = path.read_text(encoding="utf-8")
    fm_lines, body_lines, body_start, status = split_frontmatter(text)
    fields = parse_fields(fm_lines) if fm_lines is not None else {}
    draft = fields.get("draft", ("", 0))[0].strip().lower() == "true"
    return Article(
        path=path,
        rel=path.relative_to(root).as_posix(),
        text=text,
        fields=fields,
        body_lines=body_lines,
        body_start=body_start,
        frontmatter=status,
        draft=draft,
    )


def body_rows(article: Article) -> tuple[list[tuple[int, str, bool]], bool]:
    rows: list[tuple[int, str, bool]] = []
    fence: str | None = None
    for offset, line in enumerate(article.body_lines):
        match = FENCE_RE.match(line.lstrip())
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker[0]
            elif marker[0] == fence:
                fence = None
            rows.append((article.body_start + offset, line, True))
            continue
        rows.append((article.body_start + offset, line, fence is not None))
    return rows, fence is not None


def link_target(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("<") and ">" in raw:
        return raw[1 : raw.index(">")]
    parts = raw.split()
    return parts[0] if parts else raw


def is_external(target: str) -> bool:
    return target.startswith(
        ("http://", "https://", "//", "mailto:", "tel:", "data:", "javascript:")
    )


def relative_target_exists(index_path: Path, raw: str) -> bool:
    target = link_target(raw).split("#", 1)[0].split("?", 1)[0]
    if not target:
        return True
    resolved = (index_path.parent / target).resolve()
    if target.endswith("/") or resolved.is_dir():
        return (resolved / "index.md").is_file() or (resolved / "_index.md").is_file()
    return resolved.is_file()


def check_article(article: Article, include_drafts: bool, today: dt.date) -> list[Issue]:
    issues: list[Issue] = []
    rel = article.rel

    if article.frontmatter == "missing":
        return [Issue(rel, 1, "frontmatter.missing", "缺少 frontmatter：文件必须以 --- 开头")]
    if article.frontmatter == "unclosed":
        return [Issue(rel, 1, "frontmatter.unclosed", "frontmatter 没有结束标记 ---")]

    for key in REQUIRED_FIELDS:
        if key not in article.fields:
            issues.append(Issue(rel, 1, "frontmatter.required", f"缺少字段：{key}"))

    title, title_line = article.fields.get("title", ("", 1))
    if not title.strip():
        issues.append(Issue(rel, title_line, "frontmatter.title", "title 不能为空"))
    if title != title.strip():
        issues.append(Issue(rel, title_line, "frontmatter.title_space", "title 首尾不能有空白"))

    date_value, date_line = article.fields.get("date", ("", 1))
    if date_value:
        if not DATE_RE.match(date_value):
            issues.append(
                Issue(rel, date_line, "frontmatter.date", f"date 必须为 YYYY-MM-DD：{date_value}")
            )
        else:
            try:
                date_obj = dt.date.fromisoformat(date_value)
            except ValueError:
                issues.append(
                    Issue(rel, date_line, "frontmatter.date", f"date 不是有效日期：{date_value}")
                )
            else:
                if not article.draft and date_obj > today:
                    issues.append(
                        Issue(
                            rel,
                            date_line,
                            "article.future_date",
                            f"发布日期在未来（{date_value}），buildFuture=false 时不会上线",
                            severity="warning",
                        )
                    )

    draft_value, draft_line = article.fields.get("draft", ("", 1))
    if draft_value.strip().lower() not in {"true", "false"}:
        issues.append(
            Issue(rel, draft_line, "frontmatter.draft", f"draft 必须是 true 或 false：{draft_value}")
        )

    tags_value, tags_line = article.fields.get("tags", ("", 1))
    tags = parse_list(tags_value) if tags_value else None
    if tags_value and tags is None:
        issues.append(
            Issue(rel, tags_line, "frontmatter.tags", "tags 必须是行内数组，例如 [\"Android\", \"优化\"]")
        )
    elif not article.draft and not tags:
        issues.append(Issue(rel, tags_line, "frontmatter.tags_empty", "已发布文章至少需要一个标签"))

    summary, summary_line = article.fields.get("summary", ("", 1))
    if not article.draft and not summary.strip():
        issues.append(Issue(rel, summary_line, "frontmatter.summary", "已发布文章 summary 不能为空"))

    if "lastmod" in article.fields:
        issues.append(
            Issue(
                rel,
                article.fields["lastmod"][1],
                "frontmatter.lastmod",
                "不要手写 lastmod，GitInfo 会自动读取最后提交日期",
                severity="warning",
            )
        )

    if not SLUG_RE.match(article.slug):
        issues.append(
            Issue(
                rel,
                1,
                "file.slug",
                f"文章目录名必须是小写字母、数字和连字符：{article.slug}",
            )
        )

    if article.draft and not include_drafts:
        return issues

    rows, unclosed = body_rows(article)
    if unclosed:
        issues.append(Issue(rel, 1, "body.code_fence", "代码围栏没有闭合"))
    if not any(line.strip() for line in article.body_lines):
        issues.append(Issue(rel, 1, "body.empty", "正文不能为空"))

    for line_number, line, in_code in rows:
        if in_code:
            continue
        if H1_RE.match(line):
            issues.append(
                Issue(
                    rel,
                    line_number,
                    "body.h1",
                    "正文不能使用一级标题（#），文章标题由主题渲染",
                )
            )
        for match in IMAGE_RE.finditer(line):
            target = link_target(match.group(2))
            if not target or is_external(target):
                continue
            if not relative_target_exists(article.path, target):
                issues.append(
                    Issue(rel, line_number, "body.image_missing", f"图片不存在：{target}")
                )
        for match in LINK_RE.finditer(line):
            target = link_target(match.group(2))
            if not target or target.startswith(("#", "/")) or is_external(target):
                continue
            if not relative_target_exists(article.path, target):
                issues.append(
                    Issue(rel, line_number, "body.link_missing", f"相对链接目标不存在：{target}")
                )

    return issues


def series_name(article: Article) -> str | None:
    raw = article.fields.get("series", ("", 0))[0]
    names = parse_list(raw) if raw else None
    return names[0] if names else None


def weight_of(article: Article) -> int | None:
    raw = article.fields.get("weight", ("", 0))[0].strip()
    return int(raw) if raw.isdigit() else None


def check_series(root: Path, articles: list[Article], include_drafts: bool) -> list[Issue]:
    issues: list[Issue] = []
    groups: dict[str, list[Article]] = {}
    for article in articles:
        name = series_name(article)
        if name:
            groups.setdefault(name, []).append(article)

    for name, group in groups.items():
        if len(group) < 2:
            issues.append(
                Issue(
                    group[0].rel,
                    group[0].fields.get("series", ("", 1))[1],
                    "series.single",
                    f"系列「{name}」只有一篇文章",
                    severity="warning",
                )
            )
            continue

        ordered = sorted(
            group,
            key=lambda item: (weight_of(item) is None, weight_of(item) or 10**6, item.rel),
        )
        total = len(group)
        seen_weights: dict[int, list[str]] = {}
        section = ordered[0].section

        for position, article in enumerate(ordered):
            if article.draft and not include_drafts:
                continue

            title, title_line = article.fields.get("title", ("", 1))
            weight = weight_of(article)
            if weight is None:
                issues.append(
                    Issue(
                        article.rel,
                        article.fields.get("weight", ("", 1))[1],
                        "series.weight",
                        "系列文章需要整数 weight",
                    )
                )
            else:
                seen_weights.setdefault(weight, []).append(article.rel)

            title_match = re.match(rf"^{re.escape(name)}（([^）]+)）：\S", title)
            if not title_match:
                issues.append(
                    Issue(
                        article.rel,
                        title_line,
                        "series.title",
                        f"系列文章标题应为「{name}（序号）：标题」",
                    )
                )
            else:
                number = cn_number(title_match.group(1))
                if weight is not None and number is not None and number != weight:
                    issues.append(
                        Issue(
                            article.rel,
                            title_line,
                            "series.title_weight",
                            f"标题序号 {number} 与 weight {weight} 不一致",
                        )
                    )

            top_re = re.compile(
                r"本文是\[《"
                + re.escape(name)
                + r"》\]\(\.\./\)系列第\s*(\d+)\s*篇[，,]\s*共\s*(\d+)\s*篇"
            )
            top_match = top_re.search(article.text)
            if not top_match:
                issues.append(
                    Issue(
                        article.rel,
                        1,
                        "series.top_nav",
                        f"缺少顶部系列导航：本文是[《{name}》](../)系列第 N 篇，共 {total} 篇。",
                    )
                )
            else:
                if weight is not None and int(top_match.group(1)) != weight:
                    issues.append(
                        Issue(
                            article.rel,
                            1,
                            "series.top_nav_number",
                            f"顶部导航写的是第 {top_match.group(1)} 篇，weight 是 {weight}",
                        )
                    )
                if int(top_match.group(2)) != total:
                    issues.append(
                        Issue(
                            article.rel,
                            1,
                            "series.top_nav_total",
                            f"顶部导航写的是共 {top_match.group(2)} 篇，实际有 {total} 篇",
                        )
                    )

            nav_marker = article.text.find("**系列导航**")
            if nav_marker == -1:
                issues.append(
                    Issue(article.rel, 1, "series.bottom_nav", "缺少文末 **系列导航**")
                )
                tail = ""
            else:
                tail = article.text[nav_marker:]

            for other in ordered:
                if other is article:
                    continue
                if f"../{other.slug}/" not in tail:
                    issues.append(
                        Issue(
                            article.rel,
                            1,
                            "series.nav_link",
                            f"文末系列导航缺少 {other.slug} 的链接",
                        )
                    )

            if "（本篇）" not in tail:
                issues.append(
                    Issue(
                        article.rel,
                        1,
                        "series.self_mark",
                        "文末系列导航没有标记（本篇）",
                        severity="warning",
                    )
                )

            if position > 0 and "上一篇：" not in tail:
                issues.append(Issue(article.rel, 1, "series.prev", "文末导航缺少上一篇链接"))
            if position < len(ordered) - 1 and "下一篇：" not in tail:
                issues.append(Issue(article.rel, 1, "series.next", "文末导航缺少下一篇链接"))
            if position == len(ordered) - 1 and "上一篇：" not in tail and "本篇完" not in tail:
                issues.append(
                    Issue(
                        article.rel,
                        1,
                        "series.last",
                        "最后一篇文末应标注「本篇完」或上一篇链接",
                        severity="warning",
                    )
                )

        for weight, paths in seen_weights.items():
            if len(paths) > 1:
                for path in paths:
                    issues.append(
                        Issue(path, 1, "series.weight_duplicate", f"weight {weight} 重复：{'、'.join(paths)}")
                    )

        index_path = root / "content" / section / "_index.md"
        if not index_path.is_file():
            issues.append(
                Issue(
                    f"content/{section}/_index.md",
                    1,
                    "series.index_missing",
                    f"系列「{name}」缺少栏目页 _index.md",
                )
            )
            continue

        index_article = read_article(index_path, root)
        index_fields = index_article.fields
        for key in ("title", "description", "date", "draft"):
            if key not in index_fields:
                issues.append(
                    Issue(
                        index_article.rel,
                        1,
                        "series.index_field",
                        f"栏目页缺少字段：{key}",
                    )
                )
        index_date = index_fields.get("date", ("", 1))[0]
        if index_date and not DATE_RE.match(index_date):
            issues.append(
                Issue(
                    index_article.rel,
                    index_fields["date"][1],
                    "series.index_date",
                    f"栏目页 date 必须为 YYYY-MM-DD：{index_date}",
                )
            )

        for article in ordered:
            if f"({article.slug}/)" not in index_article.text:
                issues.append(
                    Issue(
                        index_article.rel,
                        1,
                        "series.index_link",
                        f"栏目页目录缺少 {article.slug} 的链接",
                    )
                )

        row_count = len(re.findall(r"(?m)^\|\s*\d+\s*\|", index_article.text))
        if row_count and row_count != total:
            issues.append(
                Issue(
                    index_article.rel,
                    1,
                    "series.index_count",
                    f"栏目页目录有 {row_count} 行，系列实际有 {total} 篇",
                    severity="warning",
                )
            )

    return issues


def article_paths(root: Path, sections: tuple[str, ...]) -> list[Path]:
    paths: list[Path] = []
    for section in sections:
        paths.extend(sorted((root / "content" / section).glob("*/index.md")))
    return paths


def map_changed_paths(
    root: Path, paths: list[str], sections: tuple[str, ...]
) -> tuple[list[Path], list[Issue], set[str]]:
    selected: list[Path] = []
    issues: list[Issue] = []
    touched_sections: set[str] = set()
    seen: set[Path] = set()

    for raw in paths:
        normalized = raw.replace("\\", "/")
        parts = PurePosixPath(normalized).parts
        if not parts or parts[0] != "content" or len(parts) < 3:
            continue
        section = parts[1]
        if section not in sections:
            continue
        touched_sections.add(section)
        if len(parts) == 3 and parts[2].endswith(".md") and parts[2] != "_index.md":
            issues.append(
                Issue(
                    normalized,
                    1,
                    "file.bundle",
                    "文章必须使用 page bundle：content/<栏目>/<slug>/index.md",
                )
            )
            continue
        if len(parts) >= 4 and parts[2] != "_index.md":
            index_path = root / "content" / section / parts[2] / "index.md"
            if index_path.is_file() and index_path not in seen:
                seen.add(index_path)
                selected.append(index_path)

    return selected, issues, touched_sections


def check_paths(
    root: Path,
    paths: list[str] | None = None,
    include_drafts: bool = False,
) -> CheckResult:
    sections = load_main_sections(root)
    all_articles = [read_article(path, root) for path in article_paths(root, sections)]
    issues: list[Issue] = []
    selected: list[Path] = []
    touched_sections: set[str] = set()

    if paths:
        selected, mapping_issues, touched_sections = map_changed_paths(root, paths, sections)
        issues.extend(mapping_issues)
    else:
        selected = [article.path for article in all_articles]
        touched_sections = set(sections)

    by_path = {article.path: article for article in all_articles}
    checked = 0
    for path in selected:
        article = by_path.get(path)
        if article is None:
            article = read_article(path, root)
        if article.draft and not include_drafts:
            continue
        checked += 1
        issues.extend(check_article(article, include_drafts, dt.date.today()))

    series_articles = [article for article in all_articles if article.section in touched_sections]
    issues.extend(check_series(root, series_articles, include_drafts))

    issues.sort(key=lambda issue: (issue.path, issue.line, issue.code))
    return CheckResult(issues=issues, files=checked)


def changed_content_paths(root: Path) -> list[str]:
    def git_paths(*args: str) -> list[str]:
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

    tracked = git_paths("diff", "--name-only", "-z", "HEAD", "--", "content")
    untracked = git_paths("ls-files", "--others", "--exclude-standard", "-z", "--", "content")
    return list(dict.fromkeys(tracked + untracked))


def configure_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="博客文章格式检查")
    parser.add_argument("paths", nargs="*", help="要检查的文件或目录（默认检查全部）")
    parser.add_argument("--changed", action="store_true", help="只检查 content/ 下的改动")
    parser.add_argument("--include-drafts", action="store_true", help="同时检查草稿")
    parser.add_argument("--strict", action="store_true", help="警告也返回失败")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--root", help="仓库根目录（默认自动识别）")
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else REPO_ROOT

    paths = list(args.paths)
    if args.changed:
        paths.extend(changed_content_paths(root))
        if not paths:
            if args.json:
                print(json.dumps({"ok": True, "files": 0, "issues": []}, ensure_ascii=False))
            else:
                print("格式检查：content/ 下没有改动。")
            return 0

    result = check_paths(root, paths or None, include_drafts=args.include_drafts)

    if args.json:
        print(
            json.dumps(
                {
                    "ok": result.ok and not (args.strict and result.warnings),
                    "files": result.files,
                    "issues": [asdict(issue) for issue in result.issues],
                },
                ensure_ascii=False,
            )
        )
    else:
        for issue in result.issues:
            prefix = "错误" if issue.is_error else "警告"
            print(f"{prefix} {issue.path}:{issue.line} [{issue.code}] {issue.message}")
        print(
            f"格式检查：检查 {result.files} 篇，"
            f"{len(result.errors)} 个错误，{len(result.warnings)} 个警告。"
        )

    if result.errors:
        return 1
    if args.strict and result.warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
