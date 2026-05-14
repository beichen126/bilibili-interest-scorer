"""B站视频评分筛选工具 - 命令行入口"""

import sys
import os
import argparse
import json

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

if __name__ == "__main__" and __package__ is None:
    __package__ = "bilibili_judge"
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from .judger import judge_batch, save_results, list_results
from . import deepseek
import config


def _load_credential():
    """从缓存加载 B站登录凭证"""
    cookies_path = config.get_cookies_path()
    if not os.path.isfile(cookies_path):
        return None
    try:
        from bilibili_api import Credential
        with open(cookies_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data.get("sessdata") or not data.get("bili_jct"):
            return None
        return Credential(
            sessdata=data["sessdata"],
            bili_jct=data["bili_jct"],
            buvid3=data.get("buvid3", ""),
            buvid4=data.get("buvid4", ""),
            dedeuserid=data.get("dedeuserid", ""),
            ac_time_value=data.get("ac_time_value", ""),
        )
    except Exception:
        return None


def print_video(v: dict, index: int = None):
    """打印单个视频评分结果"""
    prefix = f"[{index}] " if index is not None else ""
    tags = []
    if v.get("is_followed"):
        tags.append("关注")
    if v.get("is_hot"):
        tags.append("热门")
    tag_str = f"[{'/'.join(tags)}] " if tags else ""

    print(f"{prefix}{tag_str}{v.get('title', '')}")
    print(f"    BV: {v.get('bvid', '')}  |  UP: {v.get('owner_name', '')}")
    print(f"    兴趣: {v.get('interest_score', 0):.0f}分  |  综合: {v.get('total_score', 0):.0f}分  |  UP粉丝: {v.get('owner_fans', 0):_}")
    if v.get("duration", 0):
        m, s = divmod(v["duration"], 60)
        h, m = divmod(m, 60)
        dur = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
        print(f"    时长: {dur}  |  播放: {v.get('view', 0):_}  点赞: {v.get('like', 0):_}")
    print()


def cmd_judge(args):
    """对视频列表进行评分"""
    credential = _load_credential()

    # 读取视频数据
    videos = []
    if args.file:
        filepath = args.file
        if not os.path.isfile(filepath):
            alt = os.path.join(config.get_news_data_dir(), filepath)
            if os.path.isfile(alt):
                filepath = alt
            else:
                print(f"[失败] 文件不存在: {filepath}")
                return
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)
        videos = raw.get("videos", raw.get("results", raw.get("recommend", [])))
        if not videos and isinstance(raw, list):
            videos = raw
        print(f"[OK] 读取 {len(videos)} 条视频 -> {filepath}")
    elif args.bvid:
        # 导入 bilibili_news scraper
        _news_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bilibili_news")
        sys.path.insert(0, _news_dir)
        from bilibili_news.scraper import BiliScraper
        scraper = BiliScraper(credential=credential)
        v = scraper.get_video_info(args.bvid)
        videos = [v.to_dict()]
        print(f"[OK] 读取视频: {args.bvid}")
    else:
        print("[失败] 请指定视频文件或 --bvid")
        return

    if not videos:
        print("[失败] 未读取到视频数据")
        return

    # 设置 DeepSeek API Key
    api_key = args.api_key or deepseek.get_api_key()
    if args.api_key:
        deepseek.set_api_key(args.api_key)

    # 评分
    results = judge_batch(videos, credential=credential, api_key=api_key)

    # 显示
    print(f"\n==== 评分结果 (共 {len(results)} 条) ====\n")
    cutoff = args.top if args.top > 0 else len(results)
    for i, v in enumerate(results[:cutoff], 1):
        print_video(v, i)
        if args.top and i >= args.top:
            break
    if args.top > 0 and len(results) > args.top:
        print(f"... 还有 {len(results) - args.top} 条未显示\n")

    # 保存
    save_results(results)


def cmd_config(args):
    """配置 DeepSeek API Key"""
    if args.api_key:
        config.set_api_key(args.api_key)
        os.environ["DEEPSEEK_API_KEY"] = args.api_key
        print(f"[OK] API Key 已保存到 {config.CONFIG_FILE}")
    else:
        key = config.get_api_key()
        if key:
            masked = key[:8] + "..." + key[-4:] if len(key) > 12 else key
            source = "环境变量" if os.environ.get("DEEPSEEK_API_KEY") else "配置文件"
            print(f"[OK] 当前 API Key ({source}): {masked}")
        else:
            print("[提示] 未设置 DeepSeek API Key")
            print("  请运行: python cli.py config --api-key sk-xxx")


def cmd_list(args):
    """列出已保存的评分结果"""
    files = list_results()
    if not files:
        print("(暂无评分结果)")
        return
    print(f"\n已保存的评分结果 ({len(files)} 个):\n")
    for f in files[-20:]:
        path = os.path.join(config.get_judge_data_dir(), f)
        size = os.path.getsize(path)
        print(f"  {f}  ({size / 1024:.1f} KB)")


def main():
    parser = argparse.ArgumentParser(
        description="B站视频评分筛选工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 评分推荐视频文件
  python cli.py judge ..\\bilibili_news\\data\\recommend_20260503_171440.json

  # 只看前10
  python cli.py judge recommend_20260503_171440.json --top 10

  # 设置 DeepSeek API Key
  python cli.py config --api-key sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        """
    )

    sub = parser.add_subparsers(dest="command", help="可用命令")

    # judge
    p_judge = sub.add_parser("judge", help="对视频列表进行评分筛选")
    p_judge.add_argument("file", nargs="?", help="bilibili_news 输出的 JSON 文件")
    p_judge.add_argument("--bvid", help="评分单个视频（BV 号）")
    p_judge.add_argument("--top", type=int, default=0, help="只显示前 N 条")
    p_judge.add_argument("--api-key", help="DeepSeek API Key（临时指定）")
    p_judge.set_defaults(func=cmd_judge)

    # config
    p_config = sub.add_parser("config", help="配置 DeepSeek API Key")
    p_config.add_argument("--api-key", help="设置 DeepSeek API Key")
    p_config.set_defaults(func=cmd_config)

    # list
    sub.add_parser("list", help="列出已保存的评分结果").set_defaults(func=cmd_list)

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
        import traceback
        traceback.print_exc()
        print(f"[失败] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
