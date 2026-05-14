"""B站视频评分引擎

评分公式:
  综合分 = DeepSeek兴趣分 × 60% + 量化分 × 40%
  已关注 → 额外 +5 (封顶100)

过滤规则:
  - 时长 < 3分钟 → 排除 (热门除外)
  - 综合分 < 60   → 排除 (热门除外)
  - 热门视频 → 强制保留
"""

import os
import json
import datetime
from typing import Optional

from . import deepseek
import config

DATA_DIR = config.get_judge_data_dir()


def _fetch_follow_mids(credential) -> set[int]:
    """获取当前账号所有关注的 mid"""
    try:
        from bilibili_api import user as user_mod, sync
        info = sync(user_mod.get_self_info(credential=credential))
        uid = info.get("mid", 0)
        u = user_mod.User(uid=uid, credential=credential)
        follows = sync(u.get_all_followings())
        mids = set(follows) if follows and isinstance(follows[0], int) else set()
        print(f"[OK] 已加载关注列表 ({len(mids)} 人)")
        return mids
    except Exception as e:
        print(f"[警告] 获取关注列表失败: {e}")
        return set()


def _calc_quantified_score(v: dict) -> float:
    """计算量化分 (0-100)

    三项子维度:
      ① 互动质量 0-40 (点赞率/收藏率/投币率/弹幕率/分享率)
      ② 热度规模 0-30 (播放量绝对值)
      ③ 作者影响力 0-30 (粉丝数)
    """
    view = v.get("view", 0) or 1
    like = v.get("like", 0) or 0
    favorite = v.get("favorite", 0) or 0
    coin = v.get("coin", 0) or 0
    danmaku = v.get("danmaku", 0) or 0
    share = v.get("share", 0) or 0

    # ① 互动质量 (0-40) — 各比率线性折算，达到满分阈值即封顶
    like_rate = min(like / view / 0.05, 1.0)      # 满分阈值 5%
    fav_rate = min(favorite / view / 0.03, 1.0)   # 满分阈值 3%
    coin_rate = min(coin / view / 0.02, 1.0)      # 满分阈值 2%
    dm_rate = min(danmaku / view / 0.02, 1.0)     # 满分阈值 2%
    share_rate = min(share / view / 0.01, 1.0)    # 满分阈值 1%

    quality = (
        like_rate * 12 +
        fav_rate * 10 +
        coin_rate * 8 +
        dm_rate * 5 +
        share_rate * 5
    )

    # ② 热度规模 (0-30)
    if view >= 500000:
        popularity = 30
    elif view >= 100000:
        popularity = 20
    elif view >= 10000:
        popularity = 10
    else:
        popularity = 0

    # ③ 作者影响力 (0-30)
    fans = v.get("owner_fans", 0) or 0
    if fans >= 1000000:
        author = 30
    elif fans >= 100000:
        author = 25
    elif fans >= 10000:
        author = 15
    elif fans >= 1000:
        author = 5
    else:
        author = 0

    return round(quality + popularity + author, 1)


def judge_batch(videos: list[dict], credential=None,
                api_key: str = None, max_count: int = 30) -> list[dict]:
    """批量评分视频

    在原视频 dict 上添加 interest_score / total_score / is_followed 字段。

    Args:
        videos: 视频列表（bilibili_news 输出的格式）
        credential: B站登录凭证（用于检查关注状态）
        api_key: DeepSeek API Key
        max_count: 最多分析的视频数

    Returns:
        评分+过滤+排序后的视频列表（dict，含额外字段）
    """
    # 1. 获取关注列表
    follow_mids = set()
    if credential:
        follow_mids = _fetch_follow_mids(credential)
    else:
        print("[提示] 未登录，跳过关注状态检查")

    # 2. DeepSeek 兴趣分析
    if deepseek.is_available() or api_key:
        analyzed = deepseek.batch_analyze(videos, api_key, max_count)
    else:
        print("[提示] 未设置 DeepSeek API Key，跳过 AI 兴趣分析")
        for v in videos:
            v["deepseek_score"] = 50
        analyzed = videos

    # 3. 逐条评分 + 过滤
    results = []
    for v in analyzed:
        duration = v.get("duration", 0) or 0
        is_hot = v.get("is_hot", False)

        # 时长过滤 (< 3分钟排除，热门除外)
        if duration > 0 and duration < 180 and not is_hot:
            continue

        # DeepSeek分
        interest_score = float(v.get("deepseek_score", 50))

        # 量化分
        quantified = _calc_quantified_score(v)

        # 综合分 (DeepSeek 60% + 量化 40%)
        total = interest_score * 0.6 + quantified * 0.4

        # 关注 +5
        owner_mid = v.get("owner_mid", 0)
        is_followed = owner_mid in follow_mids
        if is_followed:
            total += 5

        total = round(min(total, 100), 1)

        # 写入原 dict
        v["interest_score"] = interest_score
        v["total_score"] = total
        v["is_followed"] = is_followed
        results.append(v)

    # 4. 综合分过滤 (< 60排除，热门除外)
    results = [r for r in results if r.get("is_hot") or r["total_score"] >= 60]

    # 5. 按总分降序
    results.sort(key=lambda x: -x["total_score"])

    return results


def save_results(results: list[dict], filename: str = None) -> str:
    """保存评分结果到 data/ 目录"""
    if filename is None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"judged_{ts}.json"

    path = os.path.join(DATA_DIR, filename)
    data = {
        "count": len(results),
        "timestamp": datetime.datetime.now().isoformat(),
        "results": results,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] 已保存评分结果 -> {path}")
    return path


def list_results() -> list[str]:
    """列出所有评分结果文件"""
    if not os.path.isdir(DATA_DIR):
        return []
    return sorted(f for f in os.listdir(DATA_DIR) if f.startswith("judged_") and f.endswith(".json"))
