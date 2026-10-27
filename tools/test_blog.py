import argparse
import contextlib
import datetime as dt
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blog
import check_all
import check_format
import check_privacy
import doctor
import fetch_likes
import format_hook
import series
import verify_site


def fake_windows_path() -> str:
    return "C:" + chr(92) + "Users" + chr(92) + "example"


def fake_local_address() -> str:
    return "127" + "." + "0.0.1"


def fake_phone() -> str:
    return "1" + "38" + "00000000"


def fake_github_token() -> str:
    return "ghp_" + "x" * 36


FRONTMATTER = """---
title: "示例文章"
date: 2026-10-22
draft: true
tags: []
summary: ""
---

draft: true 这行在正文里，不应被修改。
"""


ARCHETYPE = """---
title: "{{ replace .File.ContentBaseName "-" " " | title }}"
date: {{ now.Format "2006-01-02" }}
draft: true
tags: []
summary: ""
---

在这里开始写作。
"""

VALID_ARTICLE = """---
title: "测试文章"
date: 2026-10-01
draft: false
tags: ["测试"]
summary: "摘要"
---

正文。
"""

SERIES_INDEX = """---
title: "测试系列"
description: "测试系列栏目"
date: 2026-10-01
draft: false
---

| 篇 | 文章 |
| --- | --- |
| 01 | [第一篇](one/) |
| 02 | [第二篇](two/) |
"""

SERIES_ONE = """---
title: "测试系列（一）：第一篇"
date: 2026-10-01
draft: false
weight: 1
tags: ["测试"]
series: ["测试系列"]
summary: "第一篇摘要"
---

> 本文是[《测试系列》](../)系列第 1 篇，共 2 篇。
> 适合：测试。

正文一。

**系列导航**

1. **测试系列（一）：第一篇**（本篇）
2. [测试系列（二）：第二篇](../two/)

> 下一篇：[《测试系列（二）：第二篇》](../two/)。
"""

SERIES_TWO = """---
title: "测试系列（二）：第二篇"
date: 2026-10-01
draft: false
weight: 2
tags: ["测试"]
series: ["测试系列"]
summary: "第二篇摘要"
---

> 本文是[《测试系列》](../)系列第 2 篇，共 2 篇。
> 适合：测试。

正文二。

**系列导航**

1. [测试系列（一）：第一篇](../one/)
2. **测试系列（二）：第二篇**（本篇）

> 上一篇：[《测试系列（一）：第一篇》](../one/) · 本篇完。
"""


class SlugTests(unittest.TestCase):
    def test_accepts_lowercase_hyphen(self):
        self.assertEqual(blog.validate_slug("hello-world"), "hello-world")
        self.assertEqual(blog.validate_slug("2026-10-22-note"), "2026-10-22-note")

    def test_rejects_uppercase(self):
        with self.assertRaises(ValueError):
            blog.validate_slug("Hello")

    def test_rejects_spaces(self):
        with self.assertRaises(ValueError):
            blog.validate_slug("hello world")

    def test_rejects_chinese(self):
        with self.assertRaises(ValueError):
            blog.validate_slug("你好")

    def test_rejects_leading_or_trailing_hyphen(self):
        for slug in ("-hello", "hello-", "hello--world", ""):
            with self.subTest(slug=slug):
                with self.assertRaises(ValueError):
                    blog.validate_slug(slug)


class FrontmatterTests(unittest.TestCase):
    def test_reads_quoted_title(self):
        self.assertEqual(blog.get_title(FRONTMATTER), "示例文章")

    def test_reads_unquoted_title(self):
        text = "---\ntitle: Hello World\ndraft: false\n---\n"
        self.assertEqual(blog.get_title(text), "Hello World")

    def test_detects_draft(self):
        self.assertTrue(blog.is_draft(FRONTMATTER))
        self.assertFalse(blog.is_draft(FRONTMATTER.replace("draft: true", "draft: false")))

    def test_set_draft_only_changes_frontmatter(self):
        out = blog.set_draft(FRONTMATTER, False)
        self.assertIn("draft: false", out.split("---")[1])
        self.assertIn("draft: true 这行在正文里", out)
        self.assertFalse(blog.is_draft(out))

    def test_set_draft_adds_field_when_missing(self):
        text = "---\ntitle: Test\n---\nBody\n"
        out = blog.set_draft(text, False)
        self.assertTrue(out.startswith("---\ndraft: false\ntitle: Test"))

    def test_missing_frontmatter(self):
        self.assertEqual(blog.parse_frontmatter("no frontmatter"), {})
        self.assertFalse(blog.is_draft("no frontmatter"))
        with self.assertRaises(ValueError):
            blog.set_draft("no frontmatter", False)


class RenderTests(unittest.TestCase):
    def test_replaces_title_and_date(self):
        out = blog.render_new_post(ARCHETYPE, "我的文章", dt.date(2026, 10, 22))
        self.assertIn('title: "我的文章"', out)
        self.assertIn("date: 2026-10-22", out)
        self.assertIn("draft: true", out)
        self.assertIn("在这里开始写作。", out)

    def test_escapes_quotes_and_backslashes(self):
        out = blog.render_new_post(ARCHETYPE, 'He said "hi" \\ bye', dt.date(2026, 1, 2))
        self.assertIn(r'title: "He said \"hi\" \\ bye"', out)

    def test_raises_without_frontmatter(self):
        with self.assertRaises(ValueError):
            blog.render_new_post("no frontmatter", "x", dt.date(2026, 1, 1))


class CreatePostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "archetypes").mkdir()
        (self.root / "archetypes/posts.md").write_text(ARCHETYPE, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_bundle_with_title_and_date(self):
        path = blog.create_post(self.root, "hello-world", "你好", dt.date(2026, 10, 22))
        self.assertEqual(path, self.root / "content/posts/hello-world/index.md")
        text = path.read_text(encoding="utf-8")
        self.assertIn('title: "你好"', text)
        self.assertIn("date: 2026-10-22", text)
        self.assertIn("draft: true", text)

    def test_refuses_existing_folder(self):
        (self.root / "content/posts/hello-world").mkdir(parents=True)
        with self.assertRaises(FileExistsError):
            blog.create_post(self.root, "hello-world", "x", dt.date(2026, 1, 1))

    def test_refuses_invalid_slug(self):
        with self.assertRaises(ValueError):
            blog.create_post(self.root, "Hello World", "x", dt.date(2026, 1, 1))


class PrivacyTests(unittest.TestCase):
    def test_detects_windows_path(self):
        findings = blog.scan_text(f"path is {fake_windows_path()}", "post.md")
        self.assertTrue(any(f.kind == "windows_path" for f in findings))

    def test_detects_local_address(self):
        findings = blog.scan_text(f"proxy {fake_local_address()}", "post.md")
        self.assertTrue(any(f.kind == "local_address" for f in findings))

    def test_detects_github_token(self):
        findings = blog.scan_text(f"token {fake_github_token()}", "post.md")
        self.assertTrue(any(f.kind == "github_token" for f in findings))

    def test_detects_phone(self):
        findings = blog.scan_text(f"电话 {fake_phone()}", "post.md")
        self.assertTrue(any(f.kind == "phone_cn" for f in findings))

    def test_reports_line_numbers(self):
        findings = blog.scan_text("clean\n" + fake_windows_path(), "post.md")
        self.assertEqual(findings[0].line, 2)

    def test_clean_text_has_no_findings(self):
        self.assertEqual(blog.scan_text("普通的文章内容。\n没有敏感信息。", "post.md"), [])

    def test_scan_files_reports_images_separately(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "post.md").write_text(fake_windows_path(), encoding="utf-8")
            (root / "cover.png").write_bytes(b"\x89PNG\r\n")
            findings, images = blog.scan_files(root, ["post.md", "cover.png"])
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].path, "post.md")
            self.assertEqual(images, ["cover.png"])


class BundleTests(unittest.TestCase):
    def test_extracts_slug(self):
        self.assertEqual(blog.bundle_slug("content/posts/hello-world/index.md"), "hello-world")
        self.assertEqual(blog.bundle_slug("content/posts/hello-world/cover.png"), "hello-world")

    def test_ignores_non_bundle_paths(self):
        self.assertIsNone(blog.bundle_slug("content/posts/_index.md"))
        self.assertIsNone(blog.bundle_slug("content/about.md"))
        self.assertIsNone(blog.bundle_slug("hugo.yml"))

    def test_filters_excluded_bundles(self):
        paths = [
            "content/posts/a/index.md",
            "content/posts/a/cover.png",
            "content/posts/b/index.md",
        ]
        self.assertEqual(
            blog.filter_excluded(paths, {"content/posts/a"}),
            ["content/posts/b/index.md"],
        )

    def test_handles_android_guide_bundles(self):
        path = "content/android-guide/01-topic/index.md"
        self.assertEqual(blog.bundle_slug(path), "01-topic")
        self.assertEqual(blog.bundle_base(path), "content/android-guide/01-topic")
        self.assertEqual(
            blog.filter_excluded([path], {"content/android-guide/01-topic"}),
            [],
        )


class FormatCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "hugo.yml").write_text(
            "params:\n  mainSections:\n    - posts\n    - android-guide\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def make_series(self):
        self.write("content/android-guide/_index.md", SERIES_INDEX)
        self.write("content/android-guide/one/index.md", SERIES_ONE)
        self.write("content/android-guide/two/index.md", SERIES_TWO)

    def codes(self, result):
        return {issue.code for issue in result.issues}

    def test_valid_article_passes(self):
        self.write("content/posts/hello/index.md", VALID_ARTICLE)
        result = check_format.check_paths(self.root)
        self.assertTrue(result.ok, result.issues)
        self.assertEqual(result.files, 1)

    def test_published_article_requires_summary(self):
        self.write(
            "content/posts/hello/index.md",
            VALID_ARTICLE.replace('summary: "摘要"', 'summary: ""'),
        )
        result = check_format.check_paths(self.root)
        self.assertIn("frontmatter.summary", self.codes(result))

    def test_published_article_requires_tags(self):
        self.write(
            "content/posts/hello/index.md",
            VALID_ARTICLE.replace('tags: ["测试"]', "tags: []"),
        )
        result = check_format.check_paths(self.root)
        self.assertIn("frontmatter.tags_empty", self.codes(result))

    def test_draft_is_skipped_by_default(self):
        self.write(
            "content/posts/hello/index.md",
            VALID_ARTICLE.replace("draft: false", "draft: true").replace(
                'summary: "摘要"', 'summary: ""'
            ),
        )
        self.assertEqual(check_format.check_paths(self.root).files, 0)
        result = check_format.check_paths(self.root, include_drafts=True)
        self.assertTrue(result.ok, result.issues)
        self.assertEqual(result.files, 1)

    def test_bad_date_fails(self):
        self.write(
            "content/posts/hello/index.md",
            VALID_ARTICLE.replace("date: 2026-10-01", "date: 2026/10/01"),
        )
        result = check_format.check_paths(self.root)
        self.assertIn("frontmatter.date", self.codes(result))

    def test_body_h1_fails(self):
        self.write(
            "content/posts/hello/index.md",
            VALID_ARTICLE + "\n# 一级标题\n",
        )
        result = check_format.check_paths(self.root)
        self.assertIn("body.h1", self.codes(result))

    def test_unclosed_code_fence_fails(self):
        self.write(
            "content/posts/hello/index.md",
            VALID_ARTICLE + "\n```bash\necho hi\n",
        )
        result = check_format.check_paths(self.root)
        self.assertIn("body.code_fence", self.codes(result))

    def test_missing_image_fails(self):
        self.write(
            "content/posts/hello/index.md",
            VALID_ARTICLE + "\n![图](missing.png)\n",
        )
        result = check_format.check_paths(self.root)
        self.assertIn("body.image_missing", self.codes(result))

    def test_missing_relative_link_fails(self):
        self.write(
            "content/posts/hello/index.md",
            VALID_ARTICLE + "\n[链接](../not-found/)\n",
        )
        result = check_format.check_paths(self.root)
        self.assertIn("body.link_missing", self.codes(result))

    def test_flat_markdown_must_be_a_bundle(self):
        self.write("content/posts/flat.md", VALID_ARTICLE)
        result = check_format.check_paths(self.root, ["content/posts/flat.md"])
        self.assertIn("file.bundle", self.codes(result))

    def test_changed_image_checks_its_bundle(self):
        self.write("content/posts/hello/index.md", VALID_ARTICLE)
        (self.root / "content/posts/hello/cover.png").write_bytes(b"\x89PNG\r\n")
        result = check_format.check_paths(self.root, ["content/posts/hello/cover.png"])
        self.assertEqual(result.files, 1)

    def test_valid_series_passes(self):
        self.make_series()
        result = check_format.check_paths(self.root)
        self.assertTrue(result.ok, result.issues)

    def test_series_requires_bottom_nav(self):
        self.make_series()
        self.write(
            "content/android-guide/one/index.md",
            SERIES_ONE.replace("**系列导航**", "没有导航"),
        )
        result = check_format.check_paths(self.root)
        self.assertIn("series.bottom_nav", self.codes(result))

    def test_series_total_mismatch_fails(self):
        self.make_series()
        self.write(
            "content/android-guide/one/index.md",
            SERIES_ONE.replace("共 2 篇", "共 3 篇"),
        )
        result = check_format.check_paths(self.root)
        self.assertIn("series.top_nav_total", self.codes(result))

    def test_series_index_must_link_all_articles(self):
        self.make_series()
        self.write(
            "content/android-guide/_index.md",
            SERIES_INDEX.replace("| 02 | [第二篇](two/) |\n", ""),
        )
        result = check_format.check_paths(self.root)
        self.assertIn("series.index_link", self.codes(result))

    def test_series_duplicate_weight_fails(self):
        self.make_series()
        self.write(
            "content/android-guide/two/index.md",
            SERIES_TWO.replace("weight: 2", "weight: 1"),
        )
        result = check_format.check_paths(self.root)
        self.assertIn("series.weight_duplicate", self.codes(result))


class FormatHookTests(unittest.TestCase):
    def test_recognizes_publish_commands(self):
        for command in (
            "python tools/blog.py publish",
            "py -3 tools\\blog.py publish --dry-run",
            "./publish.sh",
            "publish.bat",
            "git push origin main",
            "git -C repo push origin main",
        ):
            self.assertTrue(format_hook.is_publish_command(command), command)

    def test_ignores_regular_commands(self):
        for command in ("git status", "hugo --minify", "python tools/check_format.py"):
            self.assertFalse(format_hook.is_publish_command(command), command)

    def test_reads_command_from_stdin(self):
        payload = json.dumps({"tool_input": {"command": "git push"}})
        self.assertEqual(format_hook.read_command(io.StringIO(payload)), "git push")

    def test_direct_push_is_global_check(self):
        self.assertTrue(format_hook.is_direct_push("git push origin main"))
        self.assertTrue(format_hook.is_direct_push("git -C repo push origin main"))
        self.assertFalse(format_hook.is_direct_push("python tools/blog.py publish"))

    def test_is_content_path(self):
        root = Path(tempfile.mkdtemp())
        try:
            path = root / "content/posts/one/index.md"
            path.parent.mkdir(parents=True)
            path.write_text("x", encoding="utf-8")
            self.assertTrue(format_hook.is_content_path(str(path), root))
            self.assertFalse(format_hook.is_content_path(str(root / "tools/x.py"), root))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_post_write_check_blocks_errors(self):
        root = Path(tempfile.mkdtemp())
        try:
            path = root / "content/posts/one/index.md"
            path.parent.mkdir(parents=True)
            path.write_text("x", encoding="utf-8")
            fake = subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout=json.dumps(
                    {
                        "issues": [
                            {
                                "path": "content/posts/one/index.md",
                                "line": 1,
                                "code": "frontmatter.summary",
                                "message": "缺少摘要",
                                "severity": "error",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                stderr="",
            )
            with mock.patch.object(format_hook, "ROOT", root), mock.patch.object(
                format_hook, "run_check", return_value=fake
            ):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    format_hook.post_write_check({"tool_input": {"file_path": str(path)}})
            self.assertIn('"decision": "block"', output.getvalue())
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_post_write_check_ignores_non_content(self):
        root = Path(tempfile.mkdtemp())
        try:
            with mock.patch.object(format_hook, "ROOT", root), mock.patch.object(
                format_hook, "run_check"
            ) as run:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    format_hook.post_write_check(
                        {"tool_input": {"file_path": str(root / "tools/x.py")}}
                    )
            self.assertEqual(output.getvalue(), "")
            run.assert_not_called()
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_settings_declare_both_hooks(self):
        settings = Path(__file__).resolve().parents[1] / ".claude/settings.json"
        data = json.loads(settings.read_text(encoding="utf-8"))
        hooks = data["hooks"]
        self.assertIn("PreToolUse", hooks)
        self.assertIn("PostToolUse", hooks)
        commands = [
            hook["command"]
            for entries in hooks.values()
            for entry in entries
            for hook in entry["hooks"]
        ]
        self.assertTrue(any("format_hook.py" in command for command in commands))


class SeriesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "hugo.yml").write_text(
            "params:\n  mainSections:\n    - android-guide\n", encoding="utf-8"
        )
        section = self.root / "content" / "android-guide"
        section.mkdir(parents=True)
        (section / "_index.md").write_text(
            """---
title: "测试系列"
description: "测试系列栏目"
date: 2026-10-01
draft: false
---

| 篇 | 文章 | 内容 | 适合 |
| --- | --- | --- | --- |
| 01 | [第一篇](one/) | 内容一 | 所有人 |
| 02 | [第二篇](two/) | 内容二 | 所有人 |
""",
            encoding="utf-8",
        )
        (section / "one").mkdir()
        (section / "one" / "index.md").write_text(SERIES_ONE, encoding="utf-8")
        (section / "two").mkdir()
        (section / "two" / "index.md").write_text(SERIES_TWO, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_sync_is_idempotent(self):
        changed, errors = series.sync(self.root)
        self.assertEqual(changed, [])
        self.assertEqual(errors, [])

    def test_sync_fixes_total_and_missing_link(self):
        path = self.root / "content/android-guide/one/index.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("共 2 篇", "共 9 篇")
        text = text.replace(
            "2. [测试系列（二）：第二篇](../two/)", "2. 测试系列（二）：第二篇"
        )
        path.write_text(text, encoding="utf-8")
        changed, _ = series.sync(self.root, write=True)
        self.assertIn("content/android-guide/one/index.md", changed)
        updated = path.read_text(encoding="utf-8")
        self.assertIn("共 2 篇", updated)
        self.assertIn("../two/", updated)
        self.assertEqual(series.sync(self.root)[0], [])

    def test_new_creates_third_and_updates_existing(self):
        path = series.new_article(
            self.root,
            "android-guide",
            "three",
            "第三篇",
            dt.date(2026, 10, 26),
            ["Android"],
            published=False,
        )
        self.assertTrue(path.is_file())
        article = check_format.read_article(path, self.root)
        self.assertIn("（三）", article.fields["title"][0])
        self.assertEqual(article.fields["weight"][0], "3")
        self.assertEqual(article.fields["series"][0], '["测试系列"]')
        one = (self.root / "content/android-guide/one/index.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("../three/", one)
        self.assertIn("共 3 篇", one)
        index = (self.root / "content/android-guide/_index.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("(three/)", index)
        self.assertIn("[第一篇](one/)", index)
        self.assertEqual(series.sync(self.root)[0], [])
        result = check_format.check_paths(self.root, include_drafts=True)
        self.assertTrue(result.ok, result.issues)

    def test_cn_numeral(self):
        self.assertEqual(series.cn_numeral(1), "一")
        self.assertEqual(series.cn_numeral(10), "十")
        self.assertEqual(series.cn_numeral(11), "十一")
        self.assertEqual(series.cn_numeral(20), "二十")
        self.assertEqual(series.cn_numeral(35), "三十五")


class PrivacyScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", str(self.root)], check=True, capture_output=True)
        (self.root / "README.md").write_text(
            "预览 http://local" + "host:1313\n", encoding="utf-8"
        )
        (self.root / "tools").mkdir()
        (self.root / "tools/foo.py").write_text(
            'path = "' + fake_windows_path() + '"\n', encoding="utf-8"
        )
        (self.root / "content/posts/ok").mkdir(parents=True)
        (self.root / "content/posts/ok/index.md").write_text(
            "普通正文。\n", encoding="utf-8"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_scans_tools_and_allowlists_readme(self):
        findings = check_privacy.scan_repo(self.root)
        paths = {finding.path for finding in findings}
        self.assertIn("tools/foo.py", paths)
        self.assertNotIn("README.md", paths)

    def test_changed_scan_includes_untracked(self):
        findings = check_privacy.scan_repo(self.root, changed=True)
        self.assertIn("tools/foo.py", {finding.path for finding in findings})


class CheckAllTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "hugo.yml").write_text(
            'baseURL: "https://example.com/"\n'
            "params:\n  mainSections:\n    - posts\n"
            '  giscus:\n    categoryId: "x"\n',
            encoding="utf-8",
        )
        (self.root / "content/posts/one").mkdir(parents=True)
        (self.root / "content/posts/one/index.md").write_text(
            VALID_ARTICLE, encoding="utf-8"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_target_path_resolves(self):
        public = self.root / "public"
        (public / "posts/one").mkdir(parents=True)
        (public / "posts/one/index.html").write_text("ok", encoding="utf-8")
        (public / "index.html").write_text("ok", encoding="utf-8")
        target = check_all.target_path(
            public, public / "index.html", "/posts/one/#top"
        )
        self.assertIsNotNone(target)
        self.assertTrue(target.is_file())
        self.assertIsNone(
            check_all.target_path(
                public, public / "index.html", "https://example.org/"
            )
        )
        self.assertIsNone(
            check_all.target_path(public, public / "index.html", "/zhihu-archive/")
        )

    def test_check_links_reports_missing(self):
        public = self.root / "public"
        public.mkdir()
        (public / "index.html").write_text(
            '<a href="/missing/">x</a>', encoding="utf-8"
        )
        summary = check_all.Summary()
        check_all.check_links(self.root, summary)
        self.assertTrue(any("/missing/" in error for error in summary.errors))

    def test_search_index_missing_article(self):
        public = self.root / "public"
        public.mkdir()
        (public / "index.json").write_text("[]", encoding="utf-8")
        summary = check_all.Summary()
        articles = check_all.published_articles(self.root)
        check_all.check_search_index(self.root, articles, summary)
        self.assertTrue(any("/posts/one/" in error for error in summary.errors))

    def test_article_page_checks_layout(self):
        public = self.root / "public"
        page = public / "posts/one/index.html"
        page.parent.mkdir(parents=True)
        page.write_text("站内赞 giscus.app 字 · 约", encoding="utf-8")
        summary = check_all.Summary()
        articles = check_all.published_articles(self.root)
        check_all.check_article_pages(self.root, articles, summary)
        self.assertEqual(summary.errors, [])

    def test_build_site_cleans_public(self):
        public = self.root / "public"
        public.mkdir()
        stale = public / "stale.html"
        stale.write_text("stale", encoding="utf-8")
        with mock.patch(
            "check_all.shutil.which", return_value="/usr/bin/hugo"
        ), mock.patch("check_all.blog.hugo_build", return_value=True):
            self.assertTrue(check_all.build_site(self.root, check_all.Summary()))
        self.assertFalse(stale.exists())


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "hugo.yml").write_text(
            "params:\n  mainSections:\n    - posts\n", encoding="utf-8"
        )
        (self.root / "content/posts/one").mkdir(parents=True)
        (self.root / "content/posts/one/index.md").write_text(
            VALID_ARTICLE, encoding="utf-8"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_pinned_missing_article(self):
        (self.root / "data").mkdir()
        (self.root / "data/pinned.yml").write_text(
            'items:\n  - title: "x"\n    url: "/posts/ghost/"\n',
            encoding="utf-8",
        )
        messages = [item.message for item in doctor.check_pinned(self.root)]
        self.assertTrue(any("ghost" in message for message in messages))

    def test_likes_orphan(self):
        (self.root / "data").mkdir()
        (self.root / "data/likes.json").write_text(
            '{"items": {"/posts/ghost/": {"likes": 1}}}', encoding="utf-8"
        )
        messages = [item.message for item in doctor.check_likes(self.root)]
        self.assertTrue(any("ghost" in message for message in messages))

    def test_sections_missing(self):
        self.assertEqual(doctor.check_sections(self.root), [])
        (self.root / "hugo.yml").write_text(
            "params:\n  mainSections:\n    - nope\n", encoding="utf-8"
        )
        self.assertTrue(doctor.check_sections(self.root))


class VerifySiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "hugo.yml").write_text(
            "params:\n  mainSections:\n    - posts\n", encoding="utf-8"
        )
        (self.root / "content/posts/one").mkdir(parents=True)
        (self.root / "content/posts/one/index.md").write_text(
            VALID_ARTICLE, encoding="utf-8"
        )
        (self.root / "content/posts/draft").mkdir()
        (self.root / "content/posts/draft/index.md").write_text(
            VALID_ARTICLE.replace("draft: false", "draft: true"), encoding="utf-8"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_site_paths(self):
        paths = verify_site.site_paths(self.root)
        self.assertIn("/", paths)
        self.assertIn("/index.json", paths)
        self.assertIn("/posts/one/", paths)
        self.assertNotIn("/posts/draft/", paths)


class DraftPostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "content/posts/draft-one").mkdir(parents=True)
        (self.root / "content/posts/published").mkdir(parents=True)
        (self.root / "content/posts/draft-one/index.md").write_text(
            "---\ntitle: Draft One\ndraft: true\n---\n", encoding="utf-8"
        )
        (self.root / "content/posts/published/index.md").write_text(
            "---\ntitle: Published\ndraft: false\n---\n", encoding="utf-8"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_detects_draft_bundle_from_image_change(self):
        posts = blog.draft_posts(self.root, ["content/posts/draft-one/cover.png"])
        self.assertEqual([p.slug for p in posts], ["draft-one"])
        self.assertEqual(posts[0].title, "Draft One")

    def test_ignores_published_posts(self):
        posts = blog.draft_posts(self.root, ["content/posts/published/index.md"])
        self.assertEqual(posts, [])

    def test_ignores_posts_index(self):
        posts = blog.draft_posts(self.root, ["content/posts/_index.md"])
        self.assertEqual(posts, [])

    def test_collects_titles_once(self):
        titles = blog.post_titles(
            self.root,
            [
                "content/posts/draft-one/cover.png",
                "content/posts/draft-one/index.md",
                "content/posts/published/index.md",
            ],
        )
        self.assertEqual(titles, ["Draft One", "Published"])


class CommitMessageTests(unittest.TestCase):
    def test_single_title(self):
        self.assertEqual(blog.build_commit_message(["我的文章"]), "post: 我的文章")

    def test_multiple_titles(self):
        self.assertEqual(blog.build_commit_message(["A", "B"]), "post: 发布 2 篇文章")

    def test_no_titles(self):
        self.assertEqual(blog.build_commit_message([]), "post: 更新内容")


class HugoVersionTests(unittest.TestCase):
    def test_extended(self):
        self.assertTrue(
            blog.is_extended_version("hugo v0.168.0+extended windows/amd64 BuildDate=...")
        )

    def test_standard(self):
        self.assertFalse(
            blog.is_extended_version("hugo v0.168.0 windows/amd64 BuildDate=...")
        )


class ChangedPathsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.git("init")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        post = self.root / "content/posts/foo/index.md"
        post.parent.mkdir(parents=True)
        post.write_text("---\ntitle: Foo\ndraft: false\n---\n", encoding="utf-8")
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-m", "init")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def test_finds_modified_and_untracked(self):
        post = self.root / "content/posts/foo/index.md"
        post.write_text(
            post.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8"
        )
        (self.root / "content/posts/foo/cover.png").write_bytes(b"\x89PNG\r\n")
        paths = blog.changed_content_paths(self.root)
        self.assertIn("content/posts/foo/index.md", paths)
        self.assertIn("content/posts/foo/cover.png", paths)

    def test_returns_empty_when_clean(self):
        self.assertEqual(blog.changed_content_paths(self.root), [])


class NewCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "archetypes").mkdir()
        (self.root / "archetypes/posts.md").write_text(ARCHETYPE, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_post(self):
        args = argparse.Namespace(slug="hello-world", title="Hello", no_open=True)
        with contextlib.redirect_stdout(io.StringIO()):
            code = blog.cmd_new(args, root=self.root)
        self.assertEqual(code, 0)
        self.assertTrue((self.root / "content/posts/hello-world/index.md").is_file())


class HugoBuildTests(unittest.TestCase):
    def test_skips_when_hugo_missing(self):
        with mock.patch("blog.shutil.which", return_value=None):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(blog.hugo_build(Path(".")))


class PublishFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "repo"
        self.remote = base / "remote.git"
        self.root.mkdir()
        subprocess.run(
            ["git", "init", "--bare", str(self.remote)],
            check=True,
            capture_output=True,
        )
        self.git("init")
        self.git("symbolic-ref", "HEAD", "refs/heads/main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "commit.gpgsign", "false")
        self.git("remote", "add", "origin", str(self.remote))
        (self.root / "archetypes").mkdir()
        (self.root / "archetypes/posts.md").write_text(ARCHETYPE, encoding="utf-8")
        (self.root / "content/posts/hello").mkdir(parents=True)
        (self.root / "content/posts/hello/index.md").write_text(
            "---\ntitle: Hello\ndraft: false\n---\n\nold\n", encoding="utf-8"
        )
        (self.root / "content/android-guide/guide-one").mkdir(parents=True)
        (self.root / "content/android-guide/guide-one/index.md").write_text(
            '---\ntitle: Guide One\ndate: 2026-10-01\ndraft: false\n'
            'tags: ["测试"]\nsummary: "摘要"\n---\n\nold\n',
            encoding="utf-8",
        )
        self.git("add", ".")
        self.git("commit", "-m", "init")
        self.git("push", "-u", "origin", "main")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def args(self, **overrides):
        values = {"dry_run": False, "skip_build": True, "no_open": True}
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_publishes_draft_end_to_end(self):
        draft = self.root / "content/posts/hello/index.md"
        draft.write_text(
            '---\ntitle: Hello\ndate: 2026-10-01\ntags: ["测试"]\n'
            'summary: "摘要"\ndraft: true\n---\n\nnew\n',
            encoding="utf-8",
        )
        with mock.patch("blog.ask_yes_no", return_value=True):
            with contextlib.redirect_stdout(io.StringIO()):
                code = blog.cmd_publish(self.args(), root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("draft: false", draft.read_text(encoding="utf-8"))
        self.assertEqual(self.git("log", "-1", "--format=%s").stdout.strip(), "post: Hello")
        remote_file = subprocess.run(
            [
                "git",
                "--git-dir",
                str(self.remote),
                "show",
                "main:content/posts/hello/index.md",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertIn("draft: false", remote_file.stdout)

    def test_publishes_android_guide_draft(self):
        draft = self.root / "content/android-guide/guide-one/index.md"
        draft.write_text(
            '---\ntitle: Guide One\ndate: 2026-10-01\ntags: ["测试"]\n'
            'summary: "摘要"\ndraft: true\n---\n\nnew\n',
            encoding="utf-8",
        )
        with mock.patch("blog.ask_yes_no", return_value=True):
            with contextlib.redirect_stdout(io.StringIO()):
                code = blog.cmd_publish(self.args(), root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("draft: false", draft.read_text(encoding="utf-8"))
        self.assertEqual(self.git("log", "-1", "--format=%s").stdout.strip(), "post: Guide One")
        remote_file = subprocess.run(
            [
                "git",
                "--git-dir",
                str(self.remote),
                "show",
                "main:content/android-guide/guide-one/index.md",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertIn("draft: false", remote_file.stdout)

    def test_format_error_aborts_and_reverts_draft(self):
        draft = self.root / "content/posts/hello/index.md"
        draft.write_text(
            '---\ntitle: Hello\ntags: ["测试"]\nsummary: "摘要"\n'
            "draft: true\n---\n\nnew\n",
            encoding="utf-8",
        )
        before = self.git("rev-parse", "HEAD").stdout.strip()
        with mock.patch("blog.ask_yes_no", return_value=True):
            with contextlib.redirect_stdout(io.StringIO()):
                code = blog.cmd_publish(self.args(), root=self.root)
        self.assertEqual(code, 1)
        self.assertIn("draft: true", draft.read_text(encoding="utf-8"))
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), before)

    def test_declined_draft_is_not_committed(self):
        draft = self.root / "content/posts/hello/index.md"
        draft.write_text(
            '---\ntitle: Hello\ndate: 2026-10-01\ntags: ["测试"]\n'
            'summary: "摘要"\ndraft: true\n---\n\nnew\n',
            encoding="utf-8",
        )
        before = self.git("rev-parse", "HEAD").stdout.strip()
        with mock.patch("blog.ask_yes_no", return_value=False):
            with contextlib.redirect_stdout(io.StringIO()):
                code = blog.cmd_publish(self.args(), root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("draft: true", draft.read_text(encoding="utf-8"))
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), before)

    def test_privacy_abort_reverts_draft_and_skips_commit(self):
        local = "127" + "." + "0.0.1"
        draft = self.root / "content/posts/hello/index.md"
        draft.write_text(
            '---\ntitle: Hello\ndate: 2026-10-01\ntags: ["测试"]\n'
            f'summary: "摘要"\ndraft: true\n---\n\n{local}\n',
            encoding="utf-8",
        )
        before = self.git("rev-parse", "HEAD").stdout.strip()
        with mock.patch("blog.ask_yes_no", side_effect=[True, False]):
            with contextlib.redirect_stdout(io.StringIO()):
                code = blog.cmd_publish(self.args(), root=self.root)
        self.assertEqual(code, 1)
        self.assertIn("draft: true", draft.read_text(encoding="utf-8"))
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), before)


class FetchLikesTests(unittest.TestCase):
    def test_extract_likes_reads_thumbs_up_only(self):
        nodes = [
            {
                "title": "/posts/a/",
                "url": "https://github.com/o/r/discussions/1",
                "reactionGroups": [
                    {"content": "THUMBS_UP", "users": {"totalCount": 3}},
                    {"content": "HEART", "users": {"totalCount": 9}},
                ],
            }
        ]
        self.assertEqual(
            fetch_likes.extract_likes(nodes),
            {
                "/posts/a/": {
                    "likes": 3,
                    "url": "https://github.com/o/r/discussions/1",
                }
            },
        )

    def test_discussion_key_extracts_trailing_path(self):
        self.assertEqual(fetch_likes.discussion_key("/posts/hello-world/"), "/posts/hello-world/")
        self.assertEqual(
            fetch_likes.discussion_key("Comments for /posts/hello-world/"),
            "/posts/hello-world/",
        )
        self.assertEqual(
            fetch_likes.discussion_key("https://example.com/posts/hello-world/"),
            "/posts/hello-world/",
        )
        self.assertEqual(
            fetch_likes.discussion_key("posts/hello-world/"),
            "/posts/hello-world/",
        )

    def test_collect_paginates(self):
        pages = [
            {
                "data": {
                    "repository": {
                        "discussions": {
                            "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                            "nodes": [{"title": "/posts/a/", "reactionGroups": []}],
                        }
                    }
                }
            },
            {
                "data": {
                    "repository": {
                        "discussions": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [{"title": "/posts/b/", "reactionGroups": []}],
                        }
                    }
                }
            },
        ]
        calls = []

        def opener(query, variables, token):
            calls.append(variables)
            return pages[len(calls) - 1]

        items = fetch_likes.collect("o", "r", "t", opener=opener)
        self.assertEqual(set(items), {"/posts/a/", "/posts/b/"})
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["cursor"], None)
        self.assertEqual(calls[1]["cursor"], "c1")

    def test_main_without_token_keeps_existing_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "likes.json"
            path.write_text('{"items": {"x": {"likes": 1}}}', encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = fetch_likes.main(["--output", str(path)], env={})
            self.assertEqual(code, 0)
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"items": {"x": {"likes": 1}}},
            )

    def test_main_api_failure_keeps_existing_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "likes.json"
            path.write_text('{"items": {"x": {"likes": 1}}}', encoding="utf-8")
            with mock.patch.object(
                fetch_likes, "collect", side_effect=RuntimeError("boom")
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = fetch_likes.main(
                        ["--output", str(path), "--owner", "o", "--repo", "r"],
                        env={"GITHUB_TOKEN": "t"},
                    )
            self.assertEqual(code, 0)
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"items": {"x": {"likes": 1}}},
            )

    def test_main_writes_items(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "likes.json"
            with mock.patch.object(
                fetch_likes,
                "collect",
                return_value={"/posts/a/": {"likes": 2, "url": "u"}},
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = fetch_likes.main(
                        ["--output", str(path), "--owner", "o", "--repo", "r"],
                        env={"GITHUB_TOKEN": "t"},
                    )
            self.assertEqual(code, 0)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["items"]["/posts/a/"]["likes"], 2)


class SiteBuildTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    @classmethod
    def setUpClass(cls):
        if shutil.which("hugo") is None:
            raise unittest.SkipTest("未安装 hugo")

    @classmethod
    def build(cls, destination):
        subprocess.run(
            [
                "hugo",
                "--source",
                str(cls.root),
                "--destination",
                str(destination),
                "--quiet",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def expected_main_section_count(self):
        """按 hugo.yml 的 mainSections 统计当前内容页数。"""
        config = (self.root / "hugo.yml").read_text(encoding="utf-8")
        match = re.search(r"(?m)^  mainSections:\n((?:    - \S+\n?)+)", config)
        if not match:
            self.fail("hugo.yml 缺少 mainSections")
        sections = re.findall(r"(?m)^    - (\S+)$", match.group(1))
        # draft: true 不进入生产构建，也不应计入首页统计。
        count = 0
        for section in sections:
            for index in (self.root / "content" / section).glob("*/index.md"):
                if not blog.is_draft(index.read_text(encoding="utf-8")):
                    count += 1
        return count

    def test_about_page_has_common_links_and_contributions(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build(Path(tmp) / "public")
            about = (Path(tmp) / "public" / "about" / "index.html").read_text(
                encoding="utf-8"
            )
        for needle in (
            "GitHub",
            "知乎",
            "Gmail",
            "QQ",
            "博客",
            "归档站",
            "博客源码",
            "归档站源码",
            "RSS",
            "GitHub 贡献",
        ):
            self.assertIn(needle, about)
        self.assertIn("github.com/visionjam/visionjam.github.io", about)
        self.assertIn("github.com/visionjam/zhihu-archive", about)

    def test_rss_excludes_undated_pages_and_sets_last_build_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build(Path(tmp) / "public")
            rss = (Path(tmp) / "public" / "index.xml").read_text(encoding="utf-8")
        self.assertNotIn("<title>关于</title>", rss)
        self.assertNotIn("0001-01-01", rss)
        self.assertIn("<lastBuildDate>", rss)
        self.assertEqual(rss.count("<item>"), self.expected_main_section_count())

    def test_android_guide_article_has_meta_and_comments(self):
        bundle = self.root / "content" / "android-guide" / "_sitetest-android"
        bundle.mkdir(parents=True)
        (bundle / "index.md").write_text(
            '---\ntitle: "SITETEST-ANDROID"\ndate: 2026-10-20\ndraft: false\n'
            'tags: ["测试"]\nsummary: "测试摘要"\n---\n\n一二三四五六七八九十\n',
            encoding="utf-8",
        )
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self.build(Path(tmp) / "public")
                page = (
                    Path(tmp)
                    / "public"
                    / "android-guide"
                    / "_sitetest-android"
                    / "index.html"
                ).read_text(encoding="utf-8")

            self.assertIn("10 字", page)
            self.assertIn("约 1 分钟", page)
            self.assertIn("站内赞 0", page)
            self.assertIn("giscus.app", page)
            self.assertIn("点赞与评论", page)
        finally:
            shutil.rmtree(bundle, ignore_errors=True)

    def test_home_caps_latest_posts_and_links_to_all(self):
        created = []
        try:
            for i in range(21):
                bundle = self.root / "content" / "posts" / f"_sitetest-{i:02d}"
                bundle.mkdir(parents=True)
                if i == 0:
                    title = "SITETEST-OLDEST"
                elif i == 20:
                    title = "SITETEST-NEWEST"
                else:
                    title = f"SITETEST-{i:02d}"
                (bundle / "index.md").write_text(
                    f'---\ntitle: "{title}"\n'
                    f"date: 2026-10-22T{i + 1:02d}:00:00+08:00\n"
                    "draft: false\n---\n\n正文\n",
                    encoding="utf-8",
                )
                created.append(bundle)

            with tempfile.TemporaryDirectory() as tmp:
                self.build(Path(tmp) / "public")
                home = (Path(tmp) / "public" / "index.html").read_text(
                    encoding="utf-8"
                )

            self.assertEqual(home.count('class="post-entry"'), 20)
            self.assertIn("SITETEST-NEWEST", home)
            self.assertNotIn("SITETEST-OLDEST", home)
            self.assertIn("查看全部文章", home)
            self.assertIn('href="/posts/"', home)
            self.assertNotIn("type-tabs", home)
        finally:
            for bundle in reversed(created):
                shutil.rmtree(bundle, ignore_errors=True)

    def test_stats_meta_site_band_and_ranking(self):
        created = []
        likes_path = self.root / "data" / "likes.json"
        backup = likes_path.read_bytes() if likes_path.exists() else None
        try:
            for slug, title, body, day, tags in (
                (
                    "_stats-a",
                    "TABTEST-LIKE-A",
                    "一二三四五六七八九十",
                    "2026-10-21",
                    ["测试A"],
                ),
                (
                    "_stats-b",
                    "TABTEST-LIKE-B",
                    "一二三四五",
                    "2026-10-20",
                    ["测试B"],
                ),
                ("_stats-c", "TABTEST-LIKE-C", "一二", "2026-10-19", []),
            ):
                bundle = self.root / "content" / "posts" / slug
                bundle.mkdir(parents=True)
                tags_line = (
                    "tags: " + json.dumps(tags, ensure_ascii=False) + "\n"
                    if tags
                    else ""
                )
                (bundle / "index.md").write_text(
                    f'---\ntitle: "{title}"\ndate: {day}\ndraft: false\n'
                    f"{tags_line}---\n\n{body}\n",
                    encoding="utf-8",
                )
                created.append(bundle)
            likes_path.parent.mkdir(parents=True, exist_ok=True)
            likes_path.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-01-01T00:00:00+00:00",
                        "items": {
                            "/posts/_stats-a/": {"likes": 5, "url": ""},
                            "/posts/_stats-b/": {"likes": 2, "url": ""},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with tempfile.TemporaryDirectory() as tmp:
                self.build(Path(tmp) / "public")
                public = Path(tmp) / "public"
                post = (public / "posts" / "_stats-a" / "index.html").read_text(
                    encoding="utf-8"
                )
                unliked = (public / "posts" / "_stats-c" / "index.html").read_text(
                    encoding="utf-8"
                )
                home = (public / "index.html").read_text(encoding="utf-8")
                ranking = (public / "ranking" / "index.html").read_text(
                    encoding="utf-8"
                )

            self.assertIn("10 字", post)
            self.assertIn("约 1 分钟", post)
            self.assertIn("站内赞 5", post)
            self.assertIn("站内赞 0", unliked)
            self.assertIn(f"共 {self.expected_main_section_count()} 篇", home)
            self.assertIn("站内赞 7", home)
            self.assertLess(
                ranking.index("TABTEST-LIKE-A"), ranking.index("TABTEST-LIKE-B")
            )
            self.assertIn("站内赞 5", ranking)
            self.assertNotIn("rank-top", ranking)
            self.assertIn("ranking-filter", ranking)
            self.assertIn('data-filter="测试A"', ranking)
            self.assertIn('data-tags="测试A"', ranking)
            self.assertIn('data-sort="likes"', ranking)
            self.assertIn('data-sort="time"', ranking)
            self.assertIn("data-likes=", ranking)
            self.assertIn("data-date=", ranking)
            self.assertIn("点赞与评论", post)
            self.assertIn("comments-hint", post)
        finally:
            for bundle in reversed(created):
                shutil.rmtree(bundle, ignore_errors=True)
            if backup is None:
                likes_path.unlink(missing_ok=True)
            else:
                likes_path.write_bytes(backup)

    def test_single_shows_publish_and_edit_dates(self):
        created = []
        try:
            for slug, title, lastmod in (
                ("_date-edited", "SITETEST-EDITED", "2026-10-23"),
                ("_date-plain", "SITETEST-PLAIN", None),
            ):
                bundle = self.root / "content" / "posts" / slug
                bundle.mkdir(parents=True)
                lastmod_line = f"lastmod: {lastmod}\n" if lastmod else ""
                (bundle / "index.md").write_text(
                    f'---\ntitle: "{title}"\ndate: 2026-10-20\n'
                    f"{lastmod_line}draft: false\n---\n\n正文\n",
                    encoding="utf-8",
                )
                created.append(bundle)

            with tempfile.TemporaryDirectory() as tmp:
                self.build(Path(tmp) / "public")
                public = Path(tmp) / "public"
                edited = (public / "posts" / "_date-edited" / "index.html").read_text(
                    encoding="utf-8"
                )
                plain = (public / "posts" / "_date-plain" / "index.html").read_text(
                    encoding="utf-8"
                )
                home = (public / "index.html").read_text(encoding="utf-8")

            self.assertIn("发布于 2026-10-20", edited)
            self.assertIn("最后编辑于 2026-10-23", edited)
            self.assertIn("发布于 2026-10-20", plain)
            self.assertNotIn("最后编辑于", plain)
            self.assertNotIn("发布于", home)
        finally:
            for bundle in reversed(created):
                shutil.rmtree(bundle, ignore_errors=True)

    def test_home_shows_pinned_items_before_latest(self):
        data = self.root / "data" / "pinned.yml"
        backup = data.read_bytes() if data.exists() else None
        data.parent.mkdir(parents=True, exist_ok=True)
        data.write_text(
            "items:\n"
            '  - title: "SITETEST-PINNED"\n'
            '    url: "/posts/hello-world/"\n'
            '    description: "SITETEST-DESC"\n',
            encoding="utf-8",
        )
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self.build(Path(tmp) / "public")
                home = (Path(tmp) / "public" / "index.html").read_text(
                    encoding="utf-8"
                )

            self.assertIn("SITETEST-PINNED", home)
            self.assertIn("SITETEST-DESC", home)
            self.assertIn('href="/posts/hello-world/"', home)
            self.assertLess(
                home.index("SITETEST-PINNED"), home.index("最新文章")
            )
        finally:
            if backup is None:
                data.unlink()
            else:
                data.write_bytes(backup)

    def test_stats_page_and_entry_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build(Path(tmp) / "public")
            public = Path(tmp) / "public"
            stats = (public / "stats" / "index.html").read_text(encoding="utf-8")
            home = (public / "index.html").read_text(encoding="utf-8")
            ranking = (public / "ranking" / "index.html").read_text(encoding="utf-8")

        for needle in ("发文频率", "更新热力图", "写作节奏", "最近更新", "年度回顾"):
            self.assertIn(needle, stats)
        self.assertIn("stats-cell", stats)
        self.assertIn('href="/stats/"', home)
        self.assertIn('href="/ranking/"', home)
        self.assertIn('href="/stats/"', ranking)
        self.assertIn('href="/ranking/"', stats)

    def test_header_more_menu_groups_secondary_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = Path(tmp) / "public"
            self.build(public)
            home = (public / "index.html").read_text(encoding="utf-8")
            about = (public / "about" / "index.html").read_text(encoding="utf-8")

        more = re.search(r'<details class="menu-more-panel">.*?</details>', home, re.S)
        self.assertIsNotNone(more)
        panel = more.group(0)
        for path in ("ranking/", "stats/", "about/"):
            self.assertRegex(panel, rf'href="[^"]*{path}"')

        primary = home[
            home.index('<ul id="menu" class="menu">') : home.index(
                '<li class="menu-more">'
            )
        ]
        for path in ("ranking/", "stats/", "about/"):
            self.assertNotIn(path, primary)

        self.assertIn('class="menu-more-toggle active"', about)


if __name__ == "__main__":
    unittest.main()
