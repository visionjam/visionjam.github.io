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
