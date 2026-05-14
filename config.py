"""集中式配置管理

配置目录发现优先级:
  1. 环境变量 BILI_TOOLBOX_CONFIG_DIR
  2. 用户主目录 ~/.bilibili_toolbox
  3. 当前目录 ./.bilibili_toolbox (沙盒环境降级)

配置目录结构:
  ~/.bilibili_toolbox/
  ├── config.json              # API Key + 设置
  ├── credential_cache.json    # B站登录 Cookie
  ├── prompts/
  │   ├── interest_scoring_prompt.md  # 默认提示词
  │   └── custom_prompt.md           # 用户自定义提示词
  ├── news_data/               # bilibili_news 数据输出
  └── judge_data/              # bilibili_judge 数据输出
"""

import os
import json
import shutil
from pathlib import Path

__version__ = "1.0.0"


def get_config_dir() -> Path:
    if env_path := os.environ.get("BILI_TOOLBOX_CONFIG_DIR"):
        return Path(env_path)

    try:
        home_dir = Path.home() / ".bilibili_toolbox"
        home_dir.mkdir(parents=True, exist_ok=True)
        test_file = home_dir / ".test_write"
        test_file.touch()
        test_file.unlink()
        return home_dir
    except (OSError, PermissionError, RuntimeError):
        pass

    return Path.cwd() / ".bilibili_toolbox"


CONFIG_DIR = get_config_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"
CREDENTIAL_CACHE_FILE = CONFIG_DIR / "credential_cache.json"
PROMPTS_DIR = CONFIG_DIR / "prompts"
NEWS_DATA_DIR = CONFIG_DIR / "news_data"
JUDGE_DATA_DIR = CONFIG_DIR / "judge_data"

# 项目内置默认提示词路径（只读）
_PROJECT_PROMPT_DIR = Path(__file__).parent / "bilibili_judge" / "prompts"
_DEFAULT_PROMPT_SRC = _PROJECT_PROMPT_DIR / "interest_scoring_prompt.md"

DEFAULT_CONFIG = {
    "api_key": "",
    "model": "deepseek-v4-flash",
}

# ── 运行时缓存 ──
_runtime_api_key: str = ""


def ensure_dirs():
    """确保所有配置目录存在，首次运行时从项目目录复制默认提示词"""
    for d in [CONFIG_DIR, PROMPTS_DIR, NEWS_DATA_DIR, JUDGE_DATA_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    # 首次运行：复制默认提示词到配置目录
    default_prompt_dst = PROMPTS_DIR / "interest_scoring_prompt.md"
    if not default_prompt_dst.exists() and _DEFAULT_PROMPT_SRC.exists():
        shutil.copy(_DEFAULT_PROMPT_SRC, default_prompt_dst)


# ── API Key ──

def get_api_key() -> str:
    """获取 DeepSeek API Key（优先级：运行时设置 > 环境变量 > 配置文件 > 空）"""
    if _runtime_api_key:
        return _runtime_api_key
    if env_key := os.environ.get("DEEPSEEK_API_KEY"):
        return env_key
    config = load_config()
    return config.get("api_key", "")


def set_api_key(key: str):
    """设置运行时 API Key，并持久化到配置文件"""
    global _runtime_api_key
    _runtime_api_key = key
    config = load_config()
    config["api_key"] = key
    save_config(config)


def is_api_available() -> bool:
    return bool(get_api_key())


# ── 配置文件 ──

def load_config() -> dict:
    ensure_dirs()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # 兼容旧 key 名
                if "api_key" not in config and "deepseek_api_key" in config:
                    config["api_key"] = config.pop("deepseek_api_key")
                return config
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    ensure_dirs()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


# ── Cookie 缓存 ──

def get_cookies_path() -> str:
    ensure_dirs()
    return str(CREDENTIAL_CACHE_FILE)


# ── 提示词 ──

def get_default_prompt_path() -> str:
    """默认提示词路径（优先返回配置目录的副本）"""
    ensure_dirs()
    cfg_copy = PROMPTS_DIR / "interest_scoring_prompt.md"
    if cfg_copy.exists():
        return str(cfg_copy)
    return str(_DEFAULT_PROMPT_SRC)


def get_custom_prompt_path() -> str:
    ensure_dirs()
    return str(PROMPTS_DIR / "custom_prompt.md")


def has_custom_prompt() -> bool:
    return os.path.exists(get_custom_prompt_path())


def get_active_prompt() -> str:
    custom_path = get_custom_prompt_path()
    if os.path.exists(custom_path):
        with open(custom_path, "r", encoding="utf-8") as f:
            return f.read()
    default_path = get_default_prompt_path()
    if os.path.exists(default_path):
        with open(default_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def set_custom_prompt(text: str):
    ensure_dirs()
    with open(get_custom_prompt_path(), "w", encoding="utf-8") as f:
        f.write(text)


def reset_custom_prompt():
    path = get_custom_prompt_path()
    if os.path.exists(path):
        os.remove(path)


# ── 日志 ──

def get_log_path() -> str:
    ensure_dirs()
    return str(CONFIG_DIR / "app.log")


# ── 数据目录 ──

def get_news_data_dir() -> str:
    ensure_dirs()
    return str(NEWS_DATA_DIR)


def get_judge_data_dir() -> str:
    ensure_dirs()
    return str(JUDGE_DATA_DIR)
