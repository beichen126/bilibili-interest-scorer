"""B站视频信息抓取工具 - 命令行入口"""

import sys
import os
import argparse

# Windows GBK 控制台 UTF-8 输出支持
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 支持直接运行 python cli.py
if __name__ == "__main__" and __package__ is None:
    __package__ = "bilibili_news"
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from .scraper import BiliScraper, BiliVideo
from . import cookie_util


def print_video(v: BiliVideo, index: int = None):
    """打印单个视频信息"""
    prefix = f"[{index}] " if index is not None else ""
    print(f"{prefix}{v.short_title}")
    print(f"    BV: {v.bvid}  |  UP: {v.owner_name}")
    print(f"    播放: {v.view:_}  点赞: {v.like:_}  收藏: {v.favorite:_}  投币: {v.coin:_}  分享: {v.share:_}")
    print(f"    时长: {v.duration_str}  |  发布: {v.pubdate_str}")
    print()


def cmd_login(args):
    """登录 B站"""
    if args.password:
        phone = args.phone or input("手机号: ").strip()
        pwd = args.pwd or input("密码: ").strip()
        credential = cookie_util.login_by_password(phone, pwd)
    elif args.cookie:
        credential = cookie_util.login_by_cookie_string(args.cookie)
    elif args.manual:
        credential = cookie_util.login_by_fields()
    else:
        credential = cookie_util.login_by_qrcode()

    # 登录后验证
    if credential:
        cookie_util.check_credential(credential)


def cmd_logout(args):
    """清除登录缓存"""
    cookie_util.clear_cache()


def cmd_check(args):
    """检查登录状态"""
    credential = cookie_util.load_cache()
    if not credential:
        print("[失败] 无缓存的登录凭证")
        print("请先运行: python cli.py login")
        return

    valid = cookie_util.check_credential(credential)
    if not valid:
        print("[提示] 凭证已过期，请重新登录: python cli.py login")


def cmd_recommend(args):
    """获取个性化推荐（需登录），标记热门，补全完整数据"""
    credential = cookie_util.get_credential(auto_login=False)
    if not credential:
        print("[失败] 未登录，请先运行: python cli.py login")
        return

    scraper = BiliScraper(credential=credential)
    videos, hot_list = scraper.get_recommendations_with_hot_flag(full=True)
    hot_count = sum(1 for v in videos if v.is_hot)
    print(f"[OK] 当前热门榜共 {len(hot_list)} 条")

    print(f"\n==== 个性化推荐 (共 {len(videos)} 条, 其中 {hot_count} 条在热门) ====\n")
    for i, v in enumerate(videos, 1):
        labels = []
        if v.is_hot:
            labels.append("热门")
        if v.is_followed:
            labels.append("关注")
        tag = f"[{'/'.join(labels)}] " if labels else ""
        print(f"{tag}{v.short_title}")
        print(f"    BV: {v.bvid}  |  UP: {v.owner_name}", end="")
        if v.owner_fans:
            print(f"  |  粉丝: {v.owner_fans:_}")
        else:
            print()
        print(f"    播放: {v.view:_}  点赞: {v.like:_}  收藏: {v.favorite:_}  投币: {v.coin:_}  评论: {v.reply:_}")
        if v.tags:
            print(f"    标签: {', '.join(v.tags[:6])}")
        print(f"    时长: {v.duration_str}  |  发布: {v.pubdate_str}")
        print()

    # 自动保存
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"recommend_{ts}.json"
    scraper.save(videos, filename=filename)


def cmd_hot(args):
    """获取热门视频"""
    scraper = BiliScraper()
    videos = scraper.get_hot(pn=args.pn, ps=args.ps)
    print(f"\n==== 热门视频 (第{args.pn}页, 共 {len(videos)} 条) ====\n")
    for i, v in enumerate(videos, 1):
        print_video(v, i)

    if args.save:
        scraper.save(videos, filename=args.save)


def cmd_info(args):
    """获取单个视频详情"""
    scraper = BiliScraper()
    try:
        v = scraper.get_video_info(args.bvid)
        print(f"\n==== 视频详情 ====\n")
        print(f"标题: {v.title}")
        print(f"BV:   {v.bvid}")
        print(f"UP主: {v.owner_name} (mid: {v.owner_mid})")
        print(f"分区: {v.tname}")
        print(f"时长: {v.duration_str}")
        print(f"发布: {v.pubdate_str}")
        print(f"播放: {v.view:_}  |  点赞: {v.like:_}  |  收藏: {v.favorite:_}  |  投币: {v.coin:_}")
        print(f"分享: {v.share:_}  |  评论: {v.reply:_}  |  弹幕: {v.danmaku:_}")
        print(f"封面: {v.pic}")
        print(f"描述: {v.description[:200]}{'...' if len(v.description) > 200 else ''}")
        if v.tags:
            print(f"标签: {', '.join(v.tags[:10])}")
        print()
    except Exception as e:
        print(f"[失败] 获取视频信息出错: {e}")


def cmd_search(args):
    """搜索视频"""
    scraper = BiliScraper()
    try:
        videos = scraper.search(args.keyword, page=args.page)
        print(f"\n==== 搜索 \"{args.keyword}\" (第{args.page}页, 共 {len(videos)} 条) ====\n")
        for i, v in enumerate(videos, 1):
            print_video(v, i)
        if args.save:
            scraper.save(videos, filename=args.save)
    except Exception as e:
        print(f"[失败] 搜索出错: {e}")


