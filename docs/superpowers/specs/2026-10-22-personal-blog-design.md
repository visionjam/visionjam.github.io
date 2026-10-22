# 个人博客网站设计

- 日期：2026-10-22
- 状态：已确认
- 仓库：`visionjam/visionjam.github.io`
- 线上地址：`https://visionjam.github.io`

## 1. 目标

搭建一个以中文写作为主、用 Markdown 维护的个人博客，托管在 GitHub Pages。作者只需编写 Markdown 并推送，站点自动构建发布。视觉上追求极简阅读体验，长期可维护，不引入不必要的复杂度。

## 2. 技术选型

| 项目 | 选择 | 理由 |
|---|---|---|
| 静态站点生成器 | Hugo（扩展版） | 构建快、单二进制、长期稳定 |
| 主题 | PaperMod | 极简阅读风，自带标签、搜索、归档、RSS、深色模式、中文翻译 |
| 托管 | GitHub Pages | 免费、与仓库原生集成 |
| 构建 | GitHub Actions（push 到 main 触发） | 自动构建发布，不在仓库提交生成物 |
| 搜索 | Fuse.js（PaperMod 内置，构建时生成索引） | 纯前端，无需后端 |
| 字体 | 系统中文字体栈 | 不依赖外部 CDN，国内访问稳定 |

主题以 git submodule 引入并锁定到具体 commit，避免上游更新导致站点样式突变。

## 3. 站点结构

```
/                 首页：简短自我介绍 + 最新文章列表
/posts/           全部文章
/tags/            标签索引；/tags/<标签名>/ 为标签详情
/archives/        按年月归档
/search/          站内搜索
/about/           关于页（占位内容，后续填写）
/index.xml        RSS 订阅
```

导航栏：文章 / 标签 / 归档 / 搜索 / 关于，右侧为深浅色切换按钮。

## 4. 内容模型

文章采用 page bundle 形式，每篇一个目录，便于存放配图：

```
content/posts/hello-world/
├── index.md
└── cover.png        （可选）
```

Frontmatter 约定：

```yaml
---
title: "文章标题"
date: 2026-10-22
draft: false
tags: ["随笔", "技术"]
summary: "一句话摘要，用于列表与 SEO 描述"
---
```

- `draft: true` 的文章默认不进入构建。
- 分类暂由标签承担；如后续确有需要，再启用 `categories`。
- 日期显示格式统一为 `2006-01-02`。
- 文章正文中的图片使用相对路径引用同目录资源。

## 5. 视觉设计

- 白底黑字，单一墨蓝强调色（用于链接、标签、按钮）。
- 正文内容区宽度约 720px，行高宽松，段间距充足。
- 深色模式：默认跟随系统，支持手动切换并记住选择（PaperMod 内置）。
- 中文优先字体栈：`-apple-system, "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif`。
- 代码块使用主题自带的语法高亮与复制按钮。
- 文章页显示：发布日期、阅读时长、标签；长文自动生成目录。
- 关闭分享按钮、评论、作者头像等非必要元素。
- 移动端单栏布局，图片自适应宽度。

## 6. 部署

- 仓库沿用 `visionjam/visionjam.github.io`，保留已有提交历史；删除占位的 `_config.yml` 与旧 `README.md` 内容，替换为 Hugo 项目。
- GitHub Actions 工作流：
  1. checkout（含主题依赖）
  2. 安装 Hugo 扩展版
  3. `hugo --minify`
  4. 上传并部署到 GitHub Pages
- Pages 的 Source 设为 “GitHub Actions”。
- 推送 `main` 即发布；无需在仓库提交 `public/` 生成物。
- 根目录提供中文 `README.md`，记录写作、预览、发布流程与常用命令。

## 7. 写作与维护流程

```bash
hugo new content posts/my-post/index.md   # 新建文章
hugo server -D                            # 本地预览（含草稿）
git add . && git commit -m "post: ..."    # 提交
git push                                  # 触发自动部署
```

- 本地预览依赖本机安装 Hugo 扩展版；未安装时仍可通过 GitHub Actions 构建，但无法本地预览。
- 配图放在文章同目录，Markdown 相对路径引用。
- 备份与版本管理完全依赖 git。

## 8. 初始内容

- 一篇示例文章（介绍本站与写作方式）。
- 关于页占位内容。
- 文章模板（archetype）。
- 保留工作区现有两张截图，不纳入站点；后续可由作者自行清理。

## 9. 验收标准

1. 访问 `https://visionjam.github.io` 能看到首页与示例文章。
2. 导航栏各页面可访问：文章、标签、归档、搜索、关于、RSS。
3. 搜索能在前端返回文章结果。
4. 深色模式可切换，刷新后保持。
5. 移动端宽度下布局正常，无横向滚动。
6. 中文排版无乱码，日期格式正确。
7. 修改 Markdown 并推送后，GitHub Actions 自动完成构建与发布。
8. 本地 `hugo server -D` 可正常预览。

## 10. 风险与对策

- **上游主题变更**：固定主题版本，升级时单独验证。
- **构建失败**：Actions 日志可定位；README 记录排查入口。
- **代理/网络**：本机访问 GitHub HTTPS 依赖代理；推送使用已配置的 SSH。构建在 GitHub 侧执行，不受本机网络影响。
- **内容误发布**：草稿用 `draft: true`；发布前本地预览。
