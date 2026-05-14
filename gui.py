"""
B站工具箱 - 图形界面

整合 bilibili_news 和 bilibili_judge 两个模块。
一行启动: python gui.py
"""

import sys
import os
import json
import threading
import datetime
import io
from tkinter import ttk, messagebox, scrolledtext
import tkinter as tk

# ── 路径引导 ──────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from bilibili_news.scraper import BiliScraper, BiliVideo
from bilibili_news import cookie_util
from bilibili_judge.judger import judge_batch, save_results, list_results as list_judged
from bilibili_judge import deepseek
import config

# ── 工具函数 ──────────────────────────────────────────────

def _fmt_count(n: int) -> str:
    if n >= 10000:
        return f"{n / 10000:.1f}万"
    return str(n)

def _fmt_duration(sec: int) -> str:
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def _short_title(title: str, max_len: int = 50) -> str:
    return title[:max_len] + "…" if len(title) > max_len else title


# ── Print 捕获器 → Text Widget + 日志文件 ─────────────────

class PrintRedirector(io.TextIOBase):
    def __init__(self, text_widget):
        self.widget = text_widget
        self._log_path = config.get_log_path()

    def write(self, text):
        if not text:
            return
        self.widget.after(0, self._append, text)
        # 写入日志文件（带时间戳）
        try:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self._log_path, "a", encoding="utf-8") as f:
                for line in text.rstrip("\n").split("\n"):
                    f.write(f"[{ts}] {line}\n")
        except Exception:
            pass
        return len(text)

    def _append(self, text):
        self.widget.insert(tk.END, text)
        self.widget.see(tk.END)

    def flush(self):
        pass


# ── 视频详情弹窗 ──────────────────────────────────────────

class VideoDetailWindow(tk.Toplevel):
    def __init__(self, parent, v: dict, title: str = "视频详情"):
        super().__init__(parent)
        self.title(title)
        self.geometry("600x500")
        self.minsize(500, 400)

        txt = scrolledtext.ScrolledText(self, wrap=tk.WORD, font=("Microsoft YaHei", 10))
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        lines = [
            f"标题: {v.get('title', '')}",
            f"BVID: {v.get('bvid', '')}",
            f"UP主: {v.get('owner_name', '')}  (mid: {v.get('owner_mid', '')})",
            f"分区: {v.get('tname', '')}",
            f"时长: {v.get('duration_str', _fmt_duration(v.get('duration', 0)))}",
            f"发布: {v.get('pubdate_str', datetime.datetime.fromtimestamp(v.get('pubdate', 0)).strftime('%Y-%m-%d %H:%M:%S') if v.get('pubdate') else '')}",
            f"",
            f"播放: {v.get('view', 0):_}  点赞: {v.get('like', 0):_}  收藏: {v.get('favorite', 0):_}  投币: {v.get('coin', 0):_}",
            f"分享: {v.get('share', 0):_}  评论: {v.get('reply', 0):_}  弹幕: {v.get('danmaku', 0):_}",
            f"UP主粉丝: {v.get('owner_fans', 0):_}",
            f"",
            f"热门: {'是' if v.get('is_hot') else '否'}  已关注: {'是' if v.get('is_followed') else '否'}",
            f"",
            f"标签: {', '.join(v.get('tags', [])[:8]) if isinstance(v.get('tags'), list) else v.get('tags', '')}",
            f"",
            f"简介:",
            f"{v.get('description', '')}",
        ]

        if "interest_score" in v or "total_score" in v:
            lines += [
                f"",
                f"━━ AI 评分 ━━",
                f"兴趣分: {v.get('interest_score', 'N/A')}  综合分: {v.get('total_score', 'N/A')}",
            ]

        txt.insert(tk.END, "\n".join(lines))
        txt.configure(state=tk.DISABLED)


# ══════════════════════════════════════════════════════════
#  主窗口
# ══════════════════════════════════════════════════════════

