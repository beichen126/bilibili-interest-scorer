# B站工具箱

B站个性化推荐视频抓取 + AI兴趣匹配评分，帮助你在海量视频中发现真正感兴趣的内容。

## 功能

- **首页推荐抓取** — 获取B站个性化推荐视频列表，保存为 JSON
- **AI兴趣评分** — 基于 DeepSeek API，根据自定义兴趣画像对视频打分（0-100）
- **综合排序** — 结合AI评分与量化指标（播放/点赞/弹幕等），精准筛选
- **统一GUI** — Tkinter图形界面，三标签页操作，无需命令行

## 依赖

| 模块 | 依赖 |
|------|------|
| 核心 | Python 3.8+ |
| bilibili_news | `bilibili-api-python` |
| bilibili_judge | `requests` |
| GUI | Tkinter（Python 内置） |

## 快速开始

### 1. 安装依赖

```bash
pip install bilibili-api-python requests
```

### 2. 运行 GUI

```bash
python gui.py
```

### 3. 登录B站

在 GUI "首页推荐" 标签页中点击 **扫码登录**，用B站手机客户端扫描二维码完成登录。

### 4. 抓取推荐视频

登录后点击 **获取推荐**，自动拉取首页个性化推荐视频列表。

### 5. AI评分（可选）

切换到 "AI评分" 标签页，设置 DeepSeek API Key：

```bash
# 也可通过命令行设置
cd bilibili_judge
python cli.py config --api-key sk-你的DeepSeek密钥
```

编辑评分提示词（你的兴趣画像）后，点击 **开始评分**。

## 命令行用法

### bilibili_news — 视频抓取

```bash
cd bilibili_news
python cli.py login              # 扫码登录
python cli.py recommend          # 获取个性化推荐
python cli.py hot                # 热门视频
python cli.py info BVxxxxxxxxxx  # 视频详情
python cli.py search 关键词       # 搜索视频
```

### bilibili_judge — AI评分

```bash
cd bilibili_judge
python cli.py config --api-key sk-xxx   # 设置API Key
python cli.py judge ../bilibili_news/data/recommend_xxx.json  # 批量评分
python cli.py list                      # 查看历史评分
```

## 项目结构

```
.
├── gui.py              # 图形界面主入口
├── config.py           # 集中配置管理（API Key、路径等）
├── build_exe.bat       # PyInstaller 打包脚本
├── bilibili_news/       # 视频抓取模块
│   ├── scraper.py      # 核心抓取类（BiliScraper）
│   ├── cookie_util.py  # 登录凭证管理（扫码/密码/Cookie）
│   └── cli.py          # 命令行入口
├── bilibili_judge/      # AI评分模块
│   ├── judger.py       # 评分引擎
│   ├── deepseek.py     # DeepSeek API 调用
│   ├── prompts/        # 评分提示词模板
│   └── cli.py          # 命令行入口
└── dist/               # 编译输出（exe）
```

## 数据存储

所有数据和配置存储在 `~/.bilibili_toolbox/` 目录下：

```
~/.bilibili_toolbox/
├── config.json              # API Key + 设置
├── credential_cache.json    # B站登录Cookie
├── prompts/                 # 评分提示词
├── news_data/               # 抓取的视频数据
├── judge_data/              # 评分结果
└── app.log                  # 运行日志
```

## 编译为 exe

```bash
pip install pyinstaller
build_exe.bat
```

输出：`dist/B站工具箱.exe`（无控制台窗口）

## License

MIT
