"""
DeepSeek API 诊断工具

测试 API 连通性并显示原始返回内容，帮助排查评分失败原因。
用法:
  python debug_deepseek.py
  python debug_deepseek.py --api-key sk-xxx
  python debug_deepseek.py --verbose
"""

import sys
import os
import json

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from bilibili_judge import deepseek

SAMPLE_PROMPT = """视频标题：【硬核】408考研数据结构从零到精通
UP主：王道计算机教育
标签/分区：考研, 计算机, 数据结构
简介：全网最详细的408数据结构精讲，从底层原理到真题实战，适合跨考和科班同学。
播放量：358000
时长(秒)：4860"""


def main():
    import argparse
    parser = argparse.ArgumentParser(description="DeepSeek API 诊断工具")
    parser.add_argument("--api-key", help="DeepSeek API Key（不指定则读取已有配置）")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示完整请求/响应")
    args = parser.parse_args()

    # 获取 API Key
    if args.api_key:
        deepseek.set_api_key(args.api_key)
    api_key = deepseek.get_api_key()

    if not api_key:
        print("[失败] 未设置 DeepSeek API Key")
        print("  请通过 --api-key 指定，或在 GUI 中配置")
        sys.exit(1)

    key_masked = api_key[:8] + "…" + api_key[-4:] if len(api_key) > 16 else api_key[:4] + "…"
    print(f"API Key: {key_masked}")
    print(f"Model:   {deepseek.DEFAULT_MODEL}")
    print(f"URL:     {deepseek.API_URL}")
    system_prompt = deepseek.get_active_prompt()
    print(f"系统提示词长度: {len(system_prompt)} 字符")
    if system_prompt:
        print(f"系统提示词前 100 字: {system_prompt[:100]}…")
    print()

    # 测试调用
    print("=" * 60)
    print("发送测试请求…")
    print("=" * 60)

    import requests
    payload = {
        "model": deepseek.DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt or "(空)"},
            {"role": "user", "content": SAMPLE_PROMPT},
        ],
        "temperature": 0.0,
        "max_tokens": 256,
    }

    if args.verbose:
        print(f"\n请求报文:")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print()

    try:
        resp = requests.post(
            deepseek.API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json; charset=utf-8",
            },
            data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
            timeout=deepseek.API_TIMEOUT,
        )

        print(f"HTTP 状态码: {resp.status_code}")
        print()

        if resp.status_code != 200:
            print(f"响应体 (前 500 字符):")
            print(resp.text[:500])
            print()
            print("[失败] API 返回错误")
            sys.exit(1)

        data = resp.json()

        # 显示完整响应结构
        print("完整响应 JSON:")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:1000])
        print()

        # 提取 content
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"模型返回 content ({len(content)} 字符):")
        print(repr(content[:500]))
        print()

        # 尝试解析
        score = deepseek._parse_score(content)
        if score is not None:
            print(f"[OK] 解析成功: deepseek_score = {score}")
        else:
            print(f"[失败] _parse_score 返回 None")
            print("建议: 检查返回内容的格式，可能需要更新 _parse_score")

    except requests.exceptions.Timeout:
        print(f"[失败] 请求超时 ({deepseek.API_TIMEOUT}s)")
    except requests.exceptions.ConnectionError as e:
        print(f"[失败] 网络连接失败: {e}")
    except Exception as e:
        print(f"[失败] 请求异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
