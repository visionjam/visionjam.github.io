---
title: "我如何使用 Obsidian"
date: 2026-10-25
draft: false
tags: ["Obsidian", "知识管理", "工具"]
aliases: ["/posts/wo-ruhe-shiyong-obsidian/"]
summary: "Windows 与 Android 双端同步、移动端 toolbar 与启动速度、Markdown 常用语法、插件取舍，以及一套按活动组织的仓库结构。半年、400+ 篇笔记的 Obsidian 工作流。"
---

2026 年 4 月 2 日，我认识了 Obsidian 这个知识管理软件，我在电脑上创建了第一个 vault。半年后，它有 400 多篇笔记、500 多次提交。大部分提交是自动备份，但这个数字至少说明一件事：它不是我装完就放着吃灰的软件。

这篇不写「Obsidian 有多牛逼」，也不列 30 个插件。我只写我自己每天在用的那部分：怎么同步、手机怎么用、Markdown 怎么写、插件怎么选、目录怎么放。

我的设备是 Windows + Android；没有 Mac，也没有用官方 Sync。~~（穷学生）~~ 下面的设置不是标准答案，是我用了半年后留下来的。如果你刚开始，别照抄，先挑一块能解决你当前问题的。

我的笔记库在 GitHub 上本身是私有仓库；公开的只有这个博客和 CSS/主题仓库。文章里的数字是聚合的，截图做了脱敏；结构是真实的，内容不展开。

{{< figure src="mobile-home.jpg" align="center" caption="移动端主页：周期提醒和统计卡；统计排除了模板和配置目录，所以数字比全库略少。" >}}

## 一、同步与基础设置

### 为什么用 Git，不用官方 Sync

官方 Sync 更省事：登录、付费、打开同步，完事。它适合大多数人。

我选 Git，是因为三个很具体的理由：

1. 免费，私有仓库够用；
2. 有提交历史，改坏了能回退；（有时候插件会发生莫名其妙的冲突）
3. 数据在 GitHub 上，哪天不想用 Obsidian 了，Markdown 还在。

代价也很具体：手机端要装 Git 客户端，冲突要自己处理，图片（也可以用图床）和插件会让仓库变大。如果你不想折腾，官方 Sync 是更好的选择。工具是拿来用的，不是拿来供的。

### Windows：obsidian-git

我在 Windows 上装的是 obsidian-git。核心设置就几项：

| 设置               | 我的值    | 说明                    |
| ------------------ | --------- | ----------------------- |
| 自动提交间隔       | 5 分钟    | 停止编辑后 5 分钟       |
| 停止编辑后自动提交 | 开        | 不是无条件每 5 分钟提交 |
| 自动推送间隔       | 0（关闭） | push 手动               |
| 启动时自动 pull    | 开        | 换设备先拿最新          |
| push 前先 pull     | 开        | 减少冲突                |
| 同步方式           | merge     | 不改写历史              |

关键在最后两列：**我只让它自动 commit，不让它自动 push。**

自动提交是保险，自动推送是风险。写到一半的笔记、还没检查的截图、临时改坏的 frontmatter，都不应该自动跑到另一台设备上。我宁可写完一段，自己按一下 push。

自动备份的 commit message 我用 `vault backup: {{date}}`，看历史时一眼就能认出哪些是机器提交的。push 失败时先 `pull --rebase`，不要 force push。这条不是洁癖，是保住历史。

### Android：GitSync

手机端我用 GitSync，不用 obsidian-git。obsidian-git 在 Android 上不稳定，弹窗和同步失败都遇到过；GitSync 更像一个正经的 Git 客户端。

步骤不复杂：

1. 在 GitSync 里登录 GitHub，选 `ALL REPOS`，不然看不到私有仓库；
2. 把仓库 clone 到手机本地；
3. 在 Obsidian 里打开这个本地文件夹作为 vault。

有两个坑值得提前说：

- **不要从电脑直接拷 vault 到手机。** 文件是过去了，但 Git 的元数据和文件状态会对不上，后面容易冲突。让手机自己 clone。
- **SSH 在手机上可能有问题。** 我用的是 GitHub 登录；如果你非要用 SSH，先把 key 导入 GitSync，别指望系统 ssh 能直接工作。

GitSync 可以设置「打开/关闭 App 时同步」。方便，但仓库大的时候会拖慢启动；如果你在意启动速度，可以先用手动同步，或者改成定时。

### 哪些东西不要同步

我的 `.gitignore` 大概是这样：

```gitignore
# 每台设备自己的界面布局
.obsidian/workspace.json
.obsidian/workspace-mobile.json

# 本地回收站
.trash/

# 桌面专用、手机端会出问题的插件
.obsidian/plugins/obsidian-git/
.obsidian/plugins/obsidian42-brat/

# 字体和自动生成的巨型 CSS
fonts/
.obsidian/plugins/custom-font-loader/*_v*.css
```

