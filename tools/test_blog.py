import argparse
import contextlib
import datetime as dt
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blog
import fetch_likes


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
            for slug, title, body, day in (
                ("_stats-a", "TABTEST-LIKE-A", "一二三四五六七八九十", "2026-10-21"),
                ("_stats-b", "TABTEST-LIKE-B", "一二三四五", "2026-10-20"),
                ("_stats-c", "TABTEST-LIKE-C", "一二", "2026-10-19"),
            ):
                bundle = self.root / "content" / "posts" / slug
                bundle.mkdir(parents=True)
                (bundle / "index.md").write_text(
                    f'---\ntitle: "{title}"\ndate: {day}\ndraft: false\n---\n\n{body}\n',
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
            self.assertIn("共 5 篇", home)
            self.assertIn("站内赞 7", home)
            self.assertLess(
                ranking.index("TABTEST-LIKE-A"), ranking.index("TABTEST-LIKE-B")
            )
            self.assertIn("站内赞 5", ranking)
            self.assertNotIn("rank-top", ranking)
        finally:
            for bundle in reversed(created):
                shutil.rmtree(bundle, ignore_errors=True)
            if backup is None:
                likes_path.unlink(missing_ok=True)
            else:
                likes_path.write_bytes(backup)

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


if __name__ == "__main__":
    unittest.main()
