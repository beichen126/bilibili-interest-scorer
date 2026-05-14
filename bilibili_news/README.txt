bilibili_news - B站个性化推荐视频抓取工具
===========================================

基于 bilibili-api-python，自动抓取已登录用户的首页个性化推荐视频。
设计用于定时任务（每2小时运行一次），登录一次后凭证自动缓存。

特点:
  - 登录态个性化推荐（二维码 / 手机号+密码 / 粘贴Cookie）
  - 自动比对热门榜，标记推荐视频是否也在热门上
  - 完整数据：标题、BV号、B站链接、UP主名/ID/粉丝数、
    播放/点赞/收藏/投币/评论/弹幕、时长、发布时间、
    封面图、分区、描述、标签、是否热门
  - 自动保存 JSON（命名带时间戳不覆盖）
  - 缓存登录凭证，定时运行无需重复登录
  - 凭证过期自动暂停，不会空跑

使用方式
--------
  首次登录（三选一）:
    python cli.py login                         # 二维码登录（推荐）
    python cli.py login --password              # 手机号+密码登录
    python cli.py login --cookie "SESSDATA=..." # 粘贴 Cookie

  获取推荐:
    python cli.py recommend                     # 基础数据
    python cli.py recommend --full              # 完整数据（含收藏/投币/评论/标签/粉丝数）

  定时运行（配合任务计划程序）:
    python cli.py auto                          # 完整模式，自动保存，退出

  其他:
    python cli.py check                         # 检查登录状态
    python cli.py hot                           # 全站热门视频
    python cli.py list                          # 列出已保存的 JSON 文件
    python cli.py read 文件名.json              # 查看保存内容

  python -m bilibili_news recommend             # 模块方式运行
  双击 run.bat 然后输入命令

登录凭证过期处理
----------------
  auto 命令启动时会自动检查凭证有效性:
    - 无缓存凭证 -> 提示登录，自动退出
    - 凭证已过期 -> 提示重新登录，自动退出
    - 凭证有效 -> 正常抓取

  不会在凭证失效后空跑或报错。

设置每2小时自动运行（Windows 任务计划程序）
---------------------------------------------
  1. 按 Win+R，输入 taskschd.msc 回车
  2. 右侧"创建基本任务"
  3. 名称: B站推荐抓取
  4. 触发器: 每天 -> 开始时间 08:00 -> 每2小时发生一次 -> 持续时间1天
  5. 操作: 启动程序
      - 程序或脚本: python
      - 添加参数: cli.py auto
      - 起始于: F:\information_technology\bilibili_news
  6. 完成

  每次运行自动保存到 data/recommend_YYYYMMDD_HHMMSS.json
  每2小时 30 条，5 次共 150 条

数据文件字段
------------
  bvid         视频 BV 号
  url          B站视频链接
  title        标题
  owner_name   UP主昵称
  owner_mid    UP主用户ID
  owner_fans   UP主粉丝数
  view         播放量
  like         点赞数
  favorite     收藏数
  coin         投币数
  share        转发数
  reply        评论数
  danmaku      弹幕数
  duration     时长（秒）
  pubdate      发布时间（Unix时间戳）
  pic          封面图URL
  tname        分区名
  description  视频简介
  tags         标签列表
  is_hot       是否同时在热门榜上

首次安装
--------
  pip install bilibili-api-python
  python cli.py login
  或直接运行 setup.bat

文件结构
--------
  bilibili_news/
    ├── __init__.py         # BiliScraper, BiliVideo
    ├── __main__.py         # python -m bilibili_news
    ├── cli.py              # 命令行入口
    ├── scraper.py          # 核心抓取引擎
    ├── cookie_util.py      # 登录凭证管理
    ├── run.bat             # 一键运行
    ├── setup.bat           # 环境安装
    ├── README.txt
    ├── credential_cache.json   # 缓存登录凭证（自动生成）
    └── data/                   # JSON 数据输出目录
