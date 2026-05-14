"""B站登录凭证管理工具

提供四种方式获取登录凭证:
  1. 手机号+密码登录（含 Geetest 验证码）
  2. 二维码登录（推荐，最简单）
  3. 粘贴 Cookie 字符串
  4. 从缓存文件自动加载

核心逻辑:
  - 登录成功后凭证自动缓存到 credential_cache.json
  - 自动化运行时优先从缓存加载（每2小时刷新无需重新登录）
  - 缓存过期后可自动尝试重新登录
"""

import os
import json
import time
import webbrowser
from typing import Optional

try:
    from bilibili_api import Credential, login_v2, sync
    from bilibili_api.utils.geetest import Geetest, GeetestType
except ImportError:
    raise ImportError("请先安装 bilibili-api-python: pip install bilibili-api-python")

import config
CACHE_FILE = config.get_cookies_path()


# ========== 缓存管理 ==========

def _save_cache(credential: Credential):
    """缓存登录凭证到本地文件"""
    data = {
        "sessdata": credential.sessdata,
        "bili_jct": credential.bili_jct,
        "buvid3": credential.buvid3,
        "buvid4": credential.buvid4,
        "dedeuserid": credential.dedeuserid,
        "ac_time_value": credential.ac_time_value,
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("[OK] 凭证已缓存到", CACHE_FILE)


def load_cache() -> Optional[Credential]:
    """从缓存文件加载登录凭证"""
    if not os.path.isfile(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data.get("sessdata") or not data.get("bili_jct"):
            return None
        return Credential(
            sessdata=data.get("sessdata", ""),
            bili_jct=data.get("bili_jct", ""),
            buvid3=data.get("buvid3", ""),
            buvid4=data.get("buvid4", ""),
            dedeuserid=data.get("dedeuserid", ""),
            ac_time_value=data.get("ac_time_value", ""),
        )
    except Exception:
        return None


def clear_cache():
    """清除缓存的登录凭证"""
    if os.path.isfile(CACHE_FILE):
        os.remove(CACHE_FILE)
        print("[OK] 已清除缓存的登录凭证")
    else:
        print("[OK] 无缓存凭证")


# ========== Geetest 验证码处理 ==========

def _solve_geetest(geetest_type: GeetestType = GeetestType.LOGIN) -> Geetest:
    """启动 Geetest 验证码，打开浏览器让用户完成

    返回已完成的 Geetest 对象，可用于 login_with_password 等。
    """
    gt = Geetest()
    gt.start_geetest_server()
    gt.generate_test(type_=geetest_type)
    url = gt.get_geetest_server_url()

    print("\n" + "=" * 60)
    print("请在浏览器中完成验证码...")
    print("=" * 60)
    print(f"如果浏览器未自动打开，请访问: {url}")
    print("=" * 60 + "\n")

    webbrowser.open(url)

    # 等待用户完成验证码
    last_check = time.time()
    while not gt.has_done():
        time.sleep(0.5)
        if time.time() - last_check > 30:
            print("(等待验证码完成，请检查浏览器窗口...)")
            last_check = time.time()

    print("[OK] 验证码已完成\n")
    return gt


# ========== 登录方式 ==========

def login_by_password(phone: str, password: str) -> Credential:
    """手机号+密码登录（含 Geetest 验证码）

    流程:
      1. 弹出浏览器完成 Geetest 验证码
      2. 用手机号+密码登录
      3. 如需短信验证，自动发送并让用户输入验证码
      4. 缓存凭证

    Args:
        phone: 手机号
        password: 密码
    """
    print("[1/3] 启动验证码...")
    geetest = _solve_geetest()

    print("[2/3] 登录中...")
    result = sync(login_v2.login_with_password(phone, password, geetest))

    if isinstance(result, login_v2.LoginCheck):
        print("[提示] 需要短信验证码确认")
        lc = result
        info = sync(lc.fetch_info())
        print(f"[提示] 验证码已发送到: {info.get('phone', {}).get('mask', '已绑定手机')}")

        code = input("请输入短信验证码: ").strip()
        credential = sync(lc.complete_check(code))
    else:
        credential = result

    _save_cache(credential)
    print("[OK] 手机号+密码登录成功")
    return credential


def login_by_qrcode() -> Credential:
    """二维码登录（推荐）

    生成二维码图片并自动打开，用 B站 App 扫码即可。
    """
    ql = login_v2.QrCodeLogin()
    print("正在生成二维码...")
    sync(ql.generate_qrcode())

    # 保存二维码图片并打开
    import time
    qr_name = f"qrcode_{time.strftime('%Y%m%d_%H%M%S')}.png"
    qr_path = os.path.join(os.path.dirname(CACHE_FILE), qr_name)
    pic = ql.get_qrcode_picture()
    pic.to_file(qr_path)
    print(f"[OK] 二维码已保存到: {qr_path}")
    webbrowser.open(qr_path)
    print("请在打开的图片中扫码，或使用 B站 手机客户端扫描。\n")

    last_event = None
    while True:
        event = sync(ql.check_state())
        if event != last_event:
            if event == login_v2.QrCodeLoginEvents.SCAN:
                print("[OK] 已扫描，请在手机上确认...")
            elif event == login_v2.QrCodeLoginEvents.CONF:
                print("[OK] 已确认，登录中...")
            elif event == login_v2.QrCodeLoginEvents.TIMEOUT:
                print("[失败] 二维码已过期")
                raise TimeoutError("二维码已过期")
            elif event == login_v2.QrCodeLoginEvents.DONE:
                print("[OK] 登录成功！")
                break
            last_event = event
        time.sleep(1)

    credential = ql.get_credential()
    _save_cache(credential)
    return credential


def login_by_cookie_string(cookie_str: str) -> Credential:
    """从浏览器 Cookie 字符串解析登录凭证

    格式: SESSDATA=xxx; bili_jct=xxx; ...
    """
    cookies = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            key, value = part.split("=", 1)
            cookies[key.strip()] = value.strip()

    sessdata = cookies.get("SESSDATA", "")
    bili_jct = cookies.get("bili_jct", "")
    if not sessdata or not bili_jct:
        raise ValueError("Cookie 中缺少 SESSDATA 或 bili_jct 字段")

    credential = Credential(
        sessdata=sessdata,
        bili_jct=bili_jct,
        buvid3=cookies.get("buvid3", ""),
        buvid4=cookies.get("buvid4", ""),
        dedeuserid=cookies.get("DedeUserID", ""),
        ac_time_value=cookies.get("ac_time_value", ""),
    )
    _save_cache(credential)
    return credential


def login_by_fields():
    """手动输入 cookie 各字段"""
    print("请从浏览器开发者工具复制以下字段的值：")
    print("  F12 -> Application -> Cookies -> bilibili.com\n")

    sessdata = input("SESSDATA: ").strip()
    bili_jct = input("bili_jct: ").strip()
    buvid3 = input("buvid3 (可选): ").strip()
    dedeuserid = input("DedeUserID (可选): ").strip()
    ac_time_value = input("ac_time_value (可选): ").strip()

    if not sessdata or not bili_jct:
        raise ValueError("SESSDATA 和 bili_jct 不能为空")

    credential = Credential(
        sessdata=sessdata,
        bili_jct=bili_jct,
        buvid3=buvid3,
        dedeuserid=dedeuserid,
        ac_time_value=ac_time_value,
    )
    _save_cache(credential)
    return credential


# ========== 自动化支持 ==========

def get_credential(auto_login: bool = True) -> Optional[Credential]:
    """获取登录凭证

    自动化场景调用顺序:
      1. 尝试从缓存加载（之前登录过的凭证）
      2. 无缓存时根据 auto_login 决定是否启动交互式登录

    Args:
        auto_login: 无缓存时是否自动启动登录流程
    """
    cached = load_cache()
    if cached:
        print("[OK] 从缓存加载登录凭证")
        return cached

    if auto_login:
        print("[提示] 未找到缓存的登录凭证")
        print("请先运行: python cli.py login")
        print("  - 二维码登录: python cli.py login")
        print("  - 手机号+密码: python cli.py login --password")
        print("  - 粘贴 Cookie: python cli.py login --cookie \"...\"")
        return None

    return None


def check_credential(credential: Credential) -> bool:
    """检查凭证是否有效"""
    try:
        from bilibili_api import user
        info = sync(user.get_self_info(credential=credential))
        name = info.get("name", "")
        if name:
            print(f"[OK] 凭证有效，当前用户: {name}")
            return True
        else:
            print("[失败] 无法获取用户信息")
            return False
    except Exception as e:
        print(f"[失败] 凭证已过期或无效: {e}")
        return False


def auto_get_credential(phone: str = "", password: str = "") -> Optional[Credential]:
    """自动化获取凭证（用于定时任务）

    策略:
      1. 优先从缓存加载
      2. 如果缓存无效但有手机号+密码，尝试自动重新登录
      3. 如果都失败，返回 None

    Args:
        phone: B站手机号（可选，用于自动重登）
        password: B站密码（可选）
    """
    credential = load_cache()
    if credential:
        print("[OK] 从缓存加载登录凭证")
        return credential

    if phone and password:
        print("[提示] 缓存无效，尝试手机号+密码登录...")
        print("[失败] 手机号+密码登录需要手动完成验证码，无法全自动化")
        print("请先在交互模式下登录一次: python cli.py login")
        return None

    print("[失败] 无可用登录凭证")
    return None
