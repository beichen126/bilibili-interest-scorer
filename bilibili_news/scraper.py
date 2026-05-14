import os
import json
import datetime
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional
import asyncio

try:
    from bilibili_api import hot, video, rank, homepage, search as bili_search, sync, user
    from bilibili_api import Credential
except ImportError:
    raise ImportError("请先安装 bilibili-api-python: pip install bilibili-api-python")

import config
DATA_DIR = config.get_news_data_dir()


@dataclass
class BiliVideo:
    """B站视频数据结构"""
    bvid: str
    aid: int
    title: str
    owner_name: str
    owner_mid: int
    owner_fans: int = 0     # UP主粉丝数
    is_followed: bool = False  # 当前账号是否已关注该作者
    view: int = 0
    like: int = 0
    favorite: int = 0
    coin: int = 0
    share: int = 0
    reply: int = 0
    danmaku: int = 0
    duration: int = 0
    pubdate: int = 0
    pic: str = ""
    tname: str = ""
    description: str = ""
    tags: list = field(default_factory=list)
    is_hot: bool = False  # 是否同时在热门榜上
    url: str = ""         # B站视频链接

    def __post_init__(self):
        if not self.url and self.bvid:
            self.url = f"https://www.bilibili.com/video/{self.bvid}"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, ensure_ascii=False) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=2)

    @property
    def pubdate_str(self) -> str:
        return datetime.datetime.fromtimestamp(self.pubdate).strftime("%Y-%m-%d %H:%M:%S")

    @property
    def duration_str(self) -> str:
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    @property
    def short_title(self) -> str:
        """截断过长的标题用于显示"""
        return self.title[:40] + "..." if len(self.title) > 40 else self.title


