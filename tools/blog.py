#!/usr/bin/env python3
"""博客文章创建与发布工具。

用法：
    python tools/blog.py new
    python tools/blog.py publish [--dry-run] [--skip-build]
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import check_format
import output_stats

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://visionjam.github.io"
ACTIONS_URL = "https://github.com/visionjam/visionjam.github.io/actions"
DEFAULT_SECTIONS = ("posts", "android-guide")

IMAGE_EXTS = {".avif", ".bmp", ".gif", ".ico", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
BINARY_EXTS = {
    ".7z",
    ".gz",
    ".mp3",
    ".mp4",
    ".mov",
    ".otf",
    ".pdf",
    ".tar",
    ".ttf",
    ".woff",
    ".woff2",
    ".zip",
}

PRIVACY_PATTERNS = [
    ("windows_path", re.compile(r"\b[A-Za-z]:[\\/]")),
    ("unc_path", re.compile(r"\\\\[A-Za-z0-9_.-]+\\[A-Za-z0-9_.$-]+")),
    ("unix_home", re.compile(r"/(?:Users|home)/[^/\s]+")),
    ("local_address", re.compile(r"\b(?:127\.0\.0\.1|localhost)\b", re.IGNORECASE)),
    ("github_token", re.compile(r"\b(?:ghp_|github_pat_)[A-Za-z0-9_]{10,}")),
    ("api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{10,}")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("phone_cn", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
]


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    text: str


@dataclass(frozen=True)
class PostInfo:
    slug: str
    index_path: Path
    title: str


def validate_slug(slug: str) -> str:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug or ""):
        raise ValueError("文件夹名只能使用英文小写字母、数字和连字符，且不能以连字符开头或结尾。")
    return slug


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return {}

    data: dict[str, str] = {}
    for line in lines[1:end]:
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
        data[key] = value
    return data


def get_title(text: str) -> str:
    return parse_frontmatter(text).get("title", "").strip()


def is_draft(text: str) -> bool:
    value = parse_frontmatter(text).get("draft", "").strip().lower()
    return value in {"true", "yes", "1"}


def set_draft(text: str, draft: bool) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("文章缺少 frontmatter。")
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        raise ValueError("文章缺少 frontmatter 结束标记。")

    value = "true" if draft else "false"
    for index in range(1, end):
        if re.match(r"^\s*draft\s*:", lines[index]):
            lines[index] = f"draft: {value}"
            break
    else:
        lines.insert(1, f"draft: {value}")

    result = "\n".join(lines)
    if text.endswith("\n"):
        result += "\n"
    return result


def render_new_post(archetype: str, title: str, date: dt.date) -> str:
    lines = archetype.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("文章模板缺少 frontmatter。")
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        raise ValueError("文章模板缺少 frontmatter 结束标记。")

    escaped = title.replace("\\", "\\\\").replace('"', '\\"')
    title_found = False
    date_found = False
    for index in range(1, end):
        if re.match(r"^\s*title\s*:", lines[index]):
            lines[index] = f'title: "{escaped}"'
            title_found = True
        elif re.match(r"^\s*date\s*:", lines[index]):
            lines[index] = f"date: {date.isoformat()}"
            date_found = True
    if not title_found or not date_found:
        raise ValueError("文章模板缺少 title 或 date 字段。")

    result = "\n".join(lines)
    if archetype.endswith("\n"):
        result += "\n"
    return result


def write_text_lf(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def create_post(root: Path, slug: str, title: str, date: dt.date) -> Path:
    validate_slug(slug)
    index_path = root / "content" / "posts" / slug / "index.md"
    if index_path.parent.exists():
        raise FileExistsError(f"文件夹已存在：{index_path.parent}")
    archetype_path = root / "archetypes" / "posts.md"
    if not archetype_path.is_file():
        raise FileNotFoundError(f"找不到模板：{archetype_path}")
    text = render_new_post(archetype_path.read_text(encoding="utf-8"), title, date)
    index_path.parent.mkdir(parents=True, exist_ok=False)
    write_text_lf(index_path, text)
    return index_path


def scan_text(text: str, path: str = "") -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for kind, pattern in PRIVACY_PATTERNS:
            if pattern.search(line):
                findings.append(Finding(path, line_number, kind, line.strip()[:160]))
    return findings


def scan_files(root: Path, paths: list[str]) -> tuple[list[Finding], list[str]]:
    findings: list[Finding] = []
    images: list[str] = []
    for relative in paths:
        full = root / relative
        if not full.is_file():
            continue
        suffix = full.suffix.lower()
        if suffix in IMAGE_EXTS:
            images.append(relative)
            if suffix != ".svg":
                continue
        if suffix in BINARY_EXTS:
            continue
        try:
            text = full.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        findings.extend(scan_text(text, relative))
    return findings, images


def main_sections(root: Path = REPO_ROOT) -> tuple[str, ...]:
    try:
        config = (root / "hugo.yml").read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_SECTIONS
    match = re.search(r"(?m)^  mainSections:\n((?:    - \S+\n?)+)", config)
    if not match:
        return DEFAULT_SECTIONS
    sections = tuple(re.findall(r"(?m)^    - (\S+)$", match.group(1)))
    return sections or DEFAULT_SECTIONS


def bundle_base(path: str, sections: tuple[str, ...] = DEFAULT_SECTIONS) -> str | None:
    parts = PurePosixPath(path.replace("\\", "/")).parts
    if len(parts) >= 4 and parts[0] == "content" and parts[1] in sections:
        slug = parts[2]
        if slug and slug != "_index.md":
            return f"content/{parts[1]}/{slug}"
    return None


def bundle_slug(path: str, sections: tuple[str, ...] = DEFAULT_SECTIONS) -> str | None:
    base = bundle_base(path, sections)
    return PurePosixPath(base).name if base else None


def filter_excluded(paths: list[str], excluded_bundles: set[str]) -> list[str]:
    result: list[str] = []
    for path in paths:
        normalized = path.replace("\\", "/")
        if any(
            normalized == bundle or normalized.startswith(bundle + "/")
            for bundle in excluded_bundles
        ):
            continue
        result.append(path)
    return result


def draft_posts(
    root: Path, paths: list[str], sections: tuple[str, ...] = DEFAULT_SECTIONS
) -> list[PostInfo]:
    seen: set[str] = set()
    result: list[PostInfo] = []
    for path in paths:
        base = bundle_base(path, sections)
        if not base or base in seen:
            continue
        seen.add(base)
        index_path = root / base / "index.md"
        if not index_path.is_file():
            continue
        text = index_path.read_text(encoding="utf-8")
        if is_draft(text):
            result.append(PostInfo(PurePosixPath(base).name, index_path, get_title(text)))
    return result


def post_titles(
    root: Path, paths: list[str], sections: tuple[str, ...] = DEFAULT_SECTIONS
) -> list[str]:
    seen: set[str] = set()
    titles: list[str] = []
    for path in paths:
        base = bundle_base(path, sections)
        if not base or base in seen:
            continue
        seen.add(base)
        index_path = root / base / "index.md"
        if not index_path.is_file():
            continue
        title = get_title(index_path.read_text(encoding="utf-8"))
        if title:
            titles.append(title)
    return titles


def build_commit_message(titles: list[str]) -> str:
    cleaned = [" ".join(title.split()) for title in titles if title and title.strip()]
    if not cleaned:
        return "post: 更新内容"
    if len(cleaned) == 1:
        return f"post: {cleaned[0]}"
    return f"post: 发布 {len(cleaned)} 篇文章"


def is_extended_version(output: str) -> bool:
    return "+extended" in output


def run_command(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


def git_paths(root: Path, *args: str) -> list[str]:
    result = run_command(["git", "-C", str(root), *args])
    if result.returncode != 0:
        return []
    return [path for path in result.stdout.split("\0") if path]


def changed_content_paths(root: Path) -> list[str]:
    tracked = git_paths(root, "diff", "--name-only", "-z", "HEAD", "--", "content")
    untracked = git_paths(
        root, "ls-files", "--others", "--exclude-standard", "-z", "--", "content"
    )
    return list(dict.fromkeys(tracked + untracked))


def hugo_build(root: Path) -> bool:
    hugo = shutil.which("hugo")
    if not hugo:
        print("未找到 Hugo，跳过本地构建（GitHub Actions 仍会构建）。")
        return True
    version = run_command([hugo, "version"])
    if version.returncode != 0 or not is_extended_version(version.stdout):
        print("本地 Hugo 不是 extended 版，跳过本地构建（GitHub Actions 仍会构建）。")
        return True
    print("本地构建检查中...")
    result = run_command([hugo, "--minify", "--gc"], cwd=root)
    if result.returncode != 0:
        print("本地构建失败：")
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return False
    print("本地构建成功。")
    return True


def ask_yes_no(prompt: str) -> bool:
    while True:
        try:
            answer = input(f"{prompt} [Y/N]: ").strip().lower()
        except EOFError:
            return False
        if answer in {"y", "yes", "是"}:
            return True
        if answer in {"n", "no", "否"}:
            return False
        print("请输入 Y 或 N。")


def revert_flips(flips: list[Path]) -> None:
    for path in flips:
        try:
            text = path.read_text(encoding="utf-8")
            write_text_lf(path, set_draft(text, True))
        except OSError as exc:
            print(f"恢复草稿状态失败：{path}（{exc}）")


def open_path(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except OSError as exc:
        print(f"无法自动打开，请手动打开：{path}（{exc}）")


def open_url(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:
        pass


def cmd_new(args: argparse.Namespace, root: Path = REPO_ROOT) -> int:
    slug = args.slug or input("文章文件夹名（英文小写/数字/连字符）: ").strip()
    title = args.title or input("文章标题: ").strip()
    if not slug or not title:
        print("文件夹名和标题都不能为空。")
        return 1
    try:
        path = create_post(root, slug, title, dt.date.today())
    except (ValueError, FileExistsError, FileNotFoundError) as exc:
        print(f"创建失败：{exc}")
        return 1
    print(f"已创建：{path.relative_to(root).as_posix()}")
    print(f"配图放：{path.parent.relative_to(root).as_posix()}/")
    print("正文中引用图片：![](图片名.png)")
    print("写完后运行发布脚本。")
    if not args.no_open:
        open_path(path)
    return 0


def refresh_publish_stats(root: Path, dry_run: bool = False) -> bool:
    root = Path(root).resolve()
    if dry_run:
        issues = output_stats.check_blog(root)
        for issue in issues:
            print(f"统计快照：{issue}")
        return True
    archive = root.parent / "zhihu-archive"
    side = (
        "both"
        if (archive / "data" / "zhihu_stats.json").is_file()
        else "blog"
    )
    try:
        counts = output_stats.refresh(
            root, archive if side == "both" else None, side
        )
    except Exception as exc:  # noqa: BLE001 - 发布前统计失败要给出明确原因
        print(f"统计快照生成失败：{exc}")
        return False
    print(
        f"统计快照：博客 {counts.get('blog', 0)} 条，"
        f"知乎 {counts.get('zhihu', 0)} 条。"
    )
    return True


def cmd_publish(args: argparse.Namespace, root: Path = REPO_ROOT) -> int:
    print("=== 发布文章 ===")
    sections = main_sections(root)
    changed = changed_content_paths(root)
    if not changed:
        print("没有发现 content/ 下的改动。")
        return 0

    drafts = draft_posts(root, changed, sections)
    excluded: set[str] = set()
    flips: list[Path] = []
    for info in drafts:
        label = info.title or info.slug
        if ask_yes_no(f"《{label}》仍是草稿，发布这篇文章吗？"):
            text = info.index_path.read_text(encoding="utf-8")
            write_text_lf(info.index_path, set_draft(text, False))
            flips.append(info.index_path)
        else:
            base = bundle_base(str(info.index_path.relative_to(root)), sections)
            if base:
                excluded.add(base)

    actionable = filter_excluded(changed, excluded)
    if not actionable:
        print("没有要发布的内容。")
        if args.dry_run:
            revert_flips(flips)
        return 0

    format_result = check_format.check_paths(root, actionable, include_drafts=True)
    if format_result.errors:
        print("格式检查未通过：")
        for issue in format_result.issues:
            prefix = "错误" if issue.is_error else "警告"
            print(f"  {prefix} {issue.path}:{issue.line} [{issue.code}] {issue.message}")
        print("请修正后再发布。")
        revert_flips(flips)
        return 1
    if format_result.warnings:
        print("格式检查警告：")
        for issue in format_result.warnings:
            print(f"  警告 {issue.path}:{issue.line} [{issue.code}] {issue.message}")
    else:
        print(f"格式检查：{format_result.files} 篇通过。")

    if not refresh_publish_stats(root, dry_run=args.dry_run):
        revert_flips(flips)
        return 1

    if not args.skip_build and not hugo_build(root):
        revert_flips(flips)
        return 1

    findings, images = scan_files(root, actionable)
    if images:
        print("本次涉及的图片（请确认不含隐私）：")
        for image in images:
            print(f"  - {image}")
    if findings:
        print("隐私扫描发现可疑内容：")
        for finding in findings:
            print(f"  {finding.path}:{finding.line} [{finding.kind}] {finding.text}")
        if not ask_yes_no("仍然继续发布吗？"):
            revert_flips(flips)
            return 1
    else:
        print("隐私扫描：未发现可疑内容。")

    titles = post_titles(root, actionable, sections)
    print("\n本次将发布：")
    for path in actionable:
        print(f"  - {path}")
    if titles:
        print("文章：" + "、".join(titles))

    if args.dry_run:
        print("\nDry run：未提交、未推送。")
        revert_flips(flips)
        return 0

    if not ask_yes_no("\n确认提交并推送到 origin main 吗？"):
        revert_flips(flips)
        return 0

    add = run_command(
        [
            "git",
            "-C",
            str(root),
            "add",
            "-A",
            "--",
            *actionable,
            "data/output_stats.json",
        ]
    )
    if add.returncode != 0:
        print("暂存失败：")
        print(add.stderr)
        revert_flips(flips)
        return 1

    message = build_commit_message(titles)
    commit = run_command(["git", "-C", str(root), "commit", "-m", message])
    if commit.returncode != 0:
        print("提交失败：")
        print(commit.stdout)
        print(commit.stderr)
        revert_flips(flips)
        return 1

    push = run_command(["git", "-C", str(root), "push", "origin", "main"])
    if push.returncode != 0:
        detail = (push.stdout + push.stderr).lower()
        if any(
            marker in detail
            for marker in (
                "non-fast-forward",
                "rejected",
                "fetch first",
                "updates were rejected",
            )
        ):
            print("远端有新提交，尝试 git pull --rebase 后重试...")
            pull = run_command(
                ["git", "-C", str(root), "pull", "--rebase", "origin", "main"]
            )
            if pull.returncode != 0:
                print("自动 rebase 失败：")
                print(pull.stdout)
                print(pull.stderr)
                print("请手动解决冲突后运行 git push origin main。")
                return 1
            push = run_command(["git", "-C", str(root), "push", "origin", "main"])
        if push.returncode != 0:
            print("推送失败：")
            print(push.stdout)
            print(push.stderr)
            print("提交已保存在本地，修复后运行 git push origin main。")
            return 1

    print("推送成功。")
    revision = run_command(["git", "-C", str(root), "rev-parse", "--short", "HEAD"])
    if revision.returncode == 0:
        print(f"提交：{revision.stdout.strip()}")

    bases: list[str] = []
    for path in actionable:
        base = bundle_base(path, sections)
        if base and base not in bases:
            bases.append(base)
    for base in bases:
        relative = PurePosixPath(base).relative_to("content").as_posix()
        print(f"文章地址：{SITE_URL}/{relative}/")
    print(f"Actions：{ACTIONS_URL}")
    print("约 1–2 分钟后上线。")
    if not args.no_open:
        open_url(ACTIONS_URL)
    return 0


def configure_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="博客文章创建与发布工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="新建一篇文章")
    new_parser.add_argument("--slug", help="文件夹名（英文小写/数字/连字符）")
    new_parser.add_argument("--title", help="文章标题")
    new_parser.add_argument("--no-open", action="store_true", help="不自动打开编辑器")

    publish_parser = subparsers.add_parser("publish", help="构建、检查并推送文章")
    publish_parser.add_argument("--dry-run", action="store_true", help="只检查，不提交不推送")
    publish_parser.add_argument("--skip-build", action="store_true", help="跳过本地 Hugo 构建")
    publish_parser.add_argument("--no-open", action="store_true", help="不自动打开浏览器")

    return parser


def main(argv: list[str] | None = None) -> int:
    configure_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "new":
        return cmd_new(args)
    if args.command == "publish":
        return cmd_publish(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