解释一下：

- `workspace.json` 和 `workspace-mobile.json` 是每台设备的窗口布局。同步它，换设备就会恢复一堆你没开的标签页，甚至卡在恢复阶段。
- `.trash/` 是本地回收站，不是内容。
- obsidian-git 和 BRAT 这类插件在手机端容易出问题，干脆不同步。
- 字体和 custom-font-loader 生成的 CSS 可能几十 MB，同步它们纯属给手机添堵。

我还排除了两个 AI 插件和一份只在本地保留的归档。每个人的情况不同，原则是一样的：**只同步内容和你真的需要的配置，不同步每台设备自己的状态。**

另外，我用了 `.gitattributes` 统一换行符：

```gitattributes
* text=auto
*.png binary
*.jpg binary
*.wasm binary
```

Windows 和 Android 的换行符不一样，不统一的话，每天都会看到「文件没改但 diff 一整页」的假冲突。

### 插件代码要不要同步？

我选择同步。

理由很实际：一台新设备 clone 下来，插件、配置、CSS 都在，打开就能用。代价是仓库变重，手机启动会慢一点。

我知道这不是最优解。如果你更在意启动速度，可以只同步 `data.json`，插件各端自己装；但那样每台设备都要手动配一遍。**这是取舍，不是对错。**

我的 `cm-chs-patch` 还会在 `.obsidian/` 里放两个 jieba wasm，加起来大概 10MB。我需要它按中文词移动光标、按中文标点停，所以留着；如果你不需要中文分词，可以关掉它，顺便把这两个文件从同步里拿掉。

### 两端共用的基础设置

| 设置             | 我的选择                |
| ---------------- | ----------------------- |
| 新建链接格式     | Markdown 链接，相对路径 |
| 附件默认位置     | `附件`                  |
| 自动更新内部链接 | 开                      |
| 显示行号         | 开                      |
| 自动全屏         | 开                      |
| 正文字号         | 16px                    |
| 主题             | GitHub Theme            |
| CSS 片段         | 9 个，后面单独讲        |

热键我只改了几个常用的：

- `Mod+M`：移动文件；
- `Mod+Shift+F`：全局搜索；
- `Mod+Alt+←`：后退。

这些设置里最重要的是链接格式和附件路径，其他都是手感。链接格式选错了，以后迁移会痛苦；附件路径不统一，图片会散得到处都是。

## 二、移动端：toolbar 与启动速度

移动端不是缩小版 PC。它屏幕小、输入慢、后台容易被杀，适合记录和轻编辑，不适合整理几百条笔记。接受这个前提，很多取舍就自然了。

### Toolbar 怎么配

Obsidian 的移动端工具栏可以自定义：**设置 → 移动端 → 管理工具栏选项**。你可以拖动排序、删除，也可以滑到底部点「添加全局命令」，把插件命令加进来。工具栏放不下时可以左右滑。

{{< figure src="mobile-toolbar-settings.jpg" align="center" caption="设置 → 移动端：管理工具栏和 Quick Action。" >}}

我的工具栏有 20 多个命令，大致分三组：

- **格式**：粗体、斜体、删除线、高亮、代码、标题、引用、无序列表、有序列表、任务、缩进/反缩进；
- **链接与结构**：插入 wikilink、插入嵌入、插入标签、Block Link Plus 的复制块链接/复制嵌入/复制 URL；
- **编辑**：撤销、重做、分隔线。

为什么留 Block Link Plus 的三个命令？因为手机上选中一段话，直接复制块链接或嵌入，比回电脑再弄方便得多。这是我少数愿意为插件腾出工具栏位置的地方。

工具栏不是越全越好。它只该放你打字时频繁用的动作，低频操作走命令面板。Android 输入法的候选栏还会和工具栏抢空间，命令太多，屏幕就只剩一条缝了。

{{< figure src="mobile-toolbar.jpg" align="center" caption="移动端 toolbar：截图里是工具栏第一屏，剩下的左右滑。" >}}

### 启动慢，先看启动时间

Obsidian 自带启动时间面板：**设置 → 通用 → 高级 → 计时器图标**。它会告诉你总启动时间、vault 加载、workspace 恢复、核心插件和每个社区插件各花了多久。

先看数字，再动手。不要一上来就装「加速插件」，那多半是拿一个新的插件去解决旧插件造成的问题。

我最近一次手机上启动（Android 16、Obsidian 1.14.4）是 3,457ms：vault 423ms、workspace 346ms、核心插件 166ms、社区插件 2,086ms。16 个活跃社区插件占了大头，笔记本身反而不是瓶颈。有的插件会严重拖慢速度，影响体验。

启动时间通常由几块组成：

