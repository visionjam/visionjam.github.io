# 个人博客网站 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 Hugo + PaperMod 搭建一个中文极简阅读风个人博客，并通过 GitHub Actions 自动部署到 `https://visionjam.github.io`。

**Architecture:** 静态站点生成。Markdown 内容位于 `content/`，Hugo 在构建时生成 `public/`；GitHub Actions 在 `main` 分支更新后构建并发布到 GitHub Pages。主题以 git submodule 固定到具体 commit。站点为根路径部署，无自定义域名。

**Tech Stack:** Hugo Extended 0.168.0、PaperMod（commit `969bebdc5600a1639158b5ef4eff9cf6cbb511ac`）、GitHub Actions、GitHub Pages。

## Global Constraints

- 界面文案与示例内容使用简体中文；命令、配置键、代码保留英文。
- `baseURL: "https://visionjam.github.io/"`，`defaultContentLanguage: "zh"`，`languageCode: "zh-cn"`。
- 不引入外部字体或 CDN；不添加评论、统计、分享按钮。
- 不提交 `public/`、`resources/_gen/`、`.hugo_build.lock`，不提交工作区里的两张 `Snipaste_*.png`。
- 每个任务结束后在本地 `main` 提交一次；**未获得用户具名确认前，不得执行 `git push`**。
- 所有验证命令在仓库根目录 `E:/my blog` 执行。

---

## File Map

| 文件 | 职责 |
|---|---|
| `hugo.yml` | 站点配置：语言、菜单、PaperMod 参数、搜索输出 |
| `.gitignore` | 排除构建产物与系统文件 |
| `themes/PaperMod` | 主题 submodule，固定 commit |
| `content/about.md` | 关于页 |
| `content/archives.md` | 归档页 |
| `content/search.md` | 搜索页 |
| `content/posts/_index.md` | 文章分区标题与描述 |
| `content/tags/_index.md` | 标签索引页标题 |
| `content/posts/hello-world/index.md` | 示例文章 |
| `archetypes/posts.md` | 新建文章的模板 |
| `assets/css/extended/custom.css` | 极简阅读风视觉覆盖 |
| `.github/workflows/hugo.yml` | 构建与部署工作流 |
| `README.md` | 写作、预览、发布说明 |

---

### Task 1: 项目骨架、主题与站点配置

**Files:**
- Create: `hugo.yml`
- Create: `.gitignore`
- Create: `content/about.md`
- Create: `content/archives.md`
- Create: `content/search.md`
- Create: `content/posts/_index.md`
- Create: `content/tags/_index.md`
- Delete: `_config.yml`
- Create (submodule): `themes/PaperMod`

**Interfaces:**
- Consumes: 无（仓库现有内容仅为 Jekyll 占位）。
- Produces: 可构建的 Hugo 站点；菜单路径 `/posts/`、`/tags/`、`/archives/`、`/search/`、`/about/`；搜索索引 `/index.json`；RSS `/index.xml`。

- [ ] **Step 1: 安装 Hugo 扩展版**

```bash
winget install --id Hugo.Hugo.Extended -e --accept-source-agreements --accept-package-agreements
```

- [ ] **Step 2: 让当前 shell 找到 Hugo 并验证版本**

```bash
export PATH="$(cygpath -u "$LOCALAPPDATA")/Microsoft/WinGet/Links:$PATH"
hugo version
```

Expected: 输出包含 `hugo v0.168.0+extended`（或更高版本且带 `+extended`）。

- [ ] **Step 3: 添加 PaperMod 主题 submodule 并固定 commit**

```bash
git -c url."git@github.com:".insteadOf="https://github.com/" submodule add --depth 1 https://github.com/adityatelange/hugo-PaperMod.git themes/PaperMod
```

Expected: `themes/PaperMod` 创建成功，`.gitmodules` 中记录的 URL 为 `https://github.com/adityatelange/hugo-PaperMod.git`。

- [ ] **Step 4: 校验并固定主题版本**

```bash
git -C themes/PaperMod checkout 969bebdc5600a1639158b5ef4eff9cf6cbb511ac
```