def cmd_auto(args):
    """每2小时定时运行：获取个性化推荐（完整数据），保存到文件

    配合 Windows 任务计划程序使用（见 README）：
      任务计划程序 -> 创建任务 -> 触发器设为每2小时 ->
      操作设为 python cli.py auto（路径指向本目录）
    """
    credential = cookie_util.load_cache()
    if not credential:
        print("[失败] 无缓存的登录凭证，请先运行: python cli.py login")
        return 1

    # 预先检查凭证是否有效
    if not cookie_util.check_credential(credential):
        print("[失败] 登录凭证已过期，自动暂停。请重新运行: python cli.py login")
        return 1

    scraper = BiliScraper(credential=credential)
    try:
        videos, hot_list = scraper.get_recommendations_with_hot_flag(full=True)
        print(f"[OK] 个性化推荐: {len(videos)} 条 ({sum(1 for v in videos if v.is_hot)} 条在热门)")
    except Exception as e:
        print(f"[失败] 推荐获取出错: {e}")
        return 1

    # 保存
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"recommend_{ts}.json"
    scraper.save(videos, filename=filename)
    return 0


def cmd_list(args):
    """列出已保存的文件"""
    scraper = BiliScraper()
    files = scraper.list_files()
    if not files:
        print("(暂无保存的数据文件)")
        return
    print(f"\n已保存的数据文件 ({len(files)} 个):\n")
    for f in files[-20:]:  # 只显示最近20个
        path = os.path.join(scraper.data_dir, f)
        size = os.path.getsize(path)
        print(f"  {f}  ({size / 1024:.1f} KB)")


def cmd_read(args):
    """查看已保存的文件"""
    scraper = BiliScraper()
    try:
        data = json.loads(open(os.path.join(scraper.data_dir, args.file), encoding="utf-8").read())
        videos_data = data.get("videos", data.get("results", {}).get("recommend", data.get("results", {}).get("hot", [])))
        if isinstance(videos_data, list) and videos_data:
            print(f"\n==== {args.file} (共 {len(videos_data)} 条) ====\n")
            for i, v in enumerate(videos_data[:20], 1):
                bv = BiliVideo(**v) if isinstance(v, dict) else v
                print_video(bv, i)
            if len(videos_data) > 20:
                print(f"... 还有 {len(videos_data) - 20} 条\n")
        else:
            # 尝试新格式
            print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
    except FileNotFoundError:
        print(f"[失败] 文件不存在: {args.file}")
        print(f"数据目录: {scraper.data_dir}")
    except Exception as e:
        print(f"[失败] 读取出错: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="B站视频信息抓取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python cli.py login                         # 二维码登录（推荐）
  python cli.py login --password              # 手机号+密码登录
  python cli.py login --password --phone 138xxx --pwd mypass
  python cli.py login --cookie "SESSDATA=..."
  python cli.py check                         # 检查登录状态
  python cli.py recommend                     # 个性化推荐（完整数据）
  python cli.py hot                           # 热门视频
  python cli.py info BV1GJ41177UF             # 视频详情
  python cli.py search 新闻                   # 搜索视频
  python cli.py auto                          # 定时运行（配合任务计划程序）
  python cli.py list                          # 列出已保存文件
        """
    )

    sub = parser.add_subparsers(dest="command", help="可用命令")

    # login
    p_login = sub.add_parser("login", help="登录 B站")
    p_login.add_argument("--password", action="store_true", help="使用手机号+密码登录")
    p_login.add_argument("--phone", help="手机号（配合 --password 使用）")
    p_login.add_argument("--pwd", help="密码（配合 --password 使用）")
    p_login.add_argument("--cookie", help="从浏览器复制的 Cookie 字符串")
    p_login.add_argument("--manual", action="store_true", help="手动输入 cookie 字段")
    p_login.set_defaults(func=cmd_login)

    # logout
    p_logout = sub.add_parser("logout", help="清除登录缓存")
    p_logout.set_defaults(func=cmd_logout)

    # check
    p_check = sub.add_parser("check", help="检查登录状态")
    p_check.set_defaults(func=cmd_check)

    # recommend
    p_rec = sub.add_parser("recommend", help="获取首页个性化推荐（完整数据：粉丝数/标签/互动统计/热门比对）")
    p_rec.set_defaults(func=cmd_recommend)

    # hot
    p_hot = sub.add_parser("hot", help="获取热门视频")
    p_hot.add_argument("--pn", type=int, default=1, help="页码 (默认: 1)")
    p_hot.add_argument("--ps", type=int, default=20, help="每页数量 (默认: 20)")
    p_hot.add_argument("--save", help="保存到文件")
    p_hot.set_defaults(func=cmd_hot)

    # info
    p_info = sub.add_parser("info", help="获取单个视频详情")
    p_info.add_argument("bvid", help="BV 号 (如 BV1GJ41177UF)")
    p_info.set_defaults(func=cmd_info)

    # search
    p_search = sub.add_parser("search", help="搜索视频")
    p_search.add_argument("keyword", help="搜索关键词")
    p_search.add_argument("--page", type=int, default=1, help="页码 (默认: 1)")
    p_search.add_argument("--save", help="保存到文件")
    p_search.set_defaults(func=cmd_search)

    # auto
    p_auto = sub.add_parser("auto", help="定时运行：个性化推荐（完整数据），配合任务计划程序使用")
    p_auto.set_defaults(func=cmd_auto)

    # list
    sub.add_parser("list", help="列出已保存的数据文件").set_defaults(func=cmd_list)

    # read
    p_read = sub.add_parser("read", help="查看已保存的数据文件")
    p_read.add_argument("file", help="文件名")
    p_read.set_defaults(func=cmd_read)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return 1

    try:
        ret = args.func(args)
        return ret if isinstance(ret, int) else 0
    except KeyboardInterrupt:
        print("\n[提示] 已取消")
        return 1
    except Exception as e:
        print(f"[失败] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
