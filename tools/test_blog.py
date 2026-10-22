import argparse
import contextlib
import datetime as dt
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blog


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
            "---\ntitle: Hello\ndraft: true\n---\n\nnew\n", encoding="utf-8"
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

    def test_declined_draft_is_not_committed(self):
        draft = self.root / "content/posts/hello/index.md"
        draft.write_text(
            "---\ntitle: Hello\ndraft: true\n---\n\nnew\n", encoding="utf-8"
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
            f"---\ntitle: Hello\ndraft: true\n---\n\n{local}\n", encoding="utf-8"
        )
        before = self.git("rev-parse", "HEAD").stdout.strip()
        with mock.patch("blog.ask_yes_no", side_effect=[True, False]):
            with contextlib.redirect_stdout(io.StringIO()):
                code = blog.cmd_publish(self.args(), root=self.root)
        self.assertEqual(code, 1)
        self.assertIn("draft: true", draft.read_text(encoding="utf-8"))
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), before)


if __name__ == "__main__":
    unittest.main()