```bash
git -C themes/PaperMod rev-parse HEAD
```

Expected: 输出 `969bebdc5600a1639158b5ef4eff9cf6cbb511ac`。

- [ ] **Step 5: 写入站点配置 `hugo.yml`**

```yaml
baseURL: "https://visionjam.github.io/"
title: "VisionJam"
languageCode: "zh-cn"
defaultContentLanguage: "zh"
theme: ["PaperMod"]

enableRobotsTXT: true
buildDrafts: false
buildFuture: false
buildExpired: false
enableEmoji: true
pygmentsUseClasses: true

pagination:
  pagerSize: 10

taxonomies:
  tag: tags

menu:
  main:
    - identifier: posts
      name: 文章
      url: /posts/
      weight: 10
    - identifier: tags
      name: 标签
      url: /tags/
      weight: 20
    - identifier: archives
      name: 归档
      url: /archives/
      weight: 30
    - identifier: search
      name: 搜索
      url: /search/
      weight: 40
    - identifier: about
      name: 关于
      url: /about/
      weight: 50

params:
  env: production
  description: "VisionJam 的个人博客，记录思考、技术与生活。"
  author: "VisionJam"
  mainSections:
    - posts
  defaultTheme: auto
  ShowReadingTime: true
  ShowShareButtons: false
  ShowPostNavLinks: true
  ShowBreadCrumbs: true
  ShowCodeCopyButtons: true
  ShowRssButtonInSectionTermList: true
  ShowAllPagesInArchive: true
  ShowPageNums: true
  ShowToc: true
  TocOpen: false
  ShowWordCount: false
  homeInfoParams:
    Title: "你好，我是 VisionJam"
    Content: "记录思考、技术与生活。这里会不定期更新文章。"
  socialIcons:
    - name: github
      title: GitHub
      url: "https://github.com/visionjam"
    - name: rss
      title: RSS 订阅
      url: "/index.xml"
  assets:
    disableHLJS: true

outputs:
  home:
    - HTML
    - RSS
    - JSON

markup:
  highlight:
    noClasses: false
    codeFences: true
    guessSyntax: true
    lineNos: false
```

- [ ] **Step 6: 写入 `.gitignore`**

```gitignore
public/
resources/_gen/
.hugo_build.lock
.DS_Store
Thumbs.db
```

- [ ] **Step 7: 写入页面内容**

`content/about.md`：

```markdown
---
title: "关于"
description: "关于我和这个博客"
---

你好，我是 **VisionJam**。

这里是我的个人博客，用来记录思考、技术与生活。

- GitHub：[@visionjam](https://github.com/visionjam)
- RSS：[/index.xml](/index.xml)

> 这段介绍可以在 `content/about.md` 中随时修改。
```

`content/archives.md`：

```markdown
---
title: "归档"
layout: "archives"
summary: "按时间浏览全部文章"
---
```

`content/search.md`：

```markdown
---
title: "搜索"
placeholder: "搜索文章标题或正文…"
layout: "search"
---
```

`content/posts/_index.md`：

```markdown
---
title: "文章"
description: "全部文章，按时间倒序排列"
---
```

`content/tags/_index.md`：

```markdown
---
title: "标签"
description: "按标签浏览文章"
---
```

- [ ] **Step 8: 删除 Jekyll 占位配置**

```bash
git rm _config.yml
```

- [ ] **Step 9: 构建站点**

```bash
hugo --minify
```

Expected: 命令退出码为 0，生成 `public/`，无 ERROR。

- [ ] **Step 10: 验证关键输出文件**

```bash
for f in public/index.html public/index.xml public/index.json public/about/index.html public/archives/index.html public/search/index.html public/posts/index.html public/tags/index.html; do test -f "$f" && echo "OK $f" || echo "MISSING $f"; done
```

Expected: 8 行全部为 `OK`。

- [ ] **Step 11: 验证中文与菜单**

```bash
grep -o 'lang="zh-cn"' public/index.html | head -1
```

