# B站工具箱

<p align="center">
  <b>🎯 B站个性化推荐视频抓取 + AI 兴趣匹配评分</b><br>
  在信息洪流中精准定位你真正想看的内容
</p>

---

## 目录

- [功能概览](#功能概览)
- [数据流架构](#数据流架构)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [GUI 界面说明](#gui-界面说明)
- [命令行用法](#命令行用法)
- [评分算法详解](#评分算法详解)
- [项目结构](#项目结构)
- [数据存储](#数据存储)
- [编译为可执行文件](#编译为可执行文件)
- [常见问题](#常见问题)

---

## 功能概览

### 视频获取（4种方式）

| 方式 | 入口 | 需登录 | 说明 |
|------|------|--------|------|
| 📋 **个性化推荐** | GUI"获取推荐" / CLI `recommend` | ✅ 是 | 抓取B站首页推荐流，同时对比热门榜标注"🔥热门"，检查关注状态标注"关注"。GUI 可勾选"补全完整数据"获取标签、完整互动统计、简介、分区和 UP 主粉丝数；CLI 始终获取完整数据 |
| 🔥 **热门榜** | GUI"热门视频" / CLI `hot` | ❌ 否 | 获取全站热门视频。CLI 支持 `--pn`/`--ps` 翻页；GUI 固定第1页50条 |
| 🔍 **搜索** | GUI 搜索框 / CLI `search 关键词` | ❌ 否 | 关键词搜索B站视频。CLI 支持 `--page` 分页；GUI 固定第1页 |
| 📹 **BV 查详情** | GUI 输入 BV 号 / CLI `info BV号` | ❌ 否 | 按 BV 号精确查询单个视频的完整信息（含标签和全量互动数据） |

### AI 评分 & 筛选

| 功能 | 描述 |
|------|------|
| 🤖 **AI 兴趣评分** | 基于 DeepSeek API，根据自定义兴趣画像（提示词）对每个视频打分 0-100 |
| 📊 **综合排序** | 融合 AI 兴趣分（60%）+ 量化指标分（40%），关注作者额外加分，<60 分自动过滤 |
| 📝 **自定义提示词** | 在 GUI "设置"页编辑你的兴趣画像，精准定义感兴趣/不感兴趣的内容 |

### 其他

| 功能 | 描述 |
|------|------|
| 🔐 **B站登录** | 支持二维码扫码 / 手机号密码 / Cookie 字符串 / 手动输入四种方式，凭证自动缓存复用 |
| 🎛️ **统一 GUI** | Tkinter 四标签页图形界面，所有操作可视化管理，无需命令行 |
| 📦 **一键打包** | PyInstaller 编译为单个 exe 文件，方便分发使用 |

---

## 数据流架构

```
┌─────────────────────────────────────────────────┐
│                  B站工具箱 GUI                    │
│             (gui.py — Tkinter 界面)              │
│                                                  │
│  ┌──────────────┐  ┌──────────────┐             │
│  │  首页推荐     │  │  AI 评分     │             │
│  │  · 扫码登录   │  │  · API Key   │             │
│  │  · 获取推荐   │  │  · 批量评分   │             │
│  │  · 搜索/详情  │  │  · 结果浏览   │             │
│  └──────┬───────┘  └──────┬───────┘             │
│         │                 │                      │
│  ┌──────┴───────┐  ┌──────┴───────┐             │
│  │ bilibili_news │  │ bilibili_judge│            │
│  │ · scraper.py  │  │ · judger.py   │            │
│  │ · cookie_util │  │ · deepseek.py │            │
│  └──────┬───────┘  └──────┬───────┘             │
│         │                 │                      │
│         ▼                 ▼                      │
│  ┌──────────────────────────────────────┐        │
│  │        ~/.bilibili_toolbox/          │        │
│  │  · config.json       (API Key)       │        │
│  │  · credential_cache  (登录凭证)      │        │
│  │  · prompts/          (评分提示词)    │        │
│  │  · news_data/        (视频数据JSON)  │        │
│  │  · judge_data/       (评分结果JSON)  │        │
│  └──────────────────────────────────────┘        │
│         ▲                 │                      │
│         │     JSON 传递   │                      │
│         └─────────────────┘                      │
└─────────────────────────────────────────────────┘

外部服务:
  ┌──────────────┐     ┌──────────────────┐
  │  B站 API      │     │  DeepSeek API    │
  │  · 推荐/热门  │     │  · 兴趣评分 AI  │
  │  · 视频详情   │     │  · v4-flash 模型 │
  │  · 用户信息   │     │  · 并发 5 线程  │
  └──────────────┘     └──────────────────┘
```

---

## 环境要求

| 组件 | 版本要求 |
|------|---------|
| Python | 3.8+ |
| pip | 20.0+ |
| 网络 | 需能访问 `api.bilibili.com` 和 `api.deepseek.com` |
| B站账号 | 推荐功能需要登录；热门/搜索/详情无需登录 |
| DeepSeek API Key | AI 评分功能需要（可到 [platform.deepseek.com](https://platform.deepseek.com) 注册获取） |

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

依赖详情：
- `bilibili-api-python` — B站非官方 API SDK（登录、推荐、视频信息等）
- `requests` — DeepSeek API HTTP 调用

### 2. 启动 GUI

```bash
python gui.py
```

### 3. 登录 B站

在 GUI "首页推荐" 标签页中点击 **二维码登录**：
1. 程序自动生成二维码图片并打开
2. 用 B站手机客户端扫描二维码
3. 在手机上确认登录
4. 登录成功后凭证自动缓存，下次启动无需重新登录

### 4. 获取推荐视频

点击 **获取推荐**，程序将：
1. 拉取首页个性化推荐列表
2. 对比当前热门榜，标注热门视频
3. 检查关注状态，标注已关注 UP 主
4. 如果勾选"补全完整数据"，额外获取标签、完整互动统计和 UP 主粉丝数
5. 自动保存为 JSON 文件

### 5. AI 评分（可选但推荐）

1. 切换到 "AI评分" 标签页
2. 点击 "从当前推荐加载 (Tab1)" 载入视频列表
3. 设置 DeepSeek API Key（首次使用需要）

   ```bash
   # 也可通过命令行设置
   cd bilibili_judge
   python cli.py config --api-key sk-你的DeepSeek密钥
   ```

4. 切换到 "设置" 标签页，编辑评分提示词（你的兴趣画像）
5. 回到 "AI评分" 标签页，点击 **开始评分**

评分完成后，结果按综合分降序排列，双击任一视频可在浏览器中打开播放。

---

## GUI 界面说明

主窗口 `1200×820`，分为顶部内容区（Notebook 四标签页）和底部日志面板。所有网络操作均在后台线程执行，UI 不会卡死。日志面板实时显示 `print()` 输出，同时写入 `~/.bilibili_toolbox/app.log`。

### 标签页一：首页推荐

```
┌─ 登录管理 ──────────────────────────────────────┐
│ [二维码登录]  [检查登录]  [退出登录]   已登录: xxx  │
├─ 视频获取 ──────────────────────────────────────┤
│ [获取推荐] [热门视频]                             │
│ 搜索: [___关键词___] [搜索]  BV: [________] [查详情] │
│ ☑ 补全完整数据（标签/收藏/投币/粉丝数等）           │
├─ 视频列表 ──────────────────────────────────────┤
│ BVID │ 标题 │ UP主 │ 播放 │ 点赞 │ 时间 │ 时长 │ 标签 │ 标记 │
│ ...                                            │
├─────────────────────────────────────────────────┤
│ [发送到 AI 评分]                    共 xx 条视频   │
└─────────────────────────────────────────────────┘
```

**交互说明**：
- **双击视频行**：弹出详情窗口，展示完整信息 —— 标题、BVID、UP主、分区、时长、发布时间、全部互动数据（播放/点赞/收藏/投币/分享/评论/弹幕）、UP主粉丝数、热门/关注标记、标签列表、视频简介。如果该视频已经过 AI 评分，还会显示兴趣分和综合分
- **点击列表头**：按该列排序（升序/降序切换）
- **Ctrl/Shift 多选**：选中多条视频后点击"发送到 AI 评分"，批量进入评分流程
- **补全完整数据**：勾选后获取推荐时会额外请求每个视频的详细信息和标签（耗时更长，数据更全）
- **自动保存**：每次获取视频后自动保存为 JSON 到 `news_data/` 目录

### 标签页二：AI评分

```
┌─ DeepSeek 配置 ──────────────────────────────────┐
│ API Key: [************************]  [保存] [显示]│
├─ 评分操作 ───────────────────────────────────────┤
│ 数据文件: [▼ recommend_20260503_171440.json]      │
│                  [刷新列表] [加载]                  │
│ [开始评分] [从当前推荐加载(Tab1)] [查看历史评分]     │
├─ 评分结果 ───────────────────────────────────────┤
│ 标题 │ UP主 │ 兴趣分 │ 综合分 │ 播放 │ UP粉丝 │ 时间 │ 时长 │ 标记 │
│ ...                                             │
├──────────────────────────────────────────────────┤
│                                    共 xx 条      │
└──────────────────────────────────────────────────┘
```

**交互说明**：
- **双击结果行**：自动调用系统浏览器打开该视频的 B站播放页面（`https://www.bilibili.com/video/{bvid}`）
- **从当前推荐加载**：直接使用标签页一中已获取的视频列表，无需通过文件中转
- **数据文件下拉框**：列出 `news_data/` 和 `judge_data/` 中所有 JSON 文件，选择一个后点"加载"即可读入
- **查看历史评分**：在日志面板列出最近 10 条评分结果文件
- **API Key 显示/隐藏**：默认用 `*` 遮罩，点击"显示"可查看明文，再次点击恢复遮罩
- **评分配额**：GUI 默认最多评分 50 条，防止 API 费用过高
- **自动保存**：评分完成后结果自动保存到 `judge_data/`

### 标签页三：数据浏览

```
┌─ 数据文件 ──────────────┐  ┌─ 内容预览 ────────────────────┐
│ recommend_0514_1200.json │  │ {                              │
│   (28.5 KB)              │  │   "count": 24,                 │
│ bilibili_0514_1330.json  │  │   "timestamp": "2026-05-14...",│
│   (15.2 KB)              │  │   "videos": [                  │
│ judged_0514_1400.json    │  │     {                          │
│   (42.1 KB)              │  │       "bvid": "BV1xx...",      │
│ ...                      │  │       "title": "...",          │
├──────────────────────────┤  │       ...                      │
│ [刷新]                   │  │     }                          │
└──────────────────────────┘  └────────────────────────────────┘
```

**交互说明**：
- **左侧文件列表**：显示 `news_data/` 和 `judge_data/` 中所有 JSON 文件，含文件大小，按时间倒序
- **右侧预览**：点击文件名后在右侧显示格式化 JSON 内容（最长 5000 字符），方便快速浏览
- **刷新按钮**：手动刷新文件列表

### 标签页四：设置

评分提示词编辑器 —— 这是控制 AI 评分行为的核心配置。

**交互说明**：
- **当前状态指示**：顶部文字提示当前使用的是"默认提示词"还是"自定义提示词"
- **编辑区**：直接编辑 Markdown 格式的评分提示词，包含三个优先级的兴趣领域、评分标准、加减分项
- **保存自定义提示词**：将编辑内容保存为 `custom_prompt.md`，下次评分自动使用
- **恢复默认提示词**：删除自定义提示词，回退到项目内置的 `interest_scoring_prompt.md` 模板
- **重新加载**：放弃未保存的修改，重新读取当前生效的提示词

---

## 命令行用法

如果你偏好命令行，每个模块都有独立的 CLI 入口。

### bilibili_news — 视频抓取

```bash
cd bilibili_news
pip install bilibili-api-python   # 首次安装依赖

# 登录 (4种方式)
python cli.py login                          # 二维码登录（推荐）
python cli.py login --password               # 手机号+密码登录
python cli.py login --password --phone 138xxx --pwd mypass
python cli.py login --cookie "SESSDATA=...;bili_jct=..."
python cli.py login --manual                 # 手动输入 Cookie 各字段

# 视频获取
python cli.py recommend                      # 个性化推荐（自动补全数据+保存）
python cli.py hot                            # 热门视频 (前20条)
python cli.py hot --pn 2 --ps 50             # 热门第2页，50条
python cli.py info BV1GJ41177UF              # 单视频详情
python cli.py search 考研                     # 搜索视频
python cli.py search 考研 --page 2            # 搜索第2页

# 凭证管理
python cli.py check                          # 检查登录状态
python cli.py logout                         # 清除登录缓存

# 数据管理
python cli.py list                           # 列出已保存的数据文件
python cli.py read recommend_20260503_171440.json  # 查看文件内容

# 定时运行（配合 Windows 任务计划程序）
python cli.py auto                           # 每2小时自动抓取推荐
```

或使用模块方式调用：
```bash
python -m bilibili_news recommend
python -m bilibili_news hot
```

### bilibili_judge — AI 评分

```bash
cd bilibili_judge
pip install requests             # 首次安装依赖
pip install bilibili-api-python  # 如需检查关注状态

# 配置 API Key
python cli.py config --api-key sk-你的DeepSeek密钥
python cli.py config                          # 查看当前配置

# 评分
python cli.py judge ../bilibili_news/data/recommend_xxx.json
python cli.py judge recommend_xxx.json --top 10       # 只看前10
python cli.py judge --bvid BV1xx4455yyy               # 评分单个视频
python cli.py judge file.json --api-key sk-xxx        # 临时指定API Key

# 查看历史
python cli.py list                           # 列出历史评分结果
```

### DeepSeek API 诊断

如果评分功能工作不正常，使用诊断工具排查：

```bash
cd bilibili_judge
python debug_deepseek.py                     # 测试连通性
python debug_deepseek.py --verbose           # 查看完整请求/响应
python debug_deepseek.py --api-key sk-xxx    # 临时指定 Key
```

---

## 评分算法详解

每一条视频的**综合分**由三部分组成：

```
综合分 = DeepSeek兴趣分 × 0.6 + 量化分 × 0.4 + 关注加分（上限100）
```

### ① 兴趣分 — DeepSeek AI 评分（权重 60%）

**调用流程**：
1. 构建 user prompt：将视频的标题、UP主、标签/分区、简介、播放量、时长按模板拼接
2. 以评分提示词（"设置"页编辑的兴趣画像）作为 system prompt
3. 调用 DeepSeek Chat API（模型 `deepseek-v4-flash`），temperature=0.0
4. 模型返回纯数字 0-100，程序解析后作为 `interest_score`

**并发策略**：
- 使用 `ThreadPoolExecutor(max_workers=5)` 同时分析 5 条视频
- 每条视频独立请求，最多重试 3 次（间隔 1 秒）
- 请求超时 90 秒，超时或失败则该条视频默认得 50 分
- 分数解析支持纯数字、正则提取、中文数字（如"八十五"→85）

**提示词影响**：
评分提示词决定了 AI 的打分倾向。你在提示词中定义的"第一优先级""第二优先级""第三优先级"兴趣领域，以及加分项（深度长视频、多领域交叉）和减分项（营销号、纯娱乐八卦），会直接影响每条视频的得分。

### ② 量化分 — 客观数据指标（权重 40%）

不需要 API 调用，直接基于视频的客观统计数据计算。满分为 100，由三个子维度相加：

**子维度 A：互动质量（满分 40）**

计算各项互动率（互动数 / 播放量），每项达到满分阈值后封顶：

| 指标 | 权重 | 满分阈值 | 公式 |
|------|------|---------|------|
| 点赞率 | 12 分 | 5% | `min(点赞数/播放量/0.05, 1.0) × 12` |
| 收藏率 | 10 分 | 3% | `min(收藏数/播放量/0.03, 1.0) × 10` |
| 投币率 | 8 分 | 2% | `min(投币数/播放量/0.02, 1.0) × 8` |
| 弹幕率 | 5 分 | 2% | `min(弹幕数/播放量/0.02, 1.0) × 5` |
| 分享率 | 5 分 | 1% | `min(分享数/播放量/0.01, 1.0) × 5` |

> 例：一个 10 万播放的视频，点赞 6000（6%），收藏 4000（4%），投币 1500（1.5%），弹幕 3000（3%），分享 500（0.5%）
> 互动质量 = 12（点赞率封顶）+ 10（收藏率封顶）+ 6（投币率 1.5%/2%×8）+ 5（弹幕率封顶）+ 2.5（分享率 0.5%/1%×5）= **35.5 分**

**子维度 B：热度规模（满分 30）**

| 播放量 | 得分 |
|--------|------|
| ≥ 50万 | 30 |
| ≥ 10万 | 20 |
| ≥ 1万 | 10 |
| < 1万 | 0 |

**子维度 C：作者影响力（满分 30）**

| UP主粉丝数 | 得分 |
|-----------|------|
| ≥ 100万 | 30 |
| ≥ 10万 | 25 |
| ≥ 1万 | 15 |
| ≥ 1000 | 5 |
| < 1000 | 0 |

**量化分 = 互动质量 + 热度规模 + 作者影响力**（三项直接相加，范围 0–100）

### ③ 关注加成

如果当前登录账号已关注该视频的 UP 主，额外 **+5 分**（总分上限 100）。

此功能需要登录态。评分时会自动获取你的关注列表，将视频作者的 `owner_mid` 与关注列表比对。

### 过滤规则（评分后）

以下视频会被自动排除，不进入最终结果：

| 条件 | 处理 |
|------|------|
| 时长 < 3 分钟（180秒） | 排除 |
| 综合分 < 60 | 排除 |
| **热门视频**（`is_hot=True`） | **强制保留**，不受以上限制 |

> 热门视频的判定：在获取推荐列表时，同步拉取全站热门榜，将推荐视频的 BVID 与热门榜交叉比对。

### 最终排序

评分结果按 **综合分降序** 排列，得分最高的视频排在最前。

---

## 项目结构

```
.
├── gui.py                        # 🖥️ 图形界面主入口 (Tkinter 四标签页)
├── config.py                     # ⚙️ 集中配置管理
│   · API Key 读写（环境变量 > 配置文件 > 运行时）
│   · 提示词管理（默认/自定义）
│   · 数据目录自动创建
│   · 配置目录优先级: 环境变量 > ~/.bilibili_toolbox > ./.bilibili_toolbox
│
├── build_exe.bat                 # 📦 PyInstaller 打包脚本 → dist/B站工具箱.exe
├── requirements.txt              # 📋 pip 依赖清单
├── README.md                     # 📖 本文件
│
├── bilibili_news/                # 📡 视频抓取模块
│   ├── __init__.py               #     公开接口: BiliScraper, BiliVideo
│   ├── __main__.py               #     支持 python -m bilibili_news
│   ├── cli.py                    #     CLI 命令行入口 (10 个子命令)
│   ├── scraper.py                #     核心抓取类
│   │   · BiliVideo (dataclass): 22个字段的视频数据结构
│   │   · BiliScraper: 推荐/热门/搜索/详情 + 定时运行
│   │   · 异步并发补全完整数据 (asyncio)
│   │   · 关注列表批量检查
│   ├── cookie_util.py            #     登录凭证管理
│   │   · 4种登录方式 (二维码/密码/Cookie字符串/手动)
│   │   · Geetest 验证码自动处理
│   │   · 凭证缓存与自动恢复
│   ├── run.bat                   #     Windows 快捷启动
│   └── setup.bat                 #     环境安装引导
│
├── bilibili_judge/               # 🤖 AI 评分模块
│   ├── __init__.py               #     公开接口: judge_batch, save_results
│   ├── __main__.py               #     支持 python -m bilibili_judge
│   ├── cli.py                    #     CLI 命令行入口 (3 个子命令)
│   ├── judger.py                 #     评分引擎
│   │   · 综合评分公式 (兴趣分×60% + 量化分×40%)
│   │   · 智能过滤 (时长/低分/热门保护)
│   │   · 关注状态加分
│   │   · 结果排序与保存
│   ├── deepseek.py               #     DeepSeek API 调用封装
│   │   · 5线程并发分析
│   │   · 3次自动重试
│   │   · 鲁棒的分数解析 (数字/正则/中文数字)
│   ├── debug_deepseek.py         #     API 诊断工具
│   ├── prompts/                  #     评分提示词模板
│   │   └── interest_scoring_prompt.md  默认评分模板
│   ├── run.bat                   #     Windows 快捷启动
│   └── setup.bat                 #     环境安装引导
│
└── dist/                         # 🎁 编译输出目录 (gitignore)
    └── B站工具箱.exe
```

---

## 数据存储

所有用户数据和配置统一存放在 `~/.bilibili_toolbox/`：

```
~/.bilibili_toolbox/
├── config.json                        # 配置文件 (API Key, 模型名称)
├── credential_cache.json              # B站登录凭证 (SESSDATA等, 敏感)
├── app.log                            # 运行日志 (带时间戳)
│
├── prompts/                           # 评分提示词目录
│   ├── interest_scoring_prompt.md     #   默认模板 (只读, 来自项目)
│   └── custom_prompt.md               #   用户自定义 (编辑后生效)
│
├── news_data/                         # 抓取的视频数据
│   ├── recommend_20260503_171440.json
│   ├── bilibili_20260503_184715.json
│   └── ...
│
└── judge_data/                        # 评分结果
    ├── judged_20260503_192030.json
    └── ...
```

**配置目录优先级**（`config.py` 自动选择）：
1. 环境变量 `BILI_TOOLBOX_CONFIG_DIR`
2. 用户主目录 `~/.bilibili_toolbox`（默认）
3. 当前目录 `./.bilibili_toolbox`（降级方案）

---

## 编译为可执行文件

将整个项目打包为单个 Windows exe，无需安装 Python 即可运行：

```bash
pip install pyinstaller
build_exe.bat
```

输出文件：`dist/B站工具箱.exe`（单文件，约 50MB，无控制台窗口）

打包参数说明：
- `--onefile` — 单文件输出
- `--noconsole` — 无控制台窗口（纯 GUI）
- `--add-data` — 内嵌 bilibili_news 和 bilibili_judge 模块
- `--collect-all bilibili_api` — 完整打包 bilibili-api SDK
- `--hidden-import` — 确保动态导入的模块被包含

> **注意**：PyInstaller 打包的 exe 启动较慢（5-15 秒），因为需要解压 Python 运行时。这是正常现象。

---

## 常见问题

### Q: 获取推荐时提示"需要登录"？

推荐列表是 B站个性化接口，需要登录凭证。点击"二维码登录"完成登录后再试。

### Q: 登录二维码过期了怎么办？

二维码有效期为约 2 分钟。过期后程序会自动提示，重新点击"二维码登录"即可。

### Q: 提示"API Key 无效"？

检查三点：
1. Key 格式是否正确（以 `sk-` 开头）
2. DeepSeek 账户是否有余额
3. 网络是否能访问 `api.deepseek.com`（可能需要代理）

运行诊断工具排查：`python bilibili_judge/debug_deepseek.py`

### Q: 如何让评分更符合我的口味？

切换到 "设置" 标签页，编辑评分提示词。核心是修改 **用户兴趣画像** 部分：
- 填写你感兴趣的主题、关键词、内容形式
- 设置评分标准示例，让 AI 更准确理解你的偏好
- 保存后立即生效，下次评分使用新提示词

### Q: 评分速度慢？

默认并发 5 线程调用 DeepSeek API，实际耗时取决于 API 响应速度。如果视频数量多，建议：
- 减少评分数量（GUI 默认 50 条上限）
- 使用更快的模型（修改 `deepseek.py` 中的 `DEFAULT_MODEL`）

### Q: Cookie 凭证安全吗？

凭证存储在 `credential_cache.json`（明文 JSON）。该文件已被 `.gitignore` 排除，不会被上传到 GitHub。建议不要将凭证文件分享给他人。

---

## 开发相关

### 模块调用关系

```
gui.py
 ├── bilibili_news.scraper.BiliScraper   (视频抓取)
 ├── bilibili_news.cookie_util           (登录/凭证)
 ├── bilibili_judge.judger               (评分引擎)
 │    └── bilibili_judge.deepseek        (API 调用)
 └── config                              (配置管理)
```

### 跨模块数据传递

模块间通过 JSON 文件传递数据，而非直接导入：

```
bilibili_news (scraper.save) → news_data/*.json → bilibili_judge (judger)
bilibili_judge (save_results) → judge_data/*.json → GUI 数据浏览
```

### 线程模型

- GUI 所有网络操作在后台 `threading.Thread` 中运行
- 表格刷新通过 `widget.after(0, callback)` 调度回主线程
- DeepSeek 并发调用使用 `ThreadPoolExecutor(max_workers=5)`

---

## License

[MIT License](https://opensource.org/licenses/MIT)