- **vault 加载**：文件数量、附件大小、`.git` 目录；
- **workspace 恢复**：上次开了多少标签页、侧栏有多少面板；
- **核心插件**：一般很稳定；
- **社区插件**：差异最大，有的几毫秒，有的几秒。

### 影响启动速度的几类东西

**插件。** 不是数量多就一定慢，但重插件很要命。Dataview 会随笔记数量增长，Omnisearch 会索引整个库，AI 类插件可能加载模型或 SDK，obsidian-git 在手机端本身就不该开。

**Workspace。** 有时候插件没问题，是上次开的标签页太多。`workspace-mobile.json` 不参与同步，但它还在本地；如果某天启动特别慢，可以清掉它，让 Obsidian 重新开一个干净的工作区。

**大文件。** 我的库里有两个 jieba wasm（约 10MB）、十几 MB 的插件代码、可能几十 MB 的字体 CSS。它们不参与笔记渲染，但会跟着 Git 同步，也会被 Obsidian 扫描。手机空间小的时候，这些就是负担。

**CSS 和主题。** 大主题、几十个全局片段、复杂选择器都会增加渲染成本。我的 9 个片段尽量限定在 `.dashboard` 和 `.bases-index` 里，不让它们污染整个界面。

**GitSync 的自动同步。** 如果设置成打开/关闭 App 时同步，每次打开 Obsidian 都要先 fetch/pull；仓库大时，这段时间足够你去泡杯茶。

**Dataview 重查询。** 我的主页有一堆 dataviewjs：统计卡、内容分布、月度趋势、最近动态。它们每次渲染都要扫库。手机上打开主页，等于把整个库跑一遍。我的做法是：手机只记录，重查询留在 PC。

**Templater 的文件夹触发。** 这个坑很隐蔽：模板映射写在 `data.json` 里，会随 Git 同步；但总开关在 Obsidian 的 localStorage 里，**每台设备各存一份，默认关**。换手机、重装 App 之后，新建日记不会自动套模板，不是模板坏了，是开关没开。

### 我的 Android 取舍

- 保留 cm-chs-patch 和它的 wasm，因为我需要中文分词；
- 同步插件代码，图省事，接受仓库变重；
- PC 端只自动 commit，push 手动；
- CSS 片段只留常用的，不用的不启用；
- 手机上尽量不打开主页和健康统计页；
- 启动明显变慢时，先看启动时间面板，再清 workspace，最后才考虑动插件。

这些不是最优解，只是我这台手机、这个库、这个使用习惯下的平衡。

{{< figure src="startup-time.jpg" align="center" caption="启动时间面板：社区插件 2,086ms，占总启动时间 3,457ms 的大部分。" >}}

## 三、Markdown 基础语法

Obsidian 的 Markdown 基本就是 CommonMark，加了几样自己的东西：wikilink、嵌入、callout、properties、块引用、注释。

截至 2026 年 10 月 25 日，我统计了一下自己的库（排除代码块和 frontmatter）：

| 用法                        | 数量    |
| --------------------------- | ------- |
| wikilink                    | 665     |
| Markdown 链接               | 101     |
| wikilink 嵌入（`![[...]]`） | 41      |
| callout                     | 194     |
| dataview / dataviewjs       | 47 / 21 |
| checkbox                    | 154     |
| 高亮                        | 54      |
| 数学公式 / Mermaid / 脚注   | 0       |

所以这篇只讲我常用的。数学公式和 Mermaid 不是不好，是我的笔记以文字为主，用不上。

### 标题、强调、列表、任务、表格、代码

| 语法                 | 写法                                      |
| -------------------- | ----------------------------------------- |
| 标题                 | `# 一级`、`## 二级`，最多六级             |
| 粗体 / 斜体 / 删除线 | `**粗体**`、`*斜体*`、`~~删除~~`          |
| 高亮                 | `==高亮==`                                |
| 列表                 | `- 无序`、`1. 有序`，缩进表示层级         |
| 任务                 | `- [ ] 未完成`、`- [x] 已完成`            |
| 表格                 | 用竖线分隔列，第二行写三个短横线          |
| 代码                 | 行内 `` `code` ``，块用三个反引号加语言名 |

这些没什么好讲的，记住一点就够了：**标题层级要稳定**。一级标题只给笔记标题，正文从二级开始；不然大纲面板会很难看，Dataview 按标题抓内容时也会错。

### 链接与嵌入

Obsidian 里最常用的内链是 wikilink：

```markdown
[[笔记名]]
[[笔记名|显示文字]]
[[笔记名#某个标题]]
[[笔记名#^某个块ID]]
```

外部链接用 Markdown：

```markdown
[显示文字](https://example.com)
```

嵌入用感叹号：

```markdown
![[另一篇笔记]]
![[图片.png|300]]
```

