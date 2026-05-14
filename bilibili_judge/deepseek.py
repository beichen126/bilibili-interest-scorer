"""DeepSeek API 调用封装

用于分析视频内容与用户兴趣的契合度。
返回纯数字 0-100，不返回 JSON。
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import config

DEFAULT_MODEL = "deepseek-v4-flash"
API_URL = "https://api.deepseek.com/v1/chat/completions"
API_TIMEOUT = 90


def get_active_prompt() -> str:
    return config.get_active_prompt()


def set_custom_prompt(text: str):
    config.set_custom_prompt(text)


def reset_custom_prompt():
    config.reset_custom_prompt()


def has_custom_prompt() -> bool:
    return config.has_custom_prompt()


def get_api_key() -> str:
    return config.get_api_key()


def set_api_key(key: str):
    config.set_api_key(key)


def is_available() -> bool:
    return config.is_api_available()


def _parse_score(text: str) -> Optional[int]:
    """从模型返回文本中提取 0-100 的整数分数"""
    if not text:
        return None
    text = text.strip()

    # 0. 全角数字 → 半角（８５→85）
    text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))

    # 1. 纯数字（含小数）
    try:
        score = round(float(text))
        return max(0, min(100, score))
    except ValueError:
        pass

    # 2. 正则提取第一个 0-100 整数（前后不能紧跟数字）
    match = re.search(r'(?<!\d)(0|[1-9]\d?|100)(?!\d)', text)
    if match:
        return int(match.group(1))

    # 3. 中文数字
    _cn = {k: v for k, v in zip(
        '零一二三四五六七八九十', range(0, 11))}
    if text.strip() in _cn:
        return _cn[text.strip()]

    return None


def _call_api_urllib(user_prompt: str, api_key: str) -> Optional[int]:
    """单次 DeepSeek API 调用（基于 urllib，避免 requests 的编码问题），返回分数或 None"""
    import urllib.error
    import urllib.request

    payload = json.dumps({
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": get_active_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 256,
        "thinking_mode": "non-thinking",
    }, ensure_ascii=True)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
    }
    req = urllib.request.Request(API_URL, data=payload.encode("utf-8"),
                                  headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            if resp.status != 200:
                print(f"  [DeepSeek API] HTTP {resp.status}: {body[:300]}")
                return None
            data = json.loads(body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:300]
        print(f"  [DeepSeek API] HTTP {e.code}: {err_body}")
        return None
    except urllib.error.URLError as e:
        print(f"  [DeepSeek API] 网络错误: {e.reason}")
        return None
    except Exception as e:
        print(f"  [DeepSeek API] 请求异常: {e}")
        return None

    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    # 推理模型（如 deepseek-v4-flash）可能把输出放在 reasoning_content
    if not isinstance(content, str) or not content.strip():
        content = data.get("choices", [{}])[0].get("message", {}).get("reasoning_content", "")
    if not isinstance(content, str) or not content.strip():
        print(f"  [DeepSeek API] 返回内容空 (content/reasoning_content 均无): {str(data)[:300]}")
        return None
    content = content.strip()
    score = _parse_score(content)
    if score is None:
        print(f"  [DeepSeek API] 无法解析: {content[:300]!r}")
    return score


_call_api = _call_api_urllib


def analyze_interest(title: str, owner_name: str = "", tag: str = "",
                     desc: str = "", play: int = 0, duration: int = 0,
                     api_key: str = None) -> Optional[int]:
    """分析视频与用户兴趣的契合度，返回 0-100 分数

    最多重试 3 次，每次间隔 1 秒。
    """
    api_key = api_key or get_api_key()
    if not api_key:
        return None

    user_prompt = f"""视频标题：{title}
UP主：{owner_name}
标签/分区：{tag}
简介：{desc}
播放量：{play}
时长(秒)：{duration}"""

    for attempt in range(3):
        score = _call_api(user_prompt, api_key)
        if score is not None:
            return score
        if attempt < 2:
            print(f"  [DeepSeek] 第{attempt + 1}次失败，1s后重试…")
            time.sleep(1)

    print(f"  [DeepSeek] 重试3次均失败，跳过: 《{title[:30]}》")
    return None


def batch_analyze(videos: list[dict], api_key: str = None,
                  max_count: int = 30) -> list[dict]:
    """批量分析视频兴趣契合度（并发调用，大幅提速）

    Args:
        videos: 视频列表
        api_key: DeepSeek API Key
        max_count: 最多分析的视频数

    Returns:
        每项添加 deepseek_score 字段
    """
    api_key = api_key or get_api_key()
    if not api_key:
        print("[提示] 未设置 DeepSeek API Key，跳过 AI 兴趣分析")
        return videos

    batch = videos[:max_count]
    total = len(batch)
    print(f"[OK] 正在并发分析 {total} 个视频的兴趣契合度...")

    # 预构建所有请求参数
    tasks = []
    for v in batch:
        tag = ", ".join(v.get("tags", [])) if isinstance(v.get("tags"), list) else str(v.get("tag", ""))
        tasks.append({
            "title": v.get("title", ""),
            "owner_name": v.get("owner_name", ""),
            "tag": tag,
            "desc": v.get("description", v.get("desc", "")),
            "play": v.get("play", v.get("view", 0)),
            "duration": v.get("duration", 0),
        })

    # 并发调用
    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {
            executor.submit(analyze_interest, api_key=api_key, **t): i
            for i, t in enumerate(tasks)
        }
        for future in as_completed(future_map):
            i = future_map[future]
            try:
                results[i] = future.result()
            except Exception:
                results[i] = None

    # 写回
    for i, v in enumerate(batch):
        v["deepseek_score"] = results.get(i) if results.get(i) is not None else 50

    print(f"[OK] DeepSeek 分析完成")
    return videos