```bash
grep -q '文章' public/index.html && grep -q '关于' public/index.html && echo "MENU ZH OK"
```

Expected: 第一行输出 `lang="zh-cn"`；第二行输出 `MENU ZH OK`。

- [ ] **Step 12: 提交**

```bash
git add hugo.yml .gitignore content .gitmodules themes/PaperMod
git commit -m "feat: 初始化 Hugo 站点与 PaperMod 主题

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: 极简阅读风视觉定制

**Files:**
- Create: `assets/css/extended/custom.css`

**Interfaces:**
- Consumes: Task 1 生成的 PaperMod 主题与 `.post-entry`、`.md-content` 等类名。
- Produces: 构建后合并进 `public/assets/css/stylesheet.*.css` 的定制样式。

- [ ] **Step 1: 写入 `assets/css/extended/custom.css`**

```css
/* 站点视觉微调：极简阅读风 */

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
    "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
  letter-spacing: 0.01em;
}

/* 首页与列表页：去掉卡片感，改为分隔线 */
.post-entry {
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--border);
  border-radius: 0;
  padding: 28px 0;
  transition: none;
}

.post-entry:hover,
.post-entry:focus-within {
  transform: none;
  border-color: var(--border);
}

.post-entry:last-of-type {
  border-bottom: none;
}

/* 标题使用衬线字体，增强阅读气质 */
.post-title,
.entry-header h2,
.md-content h1,
.md-content h2,
.md-content h3 {
  font-family: Georgia, "Times New Roman", "Songti SC", "SimSun", serif;
  letter-spacing: 0;
}

/* 正文排版 */
.md-content {
  font-size: 17px;
  line-height: 1.9;
}

.md-content p {
  margin: 1.1em 0;
}

/* 墨蓝强调色 */
.md-content a:not(.anchor),
.post-tags a,
.terms-tags a {
  color: #2f5d8a;
}

:root[data-theme="dark"] .md-content a:not(.anchor),
:root[data-theme="dark"] .post-tags a,
:root[data-theme="dark"] .terms-tags a {
  color: #8fb8da;
}
```

- [ ] **Step 2: 重新构建**

```bash
hugo --minify
```

Expected: 退出码 0，无 ERROR。

- [ ] **Step 3: 验证定制样式已合并**

```bash
grep -l 'Hiragino Sans GB' public/assets/css/stylesheet.*.css
```

Expected: 输出至少一个 `public/assets/css/stylesheet.<hash>.css` 路径。

- [ ] **Step 4: 验证首页列表已去掉卡片样式**

```bash
grep -o 'border-bottom:1px solid var(--border)' public/assets/css/stylesheet.*.css | head -1
```

Expected: 输出 `border-bottom:1px solid var(--border)`（压缩后无空格）。

- [ ] **Step 5: 提交**

```bash
git add assets/css/extended/custom.css
git commit -m "style: 极简阅读风视觉定制

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: 文章模板与示例文章

**Files:**
- Create: `archetypes/posts.md`
- Create: `content/posts/hello-world/index.md`

**Interfaces:**
- Consumes: Task 1 的 `/posts/`、`/tags/`、RSS 与搜索索引配置。
- Produces: 新文章 frontmatter 模板；示例文章可通过 `/posts/hello-world/` 访问；标签页 `/tags/随笔/`。

- [ ] **Step 1: 写入文章模板 `archetypes/posts.md`**

```markdown
---
title: "{{ replace .File.ContentBaseName "-" " " | title }}"
date: {{ now.Format "2006-01-02" }}
draft: true
tags: []
summary: ""
---

在这里开始写作。
```

- [ ] **Step 2: 验证模板可生成正确 frontmatter**

```bash
hugo new content posts/archetype-check/index.md
```

```bash
sed -n '1,6p' content/posts/archetype-check/index.md
```

Expected: 标题为 `Archetype Check`，`draft: true`，日期为当天（`2026-10-22`）。

- [ ] **Step 3: 删除模板验证文件**

```bash
rm -rf content/posts/archetype-check
```