class BiliToolbox(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"B站工具箱 v{config.__version__}")
        self.geometry("1200x820")
        self.minsize(900, 600)

        # ── 状态 ──
        self.scraper = BiliScraper()
        self.credential = None
        self._videos = []          # list[BiliVideo] 当前获取的视频
        self._judged = []          # list[dict] 当前评分结果

        # ── 构建 UI ──
        self._build_ui()
        self._redirect_stdout()

        # 启动后初始化
        self.after(300, self._auto_check_login)
        self.after(500, self._refresh_data_files)
        self.after(600, self._refresh_judge_files)

    # ──────────────────── UI 构建 ────────────────────

    def _build_ui(self):
        # 主容器: 内容 + 底部日志
        main_pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # 顶部内容区 (Notebook)
        content = ttk.Frame(main_pane)
        main_pane.add(content, weight=3)

        self.notebook = ttk.Notebook(content)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_main = ttk.Frame(self.notebook)
        self.tab_judge = ttk.Frame(self.notebook)
        self.tab_data = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_main, text="首页推荐")
        self.notebook.add(self.tab_judge, text="AI评分")
        self.notebook.add(self.tab_data, text="数据浏览")
        self.notebook.add(self.tab_settings, text="设置")

        self._build_main_tab()
        self._build_judge_tab()
        self._build_data_tab()
        self._build_settings_tab()

        # 底部日志
        log_frame = ttk.LabelFrame(main_pane, text="日志输出")
        main_pane.add(log_frame, weight=1)
        self._log_text = scrolledtext.ScrolledText(
            log_frame, height=10, wrap=tk.WORD,
            font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white",
        )
        self._log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    # ─── Tab 1: 首页推荐 ─────────────────────────────

    def _build_main_tab(self):
        f = ttk.Frame(self.tab_main, padding=8)
        f.pack(fill=tk.BOTH, expand=True)

        # ── 登录栏 ──
        login_f = ttk.LabelFrame(f, text="登录管理", padding=6)
        login_f.pack(fill=tk.X, pady=(0, 6))

        btn_f = ttk.Frame(login_f)
        btn_f.pack(fill=tk.X)
        ttk.Button(btn_f, text="二维码登录", command=self._login_qrcode).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="检查登录", command=self._check_login).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="退出登录", command=self._logout).pack(side=tk.LEFT, padx=2)

        self._login_status_var = tk.StringVar(value="未登录")
        ttk.Label(btn_f, textvariable=self._login_status_var, foreground="gray").pack(side=tk.RIGHT, padx=8)

        # ── 操作栏 ──
        action_f = ttk.LabelFrame(f, text="视频获取", padding=6)
        action_f.pack(fill=tk.X, pady=(0, 6))

        row1 = ttk.Frame(action_f)
        row1.pack(fill=tk.X, pady=2)
        self._btn_rec = ttk.Button(row1, text="获取推荐", command=self._fetch_recommend)
        self._btn_rec.pack(side=tk.LEFT, padx=2)
        self._btn_hot = ttk.Button(row1, text="热门视频", command=self._fetch_hot)
        self._btn_hot.pack(side=tk.LEFT, padx=2)

        row2 = ttk.Frame(action_f)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="搜索:").pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self._search_var, width=25).pack(side=tk.LEFT, padx=2)
        ttk.Button(row2, text="搜索", command=self._search).pack(side=tk.LEFT, padx=2)

        ttk.Label(row2, text="  BV:").pack(side=tk.LEFT, padx=(10, 0))
        self._bvid_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self._bvid_var, width=18).pack(side=tk.LEFT, padx=2)
        ttk.Button(row2, text="查详情", command=self._fetch_info).pack(side=tk.LEFT, padx=2)

        self._full_data_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="补全完整数据", variable=self._full_data_var).pack(side=tk.LEFT, padx=(15, 0))

        # ── 视频列表 ──
        table_f = ttk.LabelFrame(f, text="视频列表", padding=4)
        table_f.pack(fill=tk.BOTH, expand=True)

        cols = ("bvid", "title", "owner", "view", "like", "time", "duration", "tags", "flags")
        self._tree = ttk.Treeview(table_f, columns=cols, show="headings",
                                   selectmode="extended", height=14)
        headings = [("bvid", "BVID", 120), ("title", "标题", 280), ("owner", "UP主", 100),
                     ("view", "播放", 75), ("like", "点赞", 75), ("time", "发布时间", 130),
                     ("duration", "时长", 70), ("tags", "标签", 140), ("flags", "标记", 70)]
        for key, text, w in headings:
            self._tree.heading(key, text=text, command=lambda k=key: self._sort_tree(k))
            self._tree.column(key, width=w, minwidth=50, anchor="center" if key not in ("title", "tags", "flags") else "w")

        vsb = ttk.Scrollbar(table_f, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.bind("<Double-1>", self._on_video_double_click)

        # ── 底栏 ──
        bottom = ttk.Frame(f)
        bottom.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(bottom, text="发送到 AI 评分", command=self._send_to_judge).pack(side=tk.LEFT, padx=2)
        self._count_var = tk.StringVar(value="共 0 条视频")
        ttk.Label(bottom, textvariable=self._count_var).pack(side=tk.RIGHT, padx=8)

    # ─── Tab 2: AI 评分 ──────────────────────────────

    def _build_judge_tab(self):
        f = ttk.Frame(self.tab_judge, padding=8)
        f.pack(fill=tk.BOTH, expand=True)

        # ── API Key ──
        api_f = ttk.LabelFrame(f, text="DeepSeek 配置", padding=6)
        api_f.pack(fill=tk.X, pady=(0, 6))

        row = ttk.Frame(api_f)
        row.pack(fill=tk.X)
        ttk.Label(row, text="API Key:").pack(side=tk.LEFT)
        self._api_key_var = tk.StringVar()
        self._api_key_entry = ttk.Entry(row, textvariable=self._api_key_var, width=50, show="*")
        self._api_key_entry.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
        ttk.Button(row, text="保存", width=8, command=self._save_api_key).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="显示", width=6, command=self._toggle_api_key_show).pack(side=tk.LEFT, padx=2)
        self._api_key_shown = False

        # 已有 key 提示
        if deepseek.get_api_key():
            key = deepseek.get_api_key()
            self._api_key_var.set(key[:12] + "…" + key[-4:] if len(key) > 20 else key)
            self._api_key_shown = False

        # ── 操作 ──
        ctrl_f = ttk.LabelFrame(f, text="评分操作", padding=6)
        ctrl_f.pack(fill=tk.X, pady=(0, 6))

        row1 = ttk.Frame(ctrl_f)
        row1.pack(fill=tk.X, pady=2)

        ttk.Label(row1, text="数据文件:").pack(side=tk.LEFT)
        self._judge_file_var = tk.StringVar()
        self._judge_file_combo = ttk.Combobox(row1, textvariable=self._judge_file_var, width=45, state="readonly")
        self._judge_file_combo.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
        ttk.Button(row1, text="刷新列表", command=self._refresh_judge_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(row1, text="加载", command=self._load_judge_file).pack(side=tk.LEFT, padx=2)

        row2 = ttk.Frame(ctrl_f)
        row2.pack(fill=tk.X, pady=2)
        self._btn_start_judge = ttk.Button(row2, text="开始评分", command=self._start_judge)
        self._btn_start_judge.pack(side=tk.LEFT, padx=2)
        ttk.Button(row2, text="从当前推荐加载 (Tab1)", command=self._load_from_current).pack(side=tk.LEFT, padx=2)
        ttk.Button(row2, text="查看历史评分", command=self._show_judge_history).pack(side=tk.LEFT, padx=2)

        # ── 结果列表 ──
        result_f = ttk.LabelFrame(f, text="评分结果", padding=4)
        result_f.pack(fill=tk.BOTH, expand=True)

        cols = ("title", "owner", "interest", "total", "view", "fans", "time", "duration", "flags")
        self._judge_tree = ttk.Treeview(result_f, columns=cols, show="headings",
                                         selectmode="extended", height=12)
        jhead = [("title", "标题", 300), ("owner", "UP主", 100),
                  ("interest", "兴趣分", 65), ("total", "综合分", 65),
                  ("view", "播放", 75), ("fans", "UP粉丝", 75),
                  ("time", "发布时间", 120), ("duration", "时长", 65),
                  ("flags", "标记", 65)]
        for key, text, w in jhead:
            self._judge_tree.heading(key, text=text, command=lambda k=key: self._sort_judge_tree(k))
            self._judge_tree.column(key, width=w, minwidth=50,
                                     anchor="center" if key not in ("title", "flags") else "w")

        jvsb = ttk.Scrollbar(result_f, orient=tk.VERTICAL, command=self._judge_tree.yview)
        self._judge_tree.configure(yscrollcommand=jvsb.set)
        self._judge_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        jvsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._judge_tree.bind("<Double-1>", self._on_judged_double_click)

        # ── 底栏 ──
        jbottom = ttk.Frame(f)
        jbottom.pack(fill=tk.X, pady=(4, 0))
        self._judge_count_var = tk.StringVar(value="共 0 条")
        ttk.Label(jbottom, textvariable=self._judge_count_var).pack(side=tk.RIGHT, padx=8)

    # ─── Tab 3: 数据浏览 ─────────────────────────────

    def _build_data_tab(self):
        f = ttk.Frame(self.tab_data, padding=8)
        f.pack(fill=tk.BOTH, expand=True)

        paned = ttk.PanedWindow(f, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # 左侧文件列表
        left = ttk.LabelFrame(paned, text="数据文件", padding=4)
        paned.add(left, weight=1)

        lbtn = ttk.Frame(left)
        lbtn.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(lbtn, text="刷新", command=self._refresh_data_files).pack(side=tk.LEFT, padx=2)

        self._data_file_listbox = tk.Listbox(left, font=("Consolas", 10), exportselection=False)
        lvsb = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self._data_file_listbox.yview)
        self._data_file_listbox.configure(yscrollcommand=lvsb.set)
        self._data_file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lvsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._data_file_listbox.bind("<<ListboxSelect>>", self._on_file_select)

        # 右侧预览
        right = ttk.LabelFrame(paned, text="内容预览", padding=4)
        paned.add(right, weight=2)

        self._preview_text = scrolledtext.ScrolledText(
            right, wrap=tk.WORD, font=("Consolas", 10), state=tk.DISABLED,
        )
        self._preview_text.pack(fill=tk.BOTH, expand=True)

    # ─── Tab 4: 设置 ─────────────────────────────────

    def _build_settings_tab(self):
        f = ttk.Frame(self.tab_settings, padding=8)
        f.pack(fill=tk.BOTH, expand=True)

        # ── 提示词配置 ──
        prompt_f = ttk.LabelFrame(f, text="AI 评分提示词", padding=6)
        prompt_f.pack(fill=tk.BOTH, expand=True)

        # 状态栏
        status_row = ttk.Frame(prompt_f)
        status_row.pack(fill=tk.X, pady=(0, 4))
        self._prompt_source_var = tk.StringVar(value="")
        ttk.Label(status_row, textvariable=self._prompt_source_var, foreground="gray").pack(side=tk.LEFT)

        # 编辑区
        self._prompt_text = scrolledtext.ScrolledText(
            prompt_f, wrap=tk.WORD, font=("Microsoft YaHei", 10),
            height=25,
        )
        self._prompt_text.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        # 按钮行
        btn_row = ttk.Frame(prompt_f)
        btn_row.pack(fill=tk.X)

        ttk.Button(btn_row, text="保存自定义提示词", command=self._save_custom_prompt).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="恢复默认提示词", command=self._reset_custom_prompt).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="重新加载", command=self._reload_prompt_display).pack(side=tk.LEFT, padx=2)

        self._reload_prompt_display()

    def _reload_prompt_display(self):
        """刷新提示词编辑器内容"""
        self._prompt_text.delete("1.0", tk.END)
        if deepseek.has_custom_prompt():
            source = "自定义提示词（custom_prompt.md）"
        else:
            source = "默认提示词（interest_scoring_prompt.md）"
        self._prompt_source_var.set(f"当前使用: {source}")
        self._prompt_text.insert(tk.END, deepseek.get_active_prompt())

    def _save_custom_prompt(self):
        text = self._prompt_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("提示", "提示词不能为空")
            return
        deepseek.set_custom_prompt(text)
        self._prompt_source_var.set("当前使用: 自定义提示词（custom_prompt.md）")
        print(f"[OK] 自定义提示词已保存 ({len(text)} 字符)")

    def _reset_custom_prompt(self):
        if not deepseek.has_custom_prompt():
            messagebox.showinfo("提示", "当前已经是默认提示词")
            return
        if messagebox.askyesno("确认", "恢复默认提示词将删除自定义内容，确定？"):
            deepseek.reset_custom_prompt()
            self._reload_prompt_display()
            print("[OK] 已恢复默认提示词")

    # ─── 底部日志重定向 ───────────────────────────────

    def _redirect_stdout(self):
        self._stdout_orig = sys.stdout
        sys.stdout = PrintRedirector(self._log_text)

    # ──────────────────── 登录操作 ────────────────────

    def _auto_check_login(self):
        cred = cookie_util.load_cache()
        if cred:
            self.credential = cred
            self.scraper.set_credential(cred)
            self._login_status_var.set("验证中…")
            self.after(100, self._check_login)
        else:
            self._login_status_var.set("未登录")

    def _check_login(self):
        def task():
            if not self.credential:
                print("[失败] 无缓存的登录凭证")
                self.after(0, lambda: self._login_status_var.set("未登录"))
                return
            try:
                from bilibili_api import user, sync
                info = sync(user.get_self_info(credential=self.credential))
                name = info.get("name", "")
                if name:
                    print(f"[OK] 已登录: {name}")
                    self.after(0, lambda: self._login_status_var.set(f"已登录: {name}"))
                else:
                    self.after(0, lambda: self._login_status_var.set("凭证无效"))
            except Exception as e:
                print(f"[失败] 登录检查出错: {e}")
                self.after(0, lambda: self._login_status_var.set("凭证过期"))
        threading.Thread(target=task, daemon=True).start()

    def _login_qrcode(self):
        def task():
            try:
                import webbrowser
                from bilibili_api import login_v2, sync

                self.after(0, lambda: self._login_status_var.set("生成二维码…"))
                ql = login_v2.QrCodeLogin()
                sync(ql.generate_qrcode())

                qr_name = f"qrcode_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                qr_path = os.path.join(str(config.CONFIG_DIR), qr_name)
                pic = ql.get_qrcode_picture()
                pic.to_file(qr_path)
                print(f"[OK] 二维码已保存: {qr_path}")
                webbrowser.open(qr_path)

                last_event = None
                while True:
                    event = sync(ql.check_state())
                    if event != last_event:
                        if event == login_v2.QrCodeLoginEvents.SCAN:
                            print("[OK] 已扫描，请在手机上确认…")
                        elif event == login_v2.QrCodeLoginEvents.CONF:
                            print("[OK] 已确认，登录中…")
                        elif event == login_v2.QrCodeLoginEvents.TIMEOUT:
                            print("[失败] 二维码已过期")
                            self.after(0, lambda: self._login_status_var.set("二维码过期"))
                            return
                        elif event == login_v2.QrCodeLoginEvents.DONE:
                            print("[OK] 登录成功！")
                            break
                        last_event = event

                credential = ql.get_credential()
                cookie_util._save_cache(credential)
                self.credential = credential
                self.scraper.set_credential(credential)
                self.after(0, self._check_login)
            except Exception as e:
                print(f"[失败] 登录出错: {e}")
        threading.Thread(target=task, daemon=True).start()

    def _logout(self):
        cookie_util.clear_cache()
        self.credential = None
        self.scraper = BiliScraper()
        self._login_status_var.set("未登录")
        print("[OK] 已退出登录")

    # ──────────────────── 视频获取 ────────────────────

    def _toggle_buttons(self, disable: bool, exclude=None):
        btns = [self._btn_rec, self._btn_hot, self._btn_start_judge]
        state = tk.DISABLED if disable else tk.NORMAL
        for b in btns:
            if b is exclude:
                continue
            try:
                b.configure(state=state)
            except tk.TclError:
                pass

    def _fetch_recommend(self):
        if not self.credential:
            messagebox.showwarning("提示", "需要先登录才能获取个性化推荐")
            return
        full = self._full_data_var.get()

        def task():
            self.after(0, lambda: self._toggle_buttons(True))
            self.after(0, lambda: self._btn_rec.configure(text="加载中…"))
            try:
                print(f"[OK] 正在获取个性化推荐{' (完整数据)' if full else ''}…")
                videos, hot_list = self.scraper.get_recommendations_with_hot_flag(full=full)
                self._videos = videos
                self._safe_refresh_tree()
            except Exception as e:
                print(f"[失败] 获取推荐出错: {e}")
            finally:
                self.after(0, lambda: self._btn_rec.configure(text="获取推荐"))
                self.after(0, lambda: self._toggle_buttons(False))
        threading.Thread(target=task, daemon=True).start()

    def _fetch_hot(self):
        def task():
            self.after(0, lambda: self._toggle_buttons(True))
            self.after(0, lambda: self._btn_hot.configure(text="加载中…"))
            try:
                print("[OK] 正在获取热门视频…")
                videos = self.scraper.get_hot(pn=1, ps=50)
                self._videos = videos
                self._safe_refresh_tree()
            except Exception as e:
                print(f"[失败] 获取热门出错: {e}")
            finally:
                self.after(0, lambda: self._btn_hot.configure(text="热门视频"))
                self.after(0, lambda: self._toggle_buttons(False))
        threading.Thread(target=task, daemon=True).start()

    def _search(self):
        keyword = self._search_var.get().strip()
        if not keyword:
            messagebox.showwarning("提示", "请输入搜索关键词")
            return

        def task():
            self.after(0, lambda: self._toggle_buttons(True))
            try:
                print(f"[OK] 正在搜索: {keyword}")
                videos = self.scraper.search(keyword)
                self._videos = videos
                self._safe_refresh_tree()
            except Exception as e:
                print(f"[失败] 搜索出错: {e}")
            finally:
                self.after(0, lambda: self._toggle_buttons(False))
        threading.Thread(target=task, daemon=True).start()

    def _fetch_info(self):
        bvid = self._bvid_var.get().strip()
        if not bvid:
            messagebox.showwarning("提示", "请输入 BV 号")
            return

        def task():
            try:
                print(f"[OK] 正在查询: {bvid}")
                v = self.scraper.get_video_info(bvid)
                self._videos = [v]
                self._safe_refresh_tree()
            except Exception as e:
                print(f"[失败] 查询出错: {e}")
        threading.Thread(target=task, daemon=True).start()

    # ─── 表格刷新（线程安全） ─────────────────────────

    def _safe_refresh_tree(self):
        """从后台线程调用：在主线程刷新视频列表"""
        self.after(0, self._do_refresh_tree)

    def _do_refresh_tree(self):
        """必须在主线程调用"""
        for item in self._tree.get_children():
            self._tree.delete(item)
        for v in self._videos:
            tags_short = ", ".join(v.tags[:3]) if v.tags else ""
            flags = []
            if v.is_hot:
                flags.append("🔥热门")
            if v.is_followed:
                flags.append("关注")
            self._tree.insert("", tk.END, values=(
                v.bvid,
                _short_title(v.title),
                v.owner_name,
                _fmt_count(v.view),
                _fmt_count(v.like),
                v.pubdate_str[5:16] if v.pubdate else "",
                v.duration_str,
                tags_short,
                "/".join(flags),
            ))
        self._count_var.set(f"共 {len(self._videos)} 条视频")
        print(f"[OK] 列表已更新: {len(self._videos)} 条")
        self._auto_save_videos()

    def _safe_refresh_judge_tree(self):
        """从后台线程调用：在主线程刷新评分列表"""
        self.after(0, self._do_refresh_judge_tree)

    def _do_refresh_judge_tree(self):
        """必须在主线程调用"""
        for item in self._judge_tree.get_children():
            self._judge_tree.delete(item)
        for v in self._judged:
            flags = []
            if v.get("is_hot"):
                flags.append("🔥热门")
            if v.get("is_followed"):
                flags.append("关注")
            dur = _fmt_duration(v.get("duration", 0))
            pub = v.get("pubdate", 0)
            if pub:
                pub_str = datetime.datetime.fromtimestamp(pub).strftime("%m-%d %H:%M")
            else:
                pub_str = v.get("pubdate_str", "")[5:16] if v.get("pubdate_str") else ""
            self._judge_tree.insert("", tk.END, values=(
                _short_title(v.get("title", "")),
                v.get("owner_name", ""),
                f"{v.get('interest_score', 0):.0f}",
                f"{v.get('total_score', 0):.0f}",
                _fmt_count(v.get("view", 0)),
                _fmt_count(v.get("owner_fans", 0)),
                pub_str,
                dur,
                "/".join(flags),
            ))
        self._judge_count_var.set(f"共 {len(self._judged)} 条")
        self._auto_save_judged()

    def _sort_tree(self, col):
        items = [(self._tree.set(k, col), k) for k in self._tree.get_children("")]
        reverse = getattr(self, "_tree_sort_rev", False)
        items.sort(key=lambda x: x[0], reverse=reverse)
        for idx, (_, k) in enumerate(items):
            self._tree.move(k, "", idx)
        self._tree_sort_rev = not reverse

    def _on_video_double_click(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        idx = self._tree.index(sel[0])
        if idx < len(self._videos):
            v = self._videos[idx]
            if isinstance(v, BiliVideo):
                VideoDetailWindow(self, v.to_dict(), title=v.short_title)
            else:
                VideoDetailWindow(self, v)

    # ─── 视频保存 / 发送 ─────────────────────────────

    def _auto_save_videos(self):
        """自动保存视频数据（无需人工确认）"""
        if not self._videos:
            return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bilibili_{ts}.json"
        path = self.scraper.save(self._videos, filename=filename)
        self.after(0, lambda: self._refresh_data_files())

    def _auto_save_judged(self):
        """自动保存评分结果（无需人工确认）"""
        if not self._judged:
            return
        try:
            path = save_results(self._judged)
            self.after(0, lambda: print(f"[OK] 评分结果已自动保存: {path}"))
        except Exception:
            pass

    def _save_videos(self):
        if not self._videos:
            messagebox.showwarning("提示", "没有可保存的视频")
            return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bilibili_{ts}.json"
        path = self.scraper.save(self._videos, filename=filename)
        print(f"[OK] 已保存到: {path}")
        self._refresh_data_files()

    def _send_to_judge(self):
        if not self._videos:
            messagebox.showwarning("提示", "没有视频可发送")
            return
        self.notebook.select(self.tab_judge)
        self._load_from_current()

    # ──────────────────── AI 评分 ────────────────────

    def _save_api_key(self):
        key = self._api_key_var.get().strip()
        if not key:
            messagebox.showwarning("提示", "请输入 API Key")
            return
        deepseek.set_api_key(key)
        print(f"[OK] API Key 已保存到 {config.CONFIG_FILE}")
        # 回显
        self._api_key_var.set(key[:12] + "…" + key[-4:] if len(key) > 20 else key)
        self._api_key_shown = False
        self._api_key_entry.configure(show="*")

    def _toggle_api_key_show(self):
        self._api_key_shown = not self._api_key_shown
        self._api_key_entry.configure(show="" if self._api_key_shown else "*")
        if not self._api_key_shown and len(self._api_key_var.get()) > 16:
            k = self._api_key_var.get()
            self._api_key_var.set(k[:12] + "…" + k[-4:])

    def _refresh_judge_files(self):
        """刷新数据文件下拉列表"""
        news_dir = config.get_news_data_dir()
        judge_dir = config.get_judge_data_dir()
        files = []
        if os.path.isdir(news_dir):
            files += [f for f in sorted(os.listdir(news_dir)) if f.endswith(".json")]
        if os.path.isdir(judge_dir):
            files += [f for f in sorted(os.listdir(judge_dir)) if f.endswith(".json")]
        self._judge_file_combo["values"] = sorted(set(files))

    def _get_judge_file_path(self, filename: str) -> str:
        """在多个数据目录中查找文件"""
        candidates = [
            os.path.join(config.get_news_data_dir(), filename),
            os.path.join(config.get_judge_data_dir(), filename),
            filename,
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
        return candidates[0]

    def _load_judge_file(self):
        fname = self._judge_file_var.get()
        if not fname:
            messagebox.showwarning("提示", "请先选择数据文件")
            return
        path = self._get_judge_file_path(fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            videos = raw.get("videos", raw.get("results", raw.get("recommend", [])))
            if not videos and isinstance(raw, list):
                videos = raw
            print(f"[OK] 已加载 {len(videos)} 条视频: {fname}")
            self._judge_loaded = videos
        except Exception as e:
            print(f"[失败] 加载文件出错: {e}")

    def _load_from_current(self):
        if not self._videos:
            messagebox.showwarning("提示", "Tab1 中没有视频数据")
            return
        self._judge_loaded = [v.to_dict() if isinstance(v, BiliVideo) else v for v in self._videos]
        print(f"[OK] 已从当前推荐加载 {len(self._judge_loaded)} 条视频")

    def _start_judge(self):
        if not hasattr(self, "_judge_loaded") or not self._judge_loaded:
            # 尝试从文件加载
            fname = self._judge_file_var.get()
            if fname:
                self._load_judge_file()
            if not hasattr(self, "_judge_loaded") or not self._judge_loaded:
                messagebox.showwarning("提示", "请先加载视频数据（选择文件或从 Tab1 加载）")
                return

        api_key = deepseek.get_api_key()
        if not api_key:
            messagebox.showwarning("提示", "请先设置 DeepSeek API Key")
            return

        def task():
            self.after(0, lambda: self._toggle_buttons(True, exclude=self._btn_start_judge))
            self.after(0, lambda: self._btn_start_judge.configure(text="评分中…"))
            try:
                results = judge_batch(
                    self._judge_loaded,
                    credential=self.credential,
                    api_key=api_key,
                    max_count=50,
                )
                self._judged = results
                self._safe_refresh_judge_tree()
                print(f"[OK] 评分完成: {len(results)} 条通过筛选")
            except Exception as e:
                print(f"[失败] 评分出错: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self.after(0, lambda: self._btn_start_judge.configure(text="开始评分"))
                self.after(0, lambda: self._toggle_buttons(False))
        threading.Thread(target=task, daemon=True).start()

    def _sort_judge_tree(self, col):
        items = [(self._judge_tree.set(k, col), k) for k in self._judge_tree.get_children("")]
        reverse = getattr(self, "_judge_sort_rev", False)
        items.sort(key=lambda x: x[0], reverse=reverse)
        for idx, (_, k) in enumerate(items):
            self._judge_tree.move(k, "", idx)
        self._judge_sort_rev = not reverse

    def _on_judged_double_click(self, event):
        sel = self._judge_tree.selection()
        if not sel:
            return
        idx = self._judge_tree.index(sel[0])
        if idx < len(self._judged):
            v = self._judged[idx]
            # 打开浏览器播放
            url = v.get("url") or f"https://www.bilibili.com/video/{v.get('bvid', '')}"
            import webbrowser
            webbrowser.open(url)
            print(f"[OK] 已打开浏览器: {v.get('title', '')[:30]}…")

    def _save_judged(self):
        if not self._judged:
            messagebox.showwarning("提示", "没有评分结果可保存")
            return
        try:
            path = save_results(self._judged)
            print(f"[OK] 评分结果已保存: {path}")
        except Exception as e:
            print(f"[失败] 保存出错: {e}")

    def _show_judge_history(self):
        files = list_judged()
        if not files:
            print("(暂无历史评分结果)")
            return
        print(f"\n历史评分结果 ({len(files)} 个):")
        for f in files[-10:]:
            path = os.path.join(config.get_judge_data_dir(), f)
            size = os.path.getsize(path)
            print(f"  {f}  ({size / 1024:.1f} KB)")

    # ──────────────────── 数据浏览 ────────────────────

    def _refresh_data_files(self):
        self._data_file_listbox.delete(0, tk.END)
        dirs = [
            config.get_news_data_dir(),
            config.get_judge_data_dir(),
        ]
        all_files = []
        for d in dirs:
            if os.path.isdir(d):
                for f in sorted(os.listdir(d), reverse=True):
                    if f.endswith(".json"):
                        size = os.path.getsize(os.path.join(d, f))
                        all_files.append((f, size, d))
        for fname, size, _ in all_files[:100]:
            self._data_file_listbox.insert(tk.END, f"  {fname}  ({size / 1024:.1f} KB)")

    def _on_file_select(self, event):
        sel = self._data_file_listbox.curselection()
        if not sel:
            return
        raw = self._data_file_listbox.get(sel[0])
        fname = raw.strip().split("  (")[0]

        # 查找文件
        for d in [config.get_news_data_dir(), config.get_judge_data_dir()]:
            path = os.path.join(d, fname)
            if os.path.isfile(path):
                break
        else:
            self._show_preview(f"[文件未找到: {fname}]")
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            formatted = json.dumps(data, ensure_ascii=False, indent=2)
            # 如果太长只显示前 5000 字符
            if len(formatted) > 5000:
                formatted = formatted[:5000] + f"\n\n… (剩余 {len(formatted) - 5000} 字符)"
            self._show_preview(formatted)
        except Exception as e:
            self._show_preview(f"[读取失败: {e}]")

    def _show_preview(self, text: str):
        self._preview_text.configure(state=tk.NORMAL)
        self._preview_text.delete("1.0", tk.END)
        self._preview_text.insert(tk.END, text)
        self._preview_text.configure(state=tk.DISABLED)


# ══════════════════════════════════════════════════════════
#  启动
# ══════════════════════════════════════════════════════════

def _init_bundle_paths():
    """PyInstaller 单文件模式：统一使用用户主目录存放配置和数据"""
    if not getattr(sys, 'frozen', False):
        return

    home = os.path.expanduser("~")
    os.environ["BILI_TOOLBOX_CONFIG_DIR"] = os.path.join(home, ".bilibili_toolbox")

    # 重新加载 config 模块以应用新路径
    import config as cfg
    cfg.CONFIG_DIR = cfg.get_config_dir()
    cfg.CONFIG_FILE = cfg.CONFIG_DIR / "config.json"
    cfg.CREDENTIAL_CACHE_FILE = cfg.CONFIG_DIR / "credential_cache.json"
    cfg.PROMPTS_DIR = cfg.CONFIG_DIR / "prompts"
    cfg.NEWS_DATA_DIR = cfg.CONFIG_DIR / "news_data"
    cfg.JUDGE_DATA_DIR = cfg.CONFIG_DIR / "judge_data"
    cfg.ensure_dirs()

    # 同步更新各模块的引用
    import bilibili_news.scraper as ns
    ns.DATA_DIR = config.get_news_data_dir()

    import bilibili_news.cookie_util as cu
    cu.CACHE_FILE = config.get_cookies_path()

    import bilibili_judge.judger as jg
    jg.DATA_DIR = config.get_judge_data_dir()


def main():
    _init_bundle_paths()
    # Windows GBK 支持
    if sys.platform == "win32" and sys.stdout is not None:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    app = BiliToolbox()
    app.mainloop()


if __name__ == "__main__":
    main()