class BiliScraper:
    """B站视频信息抓取器（支持登录态个性化推荐）"""

    def __init__(self, data_dir: str = DATA_DIR, credential: Credential = None):
        self.data_dir = data_dir
        self.credential = credential
        os.makedirs(self.data_dir, exist_ok=True)

    def set_credential(self, credential: Credential):
        """设置登录凭证（用于获取个性化推荐）"""
        self.credential = credential

    def set_credential_from_cookies(self, sessdata: str, bili_jct: str, buvid3: str = "",
                                     dedeuserid: str = ""):
        """通过 cookie 字段设置登录凭证"""
        self.credential = Credential(
            sessdata=sessdata,
            bili_jct=bili_jct,
            buvid3=buvid3,
            dedeuserid=dedeuserid,
        )

    @property
    def is_logged_in(self) -> bool:
        return self.credential is not None

    # ---- 关注列表检查 ----

    def _fetch_follow_mids(self) -> set[int]:
        """获取当前账号所有关注的 mid"""
        try:
            from bilibili_api import user as user_mod
            info = sync(user_mod.get_self_info(credential=self.credential))
            uid = info.get("mid", 0)
            u = user.User(uid=uid, credential=self.credential)
            follows = sync(u.get_all_followings())
            # get_all_followings 返回 list[int]（mid 列表）
            mids = set(follows) if follows and isinstance(follows[0], int) else set()
            print(f"[OK] 已加载关注列表 ({len(mids)} 人)")
            return mids
        except Exception as e:
            print(f"[失败] 获取关注列表出错: {e}")
            return set()

    def mark_followed(self, videos: list[BiliVideo]):
        """标记视频作者是否已关注"""
        mids = self._fetch_follow_mids()
        for v in videos:
            if v.owner_mid in mids:
                v.is_followed = True

    # ---- 个性化推荐（需登录） ----

    def get_recommendations(self, fresh: bool = False) -> list[BiliVideo]:
        """获取首页个性化推荐视频（需登录）"""
        if not self.is_logged_in:
            raise RuntimeError("需要登录才能获取个性化推荐，请先调用 set_credential()")
        raw = sync(homepage.get_videos(credential=self.credential))
        items = raw.get("item", [])
        videos = []
        for item in items:
            v = self._parse_recommend_item(item)
            if v:
                videos.append(v)
        return videos

    def get_recommendations_with_hot_flag(self, full: bool = False) -> tuple[list[BiliVideo], list[BiliVideo]]:
        """获取个性化推荐，并标记哪些也在热门榜上

        Args:
            full: 是否补全完整数据（收藏/投币/评论/标签等）

        Returns:
            (recommend_list, hot_list)
        """
        recommends = self.get_recommendations()
        hot_list = self.get_hot(pn=1, ps=50)

        hot_bvids = {v.bvid for v in hot_list}
        for v in recommends:
            if v.bvid in hot_bvids:
                v.is_hot = True

        # 标记是否已关注作者
        print("[OK] 正在检查关注状态...")
        self.mark_followed(recommends)

        if full:
            print("[OK] 正在补全完整数据（收藏/投币/评论/标签等）...")
            self._enrich_videos(recommends)

        return recommends, hot_list

    def _enrich_videos(self, videos: list[BiliVideo]):
        """并发补全视频的完整统计数据、标签和UP主粉丝数"""
        async def fetch_all():
            # 视频信息 + 标签
            info_tasks = []
            for v in videos:
                v_obj = video.Video(bvid=v.bvid, credential=self.credential)
                info_tasks.append(asyncio.gather(v_obj.get_info(), v_obj.get_tags(), return_exceptions=True))
            info_results = await asyncio.gather(*info_tasks)

            # UP主粉丝数（去重）
            seen_mids = {}
            fan_tasks = {}
            for v in videos:
                mid = v.owner_mid
                if mid and mid not in seen_mids:
                    seen_mids[mid] = True
                    fan_tasks[mid] = user.User(uid=mid).get_relation_info()
            fan_results = {}
            if fan_tasks:
                raw = await asyncio.gather(*fan_tasks.values(), return_exceptions=True)
                for mid, result in zip(fan_tasks.keys(), raw):
                    if not isinstance(result, Exception):
                        fan_results[mid] = result.get("follower", 0)

            # 填充数据
            for i, v in enumerate(videos):
                info_result, tags_result = info_results[i]
                if not isinstance(info_result, Exception):
                    stat = info_result.get("stat", {}) or {}
                    v.view = self._int(stat.get("view", v.view))
                    v.like = self._int(stat.get("like", v.like))
                    v.favorite = self._int(stat.get("favorite"))
                    v.coin = self._int(stat.get("coin"))
                    v.share = self._int(stat.get("share"))
                    v.reply = self._int(stat.get("reply"))
                    v.danmaku = self._int(stat.get("danmaku", v.danmaku))
                    v.description = info_result.get("description", "")
                    v.tname = info_result.get("tname", "")
                if not isinstance(tags_result, Exception) and isinstance(tags_result, list):
                    v.tags = [t.get("tag_name", "") for t in tags_result if isinstance(t, dict)]
                v.owner_fans = fan_results.get(v.owner_mid, 0)

        sync(fetch_all())

    # ---- 热门视频 ----

    def get_hot(self, pn: int = 1, ps: int = 20) -> list[BiliVideo]:
        """获取热门视频列表"""
        raw = sync(hot.get_hot_videos(pn=pn, ps=ps))
        return self._parse_list(raw)

    # ---- 入站必刷 ----

    def get_popular(self) -> list[BiliVideo]:
        """获取入站必刷 85 个视频"""
        raw = sync(hot.get_history_popular_videos())
        return self._parse_list(raw)

    # ---- 每周必看 ----

    def get_weekly(self, week: int = 1) -> list[BiliVideo]:
        """获取每周必看"""
        raw = sync(hot.get_weekly_hot_videos(week=week))
        return self._parse_list(raw.get("list", []))

    # ---- 排行榜 ----

    def get_rank(self, rid: int = 0, day: int = 3) -> list[BiliVideo]:
        """获取排行榜

        Args:
            rid: 分区 ID (0 = 全站)
            day: 天数 (1/3/7)
        """
        raw = sync(rank.get_rank(rid=rid, day=day))
        return self._parse_list(raw.get("list", []))

    # ---- 单个视频详情 ----

    def get_video_info(self, bvid: str) -> BiliVideo:
        """获取单个视频的详细信息（含标签）

        Args:
            bvid: BV 号（如 BV1GJ41177UF）
        """
        v = video.Video(bvid=bvid, credential=self.credential)
        info = sync(v.get_info())
        try:
            tags_raw = sync(v.get_tags())
            tags = [t.get("tag_name", "") for t in tags_raw]
        except Exception:
            tags = []
        return self._parse_item(info, tags)

    # ---- 搜索 ----

    def search(self, keyword: str, page: int = 1) -> list[BiliVideo]:
        """搜索视频"""
        raw = sync(bili_search.search(keyword, page=page))
        result = raw.get("result", [])
        # 搜索结果按 result_type 分组
        if isinstance(result, list):
            for group in result:
                if group.get("result_type") == "video":
                    return self._parse_search_list(group.get("data", []))
        return []

    # ---- 保存 / 加载 ----

    def save(self, videos: list[BiliVideo], filename: str = None) -> str:
        """保存视频列表到 JSON 文件

        Args:
            videos: 视频列表
            filename: 文件名（默认自动生成）

        Returns:
            文件路径
        """
        if filename is None:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bilibili_{ts}.json"

        path = os.path.join(self.data_dir, filename)
        data = {
            "count": len(videos),
            "timestamp": datetime.datetime.now().isoformat(),
            "videos": [v.to_dict() for v in videos],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[OK] 已保存 {len(videos)} 条记录 -> {path}")
        return path

    def load(self, filename: str) -> list[BiliVideo]:
        """从 JSON 文件加载视频列表"""
        path = filename if os.path.isabs(filename) else os.path.join(self.data_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [BiliVideo(**v) for v in data["videos"]]

    def list_files(self) -> list[str]:
        """列出所有保存的数据文件"""
        if not os.path.isdir(self.data_dir):
            return []
        return sorted(f for f in os.listdir(self.data_dir) if f.endswith(".json"))

    # ---- 内部解析 ----

    def _parse_list(self, raw: dict | list) -> list[BiliVideo]:
        items = raw.get("list", raw) if isinstance(raw, dict) else raw
        return [self._parse_item(item) for item in items if item]

    def _parse_search_list(self, items: list) -> list[BiliVideo]:
        """解析搜索结果（字段名不同）"""
        return [self._parse_search_item(item) for item in items if item and item.get("bvid")]

    @staticmethod
    def _int(v) -> int:
        """安全转 int，处理 None"""
        if v is None:
            return 0
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0

    def _parse_search_item(self, item: dict) -> BiliVideo:
        """解析单个搜索结果条目"""
        return BiliVideo(
            bvid=item.get("bvid", ""),
            aid=self._int(item.get("aid")),
            title=item.get("title", ""),
            owner_name=item.get("author", ""),
            owner_mid=self._int(item.get("mid")),
            view=self._int(item.get("play")),
            like=self._int(item.get("like")),
            favorite=self._int(item.get("favorites")),
            coin=0,
            share=0,
            reply=self._int(item.get("review")),
            danmaku=self._int(item.get("video_review")),
            duration=self._int(item.get("duration")),
            pubdate=self._int(item.get("pubdate")),
            pic=item.get("pic", ""),
            tname=item.get("typename", ""),
            description=item.get("description", ""),
            tags=[],
        )

    def _parse_item(self, item: dict, tags: list = None) -> BiliVideo:
        owner = item.get("owner", {}) or {}
        stat = item.get("stat", {}) or {}
        return BiliVideo(
            bvid=item.get("bvid", ""),
            aid=self._int(item.get("aid")),
            title=item.get("title", ""),
            owner_name=owner.get("name", ""),
            owner_mid=self._int(owner.get("mid")),
            view=self._int(stat.get("view")),
            like=self._int(stat.get("like")),
            favorite=self._int(stat.get("favorite")),
            coin=self._int(stat.get("coin")),
            share=self._int(stat.get("share")),
            reply=self._int(stat.get("reply")),
            danmaku=self._int(stat.get("danmaku")),
            duration=self._int(item.get("duration")),
            pubdate=self._int(item.get("pubdate")),
            pic=item.get("pic", ""),
            tname=item.get("tname", ""),
            description=item.get("description", ""),
            tags=tags or [],
        )

    def _parse_recommend_item(self, item: dict) -> Optional[BiliVideo]:
        """解析推荐视频条目（结构与热门略有不同）"""
        if not item or not item.get("bvid"):
            return None
        owner = item.get("owner", {}) or {}
        stat = item.get("stat", {}) or {}
        # 推荐列表中的 aid 字段是 id
        return BiliVideo(
            bvid=item.get("bvid", ""),
            aid=self._int(item.get("id", item.get("aid"))),
            title=item.get("title", ""),
            owner_name=owner.get("name", ""),
            owner_mid=self._int(owner.get("mid")),
            view=self._int(stat.get("view")),
            like=self._int(stat.get("like")),
            favorite=self._int(stat.get("favorite")),
            coin=self._int(stat.get("coin")),
            share=self._int(stat.get("share")),
            reply=self._int(stat.get("reply")),
            danmaku=self._int(stat.get("danmaku")),
            duration=self._int(item.get("duration")),
            pubdate=self._int(item.get("pubdate")),
            pic=item.get("pic", ""),
            tname=item.get("tname", ""),
            description="",
            tags=[],
        )