我的习惯是：**内链用 wikilink，外链用 Markdown 链接。** wikilink 短，支持别名、标题和块引用；Markdown 链接通用，离开 Obsidian 也能用。

有个容易误会的地方：设置里的「使用 Markdown 链接」只影响**新建**链接，不会把已有的 wikilink 转过去。所以我的设置是 Markdown 链接，但库里仍有大量 wikilink，两种可以共存。别看到设置和实际不一致就以为坏了。

### Callout

Callout 是 Obsidian 的引用块扩展：

```markdown
> [!info]
> 这是一条提示。

> [!warning]-
> 这是一条默认折叠的警告。
```

常用类型有 `info`、`note`、`tip`、`warning`、`danger`、`quote`、`example`。标题后面加 `+` 默认展开，加 `-` 默认折叠。

我的库里 194 个 callout，大部分是 `info` 和 `quote`。`info` 用来放模板说明，`quote` 用来放摘录。Callout 比普通引用块更醒目，但也别滥用；一页十几个彩色框，重点就没了。

### 标签、属性与 CSS 开关

标签有两种写法：

```markdown
#随手记 #项目/obsidian
```

或者写在 frontmatter 里：

```yaml
---
tags:
  - Daily
  - Obsidian
---
```

属性（properties）就是 frontmatter。它不只是装饰，Dataview 读的就是这些字段：

```yaml
---
创建日期: 2026.10.25
心情: 开心
cssclasses:
  - dashboard
---
```

这里最关键的是 `cssclasses`。我的两个页面级 CSS 片段就是靠它触发的：

- `dashboard`：主页样式；
- `bases-index`：索引页样式。

没有这个字段，CSS 片段不会生效。所以「Markdown 语法」和「CSS 美化」不是两件事，frontmatter 是它们之间的接口。

### 注释、块引用、脚注、数学、Mermaid

- 注释：`%%这段不会显示%%`，写草稿时很有用；
- 块引用：在段落末尾写 `^block-id`，然后用 `[[笔记#^block-id]]` 链接过去；
- 脚注：`[^1]`，我基本不用；
- 数学：`$行内$`、`$$块级$$`，我基本不用；
- Mermaid：在代码块里写 `mermaid`，我基本不用。

块引用值得单独说一句：它适合「我要引用你这句话」，不适合「我要引用整篇」。整篇用 wikilink 或嵌入就够了。Block Link Plus 这类插件就是帮你少手写块 ID 的。

### 几个容易踩的坑

1. **frontmatter 必须在第一行。** 前面多一个空行，属性就不生效，Dataview 也读不到。
2. **字段名要统一。** 别一会儿 `日期`、一会儿 `date`、一会儿 `创建日期`；Dataview 不会帮你猜。
3. **链接格式不要混着改。** 今天用 wikilink，明天用 Markdown 链接，最后两套路径都要维护。
4. **代码块里套代码块，用四个反引号。** 三个反引号会提前结束。
5. **Markdown 是纯文本。** Obsidian 只是编辑器；哪天不用它了，文件还在。

## 四、实用插件推荐

先说我的选插件原则：

1. 先有痛点，再装插件。不要因为别人说好就装。
2. 能用一个核心插件解决，就不装三个社区插件。
3. 手机端尤其克制。每多一个插件，启动就多一份负担。