- [ ] **Step 4: 写入示例文章 `content/posts/hello-world/index.md`**

````markdown
---
title: "你好，世界"
date: 2026-10-22
draft: false
tags: ["随笔"]
summary: "本站的第一篇文章：为什么开始写博客，以及这里会写些什么。"
---

欢迎来到我的个人博客。

这个站点使用 [Hugo](https://gohugo.io/) 和 [PaperMod](https://github.com/adityatelange/hugo-PaperMod) 搭建，内容全部以 Markdown 编写，托管在 GitHub Pages 上。

## 为什么写博客

把零散的想法写下来，是一种很好的整理方式。写作会迫使我把「大概知道」变成「真正想清楚」。

这里计划记录三类内容：

- 技术笔记：工具、代码与踩过的坑
- 阅读与思考：书、文章和日常观察
- 生活随笔：值得留下的片段

## 怎么读

- 在[归档](/archives/)里按时间浏览
- 通过[标签](/tags/)找同类文章
- 使用[搜索](/search/)查找关键词
- 订阅 [RSS](/index.xml) 获取更新

## 一段代码示例

```python
def hello(name: str) -> str:
    return f"你好，{name}！"

print(hello("世界"))
```

> 保持好奇，持续记录。

以后的文章会陆续出现在这里。
````

- [ ] **Step 5: 构建站点**

```bash
hugo --minify
```

Expected: 退出码 0，无 ERROR。

- [ ] **Step 6: 验证文章页、标签页、RSS 与搜索索引**

```bash
test -f public/posts/hello-world/index.html && echo "POST OK"
test -f "public/tags/随笔/index.html" && echo "TAG OK"
grep -q "你好，世界" public/index.xml && echo "RSS OK"
grep -q "你好，世界" public/index.json && echo "SEARCH INDEX OK"
```

Expected: 四行全部输出 `... OK`。

- [ ] **Step 7: 提交**

```bash
git add archetypes/posts.md content/posts/hello-world
git commit -m "content: 添加文章模板与示例文章

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: GitHub Actions 自动部署与使用文档

**Files:**
- Create: `.github/workflows/hugo.yml`
- Modify: `README.md`（整体替换）
- Verify: `.gitmodules`

**Interfaces:**
- Consumes: Task 1–3 的 Hugo 项目、主题 submodule、构建脚本。
- Produces: push 到 `main` 后自动构建并部署的 GitHub Actions 工作流；中文维护文档。

- [ ] **Step 1: 写入 `.github/workflows/hugo.yml`**

```yaml
name: Deploy Hugo site to Pages

on:
  push:
    branches: ["main"]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          submodules: recursive

      - name: Setup Pages
        uses: actions/configure-pages@v5

      - name: Setup Hugo
        uses: peaceiris/actions-hugo@v3
        with:
          hugo-version: "0.168.0"
          extended: true

      - name: Build with Hugo
        run: hugo --minify --gc

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: ./public

  deploy:
    runs-on: ubuntu-latest
    needs: build
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: 校验工作流 YAML 语法**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/hugo.yml', encoding='utf-8')); print('YAML OK')"
```

Expected: `YAML OK`。

- [ ] **Step 3: 整体替换 `README.md`**

```markdown
# VisionJam 的博客

基于 [Hugo](https://gohugo.io/) 与 [PaperMod](https://github.com/adityatelange/hugo-PaperMod) 的个人博客，部署在 GitHub Pages。

- 线上地址：https://visionjam.github.io
- 写作方式：Markdown（`content/posts/`）

## 本地环境

- Hugo Extended（>= 0.158.0）
- Git

Windows 安装 Hugo：

```powershell
winget install --id Hugo.Hugo.Extended -e
```

首次克隆仓库后拉取主题：

```bash
git submodule update --init --recursive
```

## 写一篇新文章

```bash
hugo new content posts/文章英文名/index.md
```

生成的文件默认 `draft: true`，写完后改为 `false`。

文章头部字段：

| 字段 | 说明 |
|---|---|
| title | 标题 |
| date | 日期，YYYY-MM-DD |
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

```bash
git add .
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
hugo.yml          站点配置
assets/css/extended/custom.css   视觉定制
.github/workflows/hugo.yml       自动部署
themes/PaperMod   主题（git submodule，固定版本）
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
```

- [ ] **Step 4: 确认主题 submodule URL 为 HTTPS**

```bash
grep -A2 'submodule "themes/PaperMod"' .gitmodules
```

Expected: `url = https://github.com/adityatelange/hugo-PaperMod.git`。

- [ ] **Step 5: 最终本地构建**

```bash
hugo --minify
```

Expected: 退出码 0，无 ERROR。

- [ ] **Step 6: 确认构建产物未被纳入版本控制**

```bash
git status --short
```

Expected: 不出现 `public/` 或 `resources/` 条目；仅显示本次新增的工作流与 README 修改。

- [ ] **Step 7: 提交**

```bash
git add .github/workflows/hugo.yml README.md
git commit -m "ci: 添加 GitHub Pages 自动部署与使用文档

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: 推送上线与线上验收

**Files:**
- 无新增文件（如线上验收发现问题，回到对应任务修复）。

**Interfaces:**
- Consumes: 本地 `main` 上 Task 1–4 的全部提交。
- Produces: 可访问的 `https://visionjam.github.io`。

- [ ] **Step 1: 获取用户对推送目标的具名确认**

向用户确认以下具体动作：

> 是否推送到 `visionjam/visionjam.github.io` 仓库的 `main` 分支？

只有得到明确的“是/可以/推送”回复后才继续。

- [ ] **Step 2: 推送**

```bash
git push origin main
```

Expected: 推送成功；GitHub 上出现最新提交。

- [ ] **Step 3: 由用户在网页端设置 Pages 来源**

用户在浏览器打开：

`https://github.com/visionjam/visionjam.github.io/settings/pages`

Settings → Pages → Build and deployment → Source 选择 **GitHub Actions**。

- [ ] **Step 4: 触发并观察部署**

若推送后工作流未运行或首次运行因 Pages 来源未设置而失败，在 Actions 页面点击 **Re-run all jobs**；或由用户确认后执行：

```bash
git commit --allow-empty -m "ci: 触发 Pages 部署

Co-Authored-By: Claude Code <noreply@anthropic.com>"
git push origin main
```

Expected: `Deploy Hugo site to Pages` 工作流中 build 与 deploy 均成功。

- [ ] **Step 5: 线上验收**

在代理开启的情况下（`127.0.0.1:7890`），用浏览器或以下命令检查：

```bash
curl -x http://127.0.0.1:7890 -s -o /dev/null -w "%{http_code}\n" https://visionjam.github.io/
```

```bash
curl -x http://127.0.0.1:7890 -s https://visionjam.github.io/ | grep -o '你好，我是 VisionJam' | head -1
```

Expected: 状态码 `200`；页面包含 `你好，我是 VisionJam`。

逐项人工确认：

- [ ] 首页显示介绍与示例文章
- [ ] `/posts/`、`/tags/`、`/archives/`、`/search/`、`/about/` 可访问
- [ ] `/index.xml` 可订阅
- [ ] 搜索输入关键词能返回结果
- [ ] 深浅色切换正常，刷新后保持
- [ ] 手机宽度下无横向滚动
- [ ] 中文与日期显示正常

---

## 验收标准对照

| 设计文档验收项 | 对应任务 |
|---|---|
| 首页与示例文章可访问 | Task 3、Task 5 |
| 导航各页面可访问 | Task 1、Task 5 |
| 前端搜索可用 | Task 1（JSON 输出）、Task 3（索引内容）、Task 5 |
| 深色模式可切换并保持 | Task 1（`defaultTheme: auto`）、Task 5 |
| 移动端布局正常 | Task 2、Task 5 |
| 中文排版与日期正确 | Task 1、Task 3、Task 5 |
| push 后自动构建发布 | Task 4、Task 5 |
| 本地 `hugo server -D` 可预览 | Task 1（Hugo 安装）、README |
