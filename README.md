# VisionJam 的博客

基于 [Hugo](https://gohugo.io/) 与 [PaperMod](https://github.com/adityatelange/hugo-PaperMod) 的个人博客，部署在 GitHub Pages。

- 线上地址：https://visionjam.github.io
- 写作方式：Markdown（`content/posts/`）

## 主页结构

- 主页从上到下为：站点简介、全站统计条、置顶、最新 20 篇文章（`params.homeLimit` 可调）。
- 置顶在 `data/pinned.yml` 中维护，按文件顺序显示，支持站内路径与外部链接。
- 「文章」页（`/posts/`）保留全部分页列表；文章超过 20 篇时，主页底部显示「查看全部文章」。
- 「排行」页（`/ranking/`）按站内点赞数排序，可按标签筛选，并显示全站统计条。
- 「统计」页（`/stats/`）汇总发文频率、更新热力图和写作节奏；入口在首页与排行页统计条末尾。
- 文章标题下显示发布日期、最后编辑日期（仅当与发布日期不同）、中文字数、预计阅读时长和站内赞数。最后编辑日期自动取自文章文件的最后一次 Git 提交，无需手动维护。

## 本地环境

- Hugo Extended（>= 0.158.0）
- Git
- Python 3.8+（一键写作/发布工具）

Windows 安装 Hugo：

```powershell
winget install --id Hugo.Hugo.Extended -e
```

首次克隆仓库后拉取主题：

```bash
git submodule update --init --recursive
```

## 一键写作与发布（推荐）

Windows 双击 `new-post.bat` / `publish.bat`；Linux 运行 `./new-post.sh` / `./publish.sh`。

也可以在终端直接使用：

```bash
python3 tools/blog.py new
python3 tools/blog.py publish
```

- `new`：创建 `content/posts/<英文短名>/index.md`，自动填好标题和日期。
- `publish`：检测草稿、本地构建、隐私扫描、列出改动，按 `Y` 确认后只提交 `content/` 并推送到 `main`。
- 只检查不推送：`python3 tools/blog.py publish --dry-run`。
- 没装 Hugo 或不是 extended 版时，脚本会跳过本地构建并提示；GitHub Actions 仍会构建。
- 隐私扫描覆盖文本文件中的本机路径、代理地址、密钥、手机号等；图片内容仍需自行确认。
- 工具测试：`python3 tools/test_blog.py`。

## 评论、站内点赞与 GitHub 贡献

- 文章页评论使用 [Giscus](https://giscus.app/)，需要 GitHub 登录；评论和主帖 👍 都存储在 GitHub Discussions。
- 站内赞就是 Giscus 主帖的 👍 数：构建前由 `tools/fetch_likes.py` 读取并写入 `data/likes.json`，页面和排行读取这份数据。点赞后要等下一次构建（每天 03:00 UTC 或下次推送）才会更新显示。当前站内赞为 0（尚未有人点赞）。
- About 页的 GitHub 贡献日历由 [lowlighter/metrics](https://github.com/lowlighter/metrics) 在 GitHub Actions 构建时生成，每天自动刷新。

### 当前状态与限制（2026-10-24）

- 站内赞目前为 0（尚未有人点赞）；点赞后需下一次推送或每日 03:00 UTC 构建才更新。
- 博客没有知乎赞/浏览量；浏览量未接第三方统计。

## 写一篇新文章（手动方式）

```bash
hugo new content posts/文章英文名/index.md
```

生成的文件默认 `draft: true`，写完后改为 `false`。

文章头部字段：

| 字段 | 说明 |
|---|---|
| title | 标题 |
| date | 发布日期，YYYY-MM-DD |
| lastmod | 可选，最后编辑日期；不填则自动取 Git 最后提交日期 |
| draft | 是否为草稿 |
| tags | 标签数组 |
| summary | 摘要，用于列表和 SEO |
| cover.image | 可选，封面图相对路径 |

正文使用标准 Markdown。配图放在文章同目录，例如：

```markdown
![图片说明](cover.png)
```

## 本地预览

```bash
hugo server -D
```

打开 http://localhost:1313 。`-D` 表示包含草稿。

## 发布

推荐使用上面的 `publish.bat` / `publish.sh`。手动方式：

```bash
git add content
git commit -m "post: 文章标题"
git push
```

推送到 `main` 后，GitHub Actions 会自动构建并发布到 GitHub Pages，通常 1–2 分钟生效。

## 目录结构

```
content/
  posts/          文章（每篇一个目录）
  about.md        关于页
  archives.md     归档页
  search.md       搜索页
tools/
  blog.py         写作与发布工具
  fetch_likes.py  从 GitHub Discussions 读取站内赞
  test_blog.py    工具与站点构建测试
data/
  pinned.yml      主页置顶清单
  likes.json      站内赞快照（CI 构建前自动刷新）
layouts/
  list.html       主页与列表页布局覆盖
  single.html     单页布局覆盖（传入日期标签开关）
  ranking.html    站内赞排行页
  _partials/comments.html          Giscus 评论/点赞
  _partials/post_meta.html         发布日期/最后编辑、字数、阅读时长、站内赞
  _partials/site_stats.html        全站统计条
  _shortcodes/github-metrics.html  About 贡献图
static/                              CI 生成的贡献 SVG（本地通常为空）
new-post.bat / publish.bat       Windows 双击入口
new-post.sh / publish.sh         Linux 入口
hugo.yml          站点配置
assets/css/extended/custom.css   视觉定制
.github/workflows/hugo.yml       自动部署
themes/PaperMod   主题（git submodule，固定版本）
.gitattributes    跨平台换行符规则
```

## 主题升级

```bash
git submodule update --remote themes/PaperMod
```

升级后务必本地 `hugo server -D` 检查，再提交。

## 常见问题

- **推送到 main 后没有更新**：查看仓库 Actions 页面；确认 Settings → Pages → Source 为 “GitHub Actions”。
- **本地 hugo 命令找不到**：重新打开终端，或确认 Hugo 已加入 PATH。
- **文章没显示**：检查 `draft` 是否为 `false`、日期是否为未来时间。
- **`python3: command not found`**：安装 Python 3.8+，或把 Python 加入 PATH。
- **`publish.sh: Permission denied`**：运行 `bash publish.sh`，或 `chmod +x publish.sh`。
- **双击 `.bat` 没有反应**：在终端运行 `python tools/blog.py publish` 查看具体错误。