下面这些是我真正会留下来的。不是排行榜，也不是「必备清单」。想找替代品时，我会用 [SimilarPlugins](https://plugins.semiautonomous.org) 按需求搜一遍，而不是看「必备插件」清单。

### 核心工作流

**Templater**

我的 11 个模板全靠它。日记、周记、月记、季记、年记、健康记录、博客、随手记、人物、书籍、视频，每个模板都带一段自动落位脚本：决定文件放到哪个目录、叫什么名字、如果目标已存在怎么办。

它不只是「填空模板」，更像一个放在 Obsidian 里的小程序。代价是模板本身是代码，改逻辑要小心；我的做法是先用设计文档写清楚，再改模板。

**Dataview**

主页的统计卡、内容分布、最近动态，`Bases/` 下的索引页，健康页的趋势，都是 Dataview 或 dataviewjs 做的。

它的核心不是「查询语法」，是**把 frontmatter 当数据库**。你写 `心情: 开心`，它就能按心情分组；你写 `日期: 2026-10-25`，它就能按时间排序。

注意性能：`dv.pages()` 扫全库，主页上放太多 dataviewjs，手机打开会慢。能用 `LIMIT` 就用，能缩小范围就别全库扫。

**Obsidian Git**

PC 端同步用。设置前面讲过了：自动 commit，手动 push。

它在手机端不稳定，所以 Android 我用 GitSync。一个库，两种同步工具，各干各的。

**Omnisearch**

比 Obsidian 自带搜索更好用，支持中文分词和模糊匹配。我的库里有大量中文笔记，原生搜索经常找不到，Omnisearch 能救回来。

它也能索引 PDF、图片、Office 文件；我全关了，只索引 Markdown，启动和搜索都快。

**Block Link Plus**

块链接、块嵌入、复制 URL，手机上也能用。我的移动端工具栏专门给它留了三个位置。

块 ID 有个小问题：多了会污染正文。我的习惯是只在真正需要引用时加，平时用标题链接就够了。

### 其他按需

| 插件              | 我用它做什么                   | 注意                                                      |
| ----------------- | ------------------------------ | --------------------------------------------------------- |
| cm-chs-patch      | 按中文词移动光标、按中文标点停 | 会在 `.obsidian/` 放约 10MB 的 wasm                       |
| Outliner          | 列表拖动、缩进、折叠           | 手机手势和它可能打架                                      |
| Hover Editor      | 在浮窗里编辑链接笔记           | 开太多会吃内存                                            |
| Tag Wrangler      | 重命名、合并标签               | 标签少的时候就要用，别等乱了再治                          |
| Note Refactor     | 把长笔记拆成多篇               | 拆完检查链接                                              |
| Simple Columns    | 多栏 callout                   | 主页的双列布局靠它；用 `[!multi-column]` 包住 `[!column]` |
| Style Settings    | 调 GitHub Theme 的选项         | 只对支持它的主题有效                                      |
| Enhancing Export  | 用 Pandoc 导出 Word、PDF       | 要先装 Pandoc                                             |
| Image auto upload | 配合 PicGo 上传图片到图床      | PicGo 要在后台运行                                        |
| Tracker           | 按 frontmatter 画折线图        | 只适合结构化数据                                          |
| Heatmap Tracker   | 记录热力图                     | 同上，先有字段再用                                        |

插件不是收藏品。装之前先问自己：它解决的是我每天都遇到的问题，还是我想象中的问题？

## 五、我的仓库结构

### 我融合了哪几种笔记法

这套结构不是照搬某一种方法论。纯卡片盒会丢掉时间线，纯日记容易写成流水账，纯文件夹又会变成仓库管理。我最后是把几种经典做法各取一段，拼成一套：

| 经典做法           | 它解决什么                                 | 在我的库里落在哪                                              |
| ------------------ | ------------------------------------------ | ------------------------------------------------------------- |
| 原子笔记 / 卡片盒  | 一条笔记只放一个想法，方便重组和链接       | `Fleetings/` 随想 → `Blogs/` 成体系的输出                     |
| 日记 / 周期笔记    | 给记录一条时间轴，按日、周、月、季、年回看 | `Calendar/Journals/` 五层                                     |
| 文献笔记           | 外部材料先入库，再慢慢消化                 | `Calendar/Books/`、`Calendar/Videos/`；`Blogs/` 里的收藏文章   |
| 存档制             | 不删除，只让内容退出活跃区                 | `Archives/`                                                   |
| 决策记录（ADR 式） | 记住「当时为什么这么定」                   | `README/grill-me.md` 的决策台账                               |
| 数据库检索         | 不靠记忆找笔记，靠视图找                   | `Bases/` 的 Dataview 索引页                                   |
| 规则与手册         | 让结构能维护、能交接                       | `Templater/` 与 `README/`                                     |

拼的时候有一条边界：**原子笔记负责「一条笔记是什么」，文件夹负责「它现在属于哪个活动」，Bases 负责「以后怎么找回来」。** 三件事分开，结构才不会互相打架。

所以它不是 PARA。PARA 按「项目—领域—资源—存档」分；我的顶层按「记录的类型 + 活动」分。`Archives/` 只是借了存档制的生命周期，不代表整套是 PARA。

### 按活动组织，不按主题

很多人按主题分：读书、工作、生活。我试过，最后放弃了。同一个主题下的笔记，形态可能完全不同：一篇是日记，一篇是摘录，一篇是待办，放在一起只会互相干扰。

我按「这是什么东西」分：

| 目录                 | 记录什么                              |
| -------------------- | ------------------------------------- |
| `Calendar/Journals`  | 发生了什么：日、周、月、季、年        |
| `Calendar/Blogs`     | 我主动输出成体系的内容                |
| `Calendar/Fleetings` | 随手记、碎片想法                      |
| `Calendar/Health`    | 我的数据：饮食、体重                  |
| `Calendar/LifeAudit` | 我说过什么：自述档案                  |
| `Calendar/Books`     | 书摘、读书笔记（文献笔记）            |
| `Calendar/Videos`    | 视频、课程笔记（文献笔记）            |
| `Peoples`            | 人物                                  |
| `Archives`           | 已完成、不活跃但需要保留的内容        |
| `Bases`              | 视图层：索引页                        |
| `Templater`          | 规则层：模板                          |
| `README`             | 手册层：主页、系统设计、SOP、决策台账 |
| `Canvas`             | 白板层：关系图、草稿                  |

判断一条新笔记放哪，先问一句：**这是事件、材料、自述、数据、决定，还是输出？**

- 事件 → `Journals`
- 输出 → `Blogs`
- 碎片 → `Fleetings`
- 材料 → `Books` 或 `Videos`
- 数据 → `Health`
- 自述 → `LifeAudit`
- 人物 → `Peoples`
- 决定 → `README` 里的决策台账
- 规则 → `Templater` 或 `README`
- 关系图 → `Canvas`

这个分类不是一开始就有的，是用了几个月之后慢慢长出来的。刚开始别追求完整，先能跑。

### 一条笔记的旅程

拿一条笔记走一遍，结构就活了：

1. 读到一句有用的话，先扔进 `Fleetings/`。一条笔记只放一个想法，标题就是这句话的关键词。
2. 这个想法值得展开，就写成 `Blogs/` 里的一篇：补来源、补自己的判断、补链接。
3. 写的过程中如果做了一个决定，往 `README/grill-me.md` 的台账里记一行：定了什么、为什么、什么时候。
4. 当天的日记只记「今天做了什么」，用 wikilink 指向上面这些笔记，不复制正文。
5. 这条线不再活跃后，整条移进 `Archives/`；`Archives.md` 会自动列出来，需要时还能搜到。

这条链路里，**日记是索引，不是仓库**。同一件事只在一个地方有正文，其他地方放链接。这样既不重复，也不会找不到。

### 目录树

```text
visionjam_vault/
├── Calendar/                 # 记录层：按活动分，不按主题
│   ├── Journals/             # 时间轴：日 / 周 / 月 / 季 / 年
│   │   ├── Daily/
│   │   ├── Weekly/
│   │   ├── Monthly/
│   │   ├── Quarterly/
│   │   └── Yearly/
│   ├── Blogs/                # 永久笔记：主动输出，也收收藏文章
│   ├── Fleetings/            # 随想：一条一个想法
│   ├── Books/                # 书摘、读书笔记（文献笔记）
│   ├── Videos/               # 视频、课程笔记（文献笔记）
│   ├── Health/               # 数据：饮食、体重
│   └── LifeAudit/            # 自述档案
├── Peoples/                  # 人物：唯一放在 Calendar 外的内容类型
├── Archives/                 # 归档：不删除，只退出活跃区
│   ├── Archives.md           # 归档索引 + 归档规则
│   └── 小米笔记/             # 从旧系统迁移进来的存档
├── Bases/                    # 视图层：12 个 Dataview 索引页
├── Templater/                # 规则层：11 个模板
├── README/                   # 手册层：主页、SOP、系统设计、决策台账
└── Canvas/                   # 白板：关系图和草稿
```

有些目录是私人的，这里只列结构，不展开内容。结构本身不敏感，内容才敏感。

### 每个目录的职责

- `Calendar/Journals/` 是时间轴。日、周、月、季、年各一层；日记只记「发生了什么」，周记以上做汇总和回看。
- `Calendar/Fleetings/` 是入口。随想、碎片、还没成形的想法都先放这里，一条笔记只放一个想法。
- `Calendar/Blogs/` 是永久笔记端。自己写成的文章放这里；从外面读到的好文章也收在这里，打「收藏」标签和作者标签，和原创分开。
- `Calendar/Books/`、`Calendar/Videos/` 是文献笔记。书、视频、课程的摘录和消化过程放这里，不直接混进原创输出。
- `Calendar/Health/`、`Calendar/LifeAudit/` 是两个按活动建的系统。前者记数据（饮食、体重），后者记自述（我说过什么、阶段复盘）。
- `Peoples/` 是人物笔记。它是唯一放在 `Calendar/` 外面的内容类型，因为人物既不是事件，也不是输出。
- `Archives/` 是归档区。放已完成、不再活跃但需要保留的内容；入口是 `Archives.md`，里面写着归档规则和自动列出的归档清单。
- `Bases/` 是视图层。12 个索引页，每个都是带 `cssclasses: bases-index` 的 `.md` 文件，用 Dataview 把对应标签的笔记列出来。
- `Templater/` 是规则层。11 个模板，决定新笔记落到哪、叫什么名字、冲突时怎么办。
- `README/` 是手册层。主页、使用说明、SOP、三套系统的设计文档、决策台账都在这里。
- `Canvas/` 是白板层。关系图、草稿、临时推演放这里，不参与日常检索。

这里要澄清一个容易混淆的点：我的 `Bases/` 目录是**自己的 Dataview 索引页**，不是 Obsidian 官方 Bases 的 `.base` 文件。官方 Bases 我也开了，简单表格会用；复杂查询还是 Dataview 更顺手。

### 命名规则

| 类型     | 格式       | 例子                  |
| -------- | ---------- | --------------------- |
| 日记     | `YY.MM.DD` | `26.10.25`            |
| 周记     | `YY.Www`   | `26.W43`              |
| 月记     | `YY.MM`    | `26.10`               |
| 季记     | `YY.Qn`    | `26.Q4`               |
| 年记     | `YY`       | `26`                  |
| 健康记录 | `YY.MM.DD` | `26.10.25`            |
| 内容笔记 | 标题       | `我如何使用 Obsidian` |

日期型笔记用固定格式，Dataview 和链接才稳定。内容型笔记用标题，方便搜索。最忌讳的是混着来：今天 `2026年10月25日`，明天 `10-25`，后天 `today`。

### 模板系统

11 个模板的末尾都贴着同一段落位脚本，只有两行因模板而异：

```js
const TARGET_DIR = "Calendar/Journals/Daily";
const RENAME_TO = _an.format("YY.MM.DD");
```

脚本做四件事：

1. 如果文件已经在正确目录、正确名字，跳过；
2. 如果目标文件已存在，打开它，把这次新建的临时文件清理掉；
3. 如果文件名还是 `Untitled`，弹窗问名字；
4. 落位失败就提示，不把错误写进正文。

这段逻辑在 11 个模板里各有一份。改的时候要 11 处同步，所以我先用设计文档写清楚，再改模板。这是我踩过的最大的坑：模板逻辑分散，改一处忘一处。

完整模板我放在 [obsidian-visionjam-theme/templates](https://github.com/visionjam/obsidian-visionjam-theme/tree/main/templates)，11 个都在，MIT 许可。用之前先把每个模板里的 `TARGET_DIR` 改成你自己的目录。

另外，Templater 的文件夹触发还有个手机端坑：映射表在 `data.json` 里会同步，但总开关在 localStorage 里，不随 Git 同步。换手机之后要手动去设置里开一次。

### 索引层与手册层

`Bases/` 下有 12 个索引页：日记、随手记、人物、博客、书籍、视频、周记、月记、季记、年记、日历、健康。每个都用 Dataview 把对应标签的笔记列出来。

索引页靠标签工作：`#Daily`、`#Fleetings`、`#Blogs` 这些标签是检索的接口，不是装饰。新建笔记时标签打错，索引页里就会缺一条。所以我把标签也当成结构的一部分，不随便加。

<!-- 可选截图位：Bases 索引页（bases-index.jpg，待补） -->

`README/` 是我的手册层：

- `主页.md`：仪表盘；
- `README.md`：使用说明；
- `SOP of a day.md`：一天怎么过；
- 系统设计文档：模板系统、健康记录、生命审计；
- 决策台账：我决定过什么、为什么、还有什么没定。

系统也要有说明书。否则三个月后，你自己都不记得为什么这么设计。

### 维护节奏

- 每周看一眼索引页，有没有该归档的；
- 每月看一次标签，超过 20 个就合并；
- 不活跃的笔记移进 `Archives/`，不要删；
- 每季度看一次系统边界：这个系统还在服务哪个活动？不服务了就归档、合并或删掉入口；
- 结构服务内容，不要为了结构而结构。

如果你刚开始，先建三个文件夹就够了：`Daily`、`Notes`、`Attachments`。用一个月，再决定要不要拆。结构是长出来的，不是一次设计出来的。

## 六、CSS 与主题下载

我改外观，不是为了好看，是为了让信息分层更清楚：主页能一眼看到统计和入口，索引页的表格能扫，标题和标签有稳定的颜色。

### 我改了什么

9 个 CSS 片段，分两类：

| 片段                     | 作用范围                  | 用途                                                          |
| ------------------------ | ------------------------- | ------------------------------------------------------------- |
| `VisionJam-Homepage.css` | `cssclasses: dashboard`   | 主页背景、渐变标题、导航卡片、统计卡、条形图、callout、响应式 |
| `VisionJam-Bases.css`    | `cssclasses: bases-index` | Dataview 表格卡片化、日历视图、健康页表格例外                 |
| `Headers.css`            | 全局                      | 六级标题颜色，沿用 GitHub Theme 的配色                        |
| `Blockquote.css`         | 全局                      | 紫色渐变引用块                                                |
| `Tags.css`               | 全局                      | 标签药丸，编辑模式和阅读模式                                  |
| `Links.css`              | 全局                      | 内链、外链颜色                                                |
| `Properties.css`         | 全局                      | 属性键紫色                                                    |
| `Sidebar-Numbering.css`  | 全局                      | 大纲和文件浏览器层级编号                                      |
| `Folding-Arrows.css`     | 全局                      | 紫色折叠箭头，始终可见                                        |

两个是页面级，七个是全局/工具级。页面级的靠 `cssclasses` 触发，全局的启用就生效。

{{< figure src="sidebar-numbering.jpg" align="center" caption="Sidebar-Numbering.css：文件浏览器和大纲的层级编号。" >}}

### 设计取舍

- 不设背景图，内容区用纯色 `#1a1b2e`；
- 不用 `backdrop-filter`，Windows 上文字会糊；
- 不用 `-webkit-font-smoothing: antialiased`，它会关掉 ClearType，字变细；
- 不用纯白，深色背景上会光晕；
- 选择器尽量限定在 `.dashboard` 和 `.bases-index` 里，不污染整个界面；
- `!important` 用得多，因为 GitHub Theme 的变量会覆盖；这是取舍，不是好习惯。

还有一点：主页 CSS 依赖 DataviewJS 生成的 class（`.vj-stats`、`.vj-banner`、`.vj-bars`）。只拷 CSS 不够，要一起拷示例笔记；不然那些样式没有落点。

### 仓库里有什么

完整代码、示例笔记、Templater 模板和安装说明放在 GitHub：

**仓库地址：[visionjam/obsidian-visionjam-theme](https://github.com/visionjam/obsidian-visionjam-theme)**

仓库结构大概是：

```text
snippets/          9 个 CSS 片段
examples/          主页、索引页示例
templates/         11 个 Templater 模板
screenshots/       效果截图
themes/            GitHub Theme 副本
README.md          安装、自定义、排错
LICENSE            MIT
NOTICE.md          第三方致谢
```

主题是 GitHub Theme 1.1.6，MIT 许可。我放了副本，也放了上游链接和 LICENSE；如果你已经在用这个主题，不需要再装一遍。

### 安装步骤

1. 把 `snippets/` 里的 `.css` 复制到你的 `.obsidian/snippets/`；
2. 在 Obsidian 设置 → 外观 → CSS 片段里启用；
3. 如果用主页样式，把 `examples/` 里的示例笔记复制进去，或者在自己的笔记 frontmatter 里加 `cssclasses: dashboard`；
4. 如果用索引页样式，加 `cssclasses: bases-index`；
5. 示例里的 DataviewJS 需要 Dataview 插件；多栏 callout 需要 Simple Columns；
6. 要用 Templater 模板，看 `templates/README.md`：先装 Templater 和 Dataview，再把每个模板的 `TARGET_DIR` 改成你的目录。

### 兼容性与限制

- 适用 Obsidian 1.6+；
- 基于 GitHub Theme 1.1.6 调色；
- 主页示例需要 Dataview；
- 多栏 callout 需要 Simple Columns；
- 移动端没有逐一测试，窄屏下表格卡片化可能要再调。

如果你用别的主题，颜色和变量要改；这不是一个即插即用的完整主题，是一套叠在 GitHub Theme 上的片段。

### 许可证与致谢

- GitHub Theme：MIT，Copyright 2023 Vladimir Kidyaev，上游是 [krios2146/obsidian-theme-github](https://github.com/krios2146/obsidian-theme-github)；
- 早期的 CSS 参考过 Klaas 的 Obsidian CSS snippets 合集；公开仓库里的相关片段是我重写的，没有直接复制原代码；
- 我的 CSS 和示例用 MIT 许可，随便改，保留 LICENSE 就行。

## 参考资料

官方和社区的资料比我写得全。遇到具体问题，先去这里查：

- [Obsidian 官方中文帮助](https://obsidian.md/zh/help/)：官方中文文档，从安装、创建 vault、第一条笔记到链接、导入和同步，入门教程都在这里。
- [Obsidian 官方帮助（英文）](https://obsidian.md/help/)：英文原文，更新通常比翻译快。
- [Obsidian 官网](https://obsidian.md/)：下载 Windows / Android 客户端，查看版本更新。
- [Obsidian 中文论坛](https://forum-zh.obsidian.md/)：中文用户社区，插件、主题、同步和排障问题都能搜。
- [PKMer](https://pkmer.cn/)：中文知识管理社区，有 Obsidian、Zotero 的教程、插件和主题整理。
- [SimilarPlugins](https://plugins.semiautonomous.org)：用自然语言描述需求来搜插件，适合装插件前先比较替代品。

## 最后

这套系统不是一次搭成的。我一开始也只有几个文件夹，模板是后来加的，CSS 是后来改的，移动端工具栏也是用着用着才稳定下来。

如果你现在只能带走一件事：先把同步和每日笔记跑通。插件、CSS、模板都可以 later。不要因为看了别人的仓库，就先花一周搭一个自己用不上的系统。

工具是给你用的，不是给你供着的。如果这篇文章帮你少踩一个坑，就够了。
