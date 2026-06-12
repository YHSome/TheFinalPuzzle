#!/usr/bin/env python3
"""
TheFinalPuzzle — Claude Auto-Responder
======================================
自动监测 Claude Code 窗口，当出现选项提示时自动按下 Enter 键。

每轮: 截图 → OCR → 检测 → 按键 → 清屏 → 刷新仪表盘 → 等待。

依赖:
    pip install pyautogui pillow pytesseract pynput rich pywin32
    Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from typing import Deque, List, Optional, Tuple

# ------------------------------------------------------------------ 依赖导入
def _exit(msg: str = "", code: int = 1):
    """退出前等待用户按键，避免双击运行时窗口直接消失。"""
    if msg:
        print(msg)
    input("\n按回车键退出...")
    sys.exit(code)


try:
    import pyautogui
except ImportError:
    _exit("[ERROR] pyautogui 未安装: pip install pyautogui")
try:
    from PIL import Image
except ImportError:
    _exit("[ERROR] pillow 未安装: pip install pillow")
try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    pytesseract = None; HAS_TESSERACT = False
try:
    from pynput.keyboard import Controller as KBController, Key, Listener
    HAS_PYNPUT = True
except ImportError:
    _exit("[ERROR] pynput 未安装: pip install pynput")
try:
    import win32gui, win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
try:
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.console import Console
    from rich import box
    from rich.align import Align
except ImportError:
    _exit("[ERROR] rich 未安装: pip install rich")

console = Console()

# ------------------------------------------------------------------ 提示模式
# ------------------------------------------------------------------ 提示检测（简化版）
def detect_prompt(text: str) -> Tuple[bool, str]:
    """检测文本中是否同时包含 Yes 和 No（不区分大小写）或中文 是+否。"""
    t = text.lower()
    # 英文: 同时出现 yes 和 no
    if re.search(r'\byes\b', t) and re.search(r'\bno\b', t):
        return True, "Yes + No"
    # 中文: 同时出现 是 和 否
    if '是' in text and '否' in text:
        return True, "是 + 否"
    # 中文: 确认 / 继续 等直接提示词
    if re.search(r'是否\s*(?:继续|确认|执行|运行)?', text):
        return True, "是否..."
    if re.search(r'确认\s*(?:继续|执行|操作)?', text):
        return True, "确认..."
    return False, ""

# ------------------------------------------------------------------ 配置
@dataclass
class Config:
    window_title: str = ""
    interval: float = 5.0
    cooldown: float = 5.0
    dry_run: bool = False
    blind_mode: bool = False
    tesseract_cmd: Optional[str] = None
    crop_bottom_ratio: float = 0.30
    save_screenshots: bool = False
    screenshot_dir: str = "./screenshots"
    pause_hotkey: str = "f8"

    @property
    def mode_label(self) -> str:
        return "BLIND" if self.blind_mode else "OCR"

# ------------------------------------------------------------------ 全局状态
paused = False
shutdown = False
hotkey_flag = False
last_user_key_time = 0.0  # 用户最后一次按键时间，用于防止抢键盘

# 统计
check_count   = 0
detect_count  = 0
enter_count   = 0
start_time    = time.time()
last_check_time   = 0.0
last_enter_time   = 0.0
last_detect_time  = 0.0

# OCR
ocr_lines: List[str]      = []
last_match: str           = ""
last_error: str           = ""

# 日志
events: Deque[Tuple[float, str, str]] = deque(maxlen=100)
timeline: Deque[int] = deque(maxlen=60)  # 0=none, 1=detected, 2=pressed

# ------------------------------------------------------------------ 窗口
def find_window(title_pattern: str) -> Optional[Tuple[int, int, int, int]]:
    if HAS_WIN32:
        result: Optional[Tuple[int, int, int, int]] = None
        def _cb(hwnd, _):
            nonlocal result
            if not win32gui.IsWindowVisible(hwnd): return True
            try: text = win32gui.GetWindowText(hwnd)
            except Exception: return True
            if title_pattern.lower() in text.lower():
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    time.sleep(0.3)
                rect = win32gui.GetWindowRect(hwnd)
                result = (rect[0], rect[1], rect[2]-rect[0], rect[3]-rect[1])
                return False
            return True
        win32gui.EnumWindows(_cb, None)
        if result: return result
    try:
        wins = pyautogui.getWindowsWithTitle(title_pattern)
        if wins:
            w = wins[0]
            if w.isMinimized: w.restore(); time.sleep(0.3)
            return (w.left, w.top, w.width, w.height)
    except Exception: pass
    return None

def get_active_window() -> Tuple[int, int, int, int]:
    if HAS_WIN32:
        hwnd = win32gui.GetForegroundWindow()
        rect = win32gui.GetWindowRect(hwnd)
        return (rect[0], rect[1], rect[2]-rect[0], rect[3]-rect[1])
    size = pyautogui.size()
    return (0, 0, size.width, size.height)

# ------------------------------------------------------------------ 截图 + OCR
def capture(region: Tuple[int, int, int, int], crop_bottom: float) -> Image.Image:
    left, top, width, height = region
    if 0 < crop_bottom < 1:
        ct = top + int(height * (1 - crop_bottom))
        ch = int(height * crop_bottom)
        return pyautogui.screenshot(region=(left, ct, width, ch))
    return pyautogui.screenshot(region=(left, top, width, height))

def ocr(image: Image.Image, tesseract_cmd: Optional[str] = None) -> str:
    if tesseract_cmd: pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    gray = image.convert("L")
    enhanced = gray.point(lambda x: min(255, max(0, int((x - 30) * 1.5))))
    try:
        return pytesseract.image_to_string(enhanced, lang="eng+chi_sim", config="--psm 3")
    except pytesseract.TesseractError:
        return pytesseract.image_to_string(enhanced, lang="eng", config="--psm 3")

# ------------------------------------------------------------------ 按键
def press_enter() -> bool:
    try:
        kb = KBController()
        kb.press(Key.enter); kb.release(Key.enter)
        return True
    except Exception: return False

# ------------------------------------------------------------------ 热键
def hotkey_listener(hotkey: str):
    global hotkey_flag, last_user_key_time
    def _on_press(key):
        global hotkey_flag, last_user_key_time
        try:
            last_user_key_time = time.time()
            if (getattr(key, 'name', None) or str(key)).lower() == hotkey.lower():
                hotkey_flag = True
        except Exception: pass
    listener = Listener(on_press=_on_press)
    listener.daemon = True
    listener.start()
    while not shutdown: time.sleep(0.5)

# ------------------------------------------------------------------ 仪表盘
def render_dashboard(cfg: Config, next_check_time: float = 0) -> Layout:
    global paused, check_count, detect_count, enter_count, start_time
    global last_check_time, last_enter_time, last_detect_time
    global ocr_lines, last_match, last_error, events, timeline

    uptime = time.time() - start_time
    uptime_str = f"{int(uptime//3600):02d}:{int(uptime%3600//60):02d}:{int(uptime%60):02d}"
    now = time.time()
    cooldown_active = (now - last_enter_time < cfg.cooldown) and last_enter_time > 0

    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="stats", size=5),
        Layout(name="timeline_bar", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="ocr_preview", ratio=1),
        Layout(name="events", ratio=1),
    )

    # -- Header --
    status_icon = "[dim]|| 已暂停[/]" if paused else "[green]> 运行中[/]"
    dry_badge = " [yellow]DRY-RUN[/]" if cfg.dry_run else ""
    status_line = (
        f"{status_icon}[white]{dry_badge}[/]  "
        f"Mode: [cyan]{cfg.mode_label}[/]  "
        f"Interval: [cyan]{cfg.interval:.0f}s[/]  "
        f"Cooldown: [cyan]{cfg.cooldown:.0f}s[/]  "
        f"Window: [cyan]{cfg.window_title or 'active'}[/]"
    )
    layout["header"].update(Panel(
        Align.center(f"[bold white]TheFinalPuzzle[/]\n{status_line}"),
        box=box.HEAVY, border_style="bright_cyan"))

    # -- Stats --
    def _ago(ts: float) -> str:
        if ts == 0: return "--"
        ago = int(now - ts) + 1
        if ago < 60: return f"{ago}s ago"
        elif ago < 3600: return f"{ago//60}m ago"
        else: return f"{ago//3600}h ago"

    # 倒计时
    if paused:
        ttd = "[dim]paused[/]"
    elif next_check_time > 0:
        remaining = max(0, next_check_time - now)
        ttd = f"[cyan]{remaining:.0f}s[/]"
    else:
        ttd = "[dim]--[/]"
    stats_text = (
        f" Checks: {check_count:<6}  Detected: {detect_count:<6}  "
        f"Enter: [bold green]{enter_count}[/]  Uptime: {uptime_str}\n"
        f" Last check: {_ago(last_check_time):<12}  "
        f"Last detect: {_ago(last_detect_time):<12}  "
        f"Last enter: {_ago(last_enter_time):<12}  "
        f"Next check: {ttd}"
    )
    layout["stats"].update(Panel(stats_text, box=box.ROUNDED, border_style="blue"))

    # -- Timeline --
    tl = list(timeline)[-60:]
    if tl:
        bar_chars = {0: "[dim]-[/]", 1: "[yellow]|[/]", 2: "[green]#[/]"}
        bar = "".join(bar_chars.get(v, "[dim]-[/]") for v in tl)
        bar += "[cyan]>[/]"  # 下一个检测位置
    else:
        bar = "[dim]waiting for data...[/]"
    tl_label = ("  [dim]- none[/]  [yellow]| detected[/]  [green]# pressed[/]  "
                "[cyan]> current[/]  "
                f"[dim](last {min(len(timeline), 60)})[/]")
    layout["timeline_bar"].update(Panel(
        f"{bar}\n{tl_label}",
        box=box.ROUNDED, border_style="magenta", title="Activity Timeline"))

    # -- OCR --
    if ocr_lines:
        preview = "\n".join(f"  [dim]|[/] {l}" for l in ocr_lines[-10:])
    else:
        preview = "  [dim]waiting for OCR...[/]"
    extra = ""
    if last_match: extra += f"\n  [yellow]Last match:[/] [bold yellow]{last_match}[/]"
    if cooldown_active: extra += "  [yellow](cooldown...)[/]"
    if last_error: extra += f"\n  [red]Error: {last_error}[/]"
    layout["ocr_preview"].update(Panel(
        preview + extra,
        box=box.ROUNDED, border_style="green", title="OCR Result (bottom of window)"))

    # -- Events --
    parts = []
    for ts, etype, detail in reversed(list(events)[-20:]):
        dt = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        icons = {"ok": "[green]OK[/]", "dry": "[yellow]--[/]", "cool": "[dim]..[/]", "err": "[red]!![/]"}
        icon = icons.get(etype, "[dim] .[/]")
        parts.append(f"  {icon} [dim]{dt}[/] {detail}")
    layout["events"].update(Panel(
        "\n".join(parts) if parts else "  [dim]no events[/]",
        box=box.ROUNDED, border_style="yellow", title="Event Log (newest first)"))

    # -- Footer --
    mode_text = "[yellow]DRY-RUN (no key press)[/]" if cfg.dry_run else "[green]LIVE (will press Enter)[/]"
    f8_text = "[green]F8: resume[/]" if paused else "[dim]F8: pause[/]"
    layout["footer"].update(Panel(
        Align.center(f"{f8_text}  |  [dim]Ctrl+C: exit[/]  |  {mode_text}"),
        box=box.ROUNDED, border_style="bright_black"))

    return layout

def show_dashboard(cfg: Config, next_check_time: float = 0):
    """清屏 + 渲染仪表盘。"""
    with console.capture() as capture:
        console.print(render_dashboard(cfg, next_check_time))
    frame = capture.get()
    os.system('cls' if os.name == 'nt' else 'clear')
    sys.stdout.write(frame)
    sys.stdout.flush()

# ------------------------------------------------------------------ 一轮检测
def do_check(cfg: Config, region: Optional[Tuple[int, int, int, int]]):
    """执行一轮 OCR 检测 + 按键。直接修改全局状态。"""
    global check_count, detect_count, enter_count
    global last_check_time, last_enter_time, last_detect_time
    global ocr_lines, last_match, last_error, events, timeline
    global last_user_key_time

    now = time.time()
    last_check_time = now

    # 用户手动操作了键盘 → 不抢键盘
    user_active = (now - last_user_key_time < cfg.cooldown)

    # 盲模式
    if cfg.blind_mode:
        if now - last_enter_time < cfg.cooldown:
            events.append((now, "cool", "Blind mode, cooldown active"))
            timeline.append(0)
            return
        if user_active:
            events.append((now, "cool", "Blind mode, user typing, skipped"))
            timeline.append(1)
            return
        if cfg.dry_run:
            enter_count += 1; last_enter_time = now
            events.append((now, "dry", "Blind mode, simulated Enter"))
            timeline.append(2)
        else:
            if press_enter():
                enter_count += 1; last_enter_time = now
                events.append((now, "ok", "Blind mode, Enter pressed"))
                timeline.append(2)
            else:
                last_error = "Key press failed"
                events.append((now, "err", "Blind mode, press failed!"))
                timeline.append(0)
        check_count += 1
        return

    # OCR 模式
    if region is None:
        region = get_active_window()

    # 截图
    try:
        img = capture(region, cfg.crop_bottom_ratio)
    except Exception as e:
        last_error = f"Screenshot failed: {e}"
        timeline.append(0)
        return

    # OCR
    try:
        text = ocr(img, cfg.tesseract_cmd)
    except pytesseract.TesseractNotFoundError:
        last_error = "Tesseract not found! Install it or use --blind"
        timeline.append(0)
        return
    except Exception as e:
        last_error = f"OCR failed: {e}"
        timeline.append(0)
        return

    ocr_lines = [l.strip() for l in text.splitlines() if l.strip()]
    last_error = ""
    check_count += 1

    # 检测
    detected, matched = detect_prompt(text)
    if not detected:
        timeline.append(0)
        return

    detect_count += 1
    last_detect_time = now
    last_match = matched

    # 冷却
    if now - last_enter_time < cfg.cooldown:
        events.append((now, "cool", f"Detected: {matched} (cooldown)"))
        timeline.append(1)
        return

    # 用户键盘活动 → 不抢键盘
    if user_active:
        events.append((now, "cool", f"Detected: {matched} (user typing, skipped)"))
        timeline.append(1)
        return

    # 按键
    if cfg.dry_run:
        enter_count += 1; last_enter_time = now
        events.append((now, "dry", f"Detected: {matched} (simulated)"))
        timeline.append(2)
    else:
        if press_enter():
            enter_count += 1; last_enter_time = now
            events.append((now, "ok", f"Detected: {matched} -> Enter pressed"))
            timeline.append(2)
        else:
            last_error = "Key press failed"
            events.append((now, "err", f"Detected: {matched} -> press FAILED!"))
            timeline.append(1)

# ------------------------------------------------------------------ 主函数
def parse_args() -> Config:
    p = argparse.ArgumentParser(
        description="TheFinalPuzzle — Claude Auto-Responder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                         OCR mode, monitor active window
  %(prog)s --blind -i 10           Blind mode, press Enter every 10s
  %(prog)s --dry-run               Detect only, don't press Enter
  %(prog)s -t "Claude Code"        Monitor window with matching title
        """,
    )
    p.add_argument("--title", "-t", default="", help="Window title match (empty = active window)")
    p.add_argument("--interval", "-i", type=float, default=5.0, help="Check interval in seconds (default: 5)")
    p.add_argument("--cooldown", "-c", type=float, default=5.0, help="Min seconds between Enter presses (default: 5)")
    p.add_argument("--blind", "-b", action="store_true", help="Blind mode (no OCR, just press Enter periodically)")
    p.add_argument("--dry-run", "-n", action="store_true", help="Detect only, do not actually press Enter")
    p.add_argument("--tesseract-cmd", default=None, help="Path to tesseract executable")
    p.add_argument("--save-screenshots", action="store_true", help="Save screenshots for debugging")
    p.add_argument("--pause-hotkey", default="f8", help="Pause/resume hotkey (default: f8)")
    args = p.parse_args()
    return Config(
        window_title=args.title,
        interval=max(1.0, args.interval),
        cooldown=max(1.0, args.cooldown),
        dry_run=args.dry_run,
        blind_mode=args.blind,
        tesseract_cmd=args.tesseract_cmd,
        save_screenshots=args.save_screenshots,
        pause_hotkey=args.pause_hotkey,
    )

def main():
    global paused, shutdown, hotkey_flag, start_time

    if hasattr(sys.stdout, "reconfigure"):
        try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass

    cfg = parse_args()

    if not cfg.blind_mode and not HAS_TESSERACT:
        console.print("[red]pytesseract not installed, OCR mode unavailable.[/]")
        console.print("Run: pip install pytesseract")
        console.print("Or use blind mode: --blind")
        _exit()

    # Tesseract 路径
    if cfg.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = cfg.tesseract_cmd
    elif HAS_TESSERACT:
        for p in [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
            "/usr/bin/tesseract", "/usr/local/bin/tesseract", "/opt/homebrew/bin/tesseract",
        ]:
            if os.path.exists(p): pytesseract.pytesseract.tesseract_cmd = p; break

    # 窗口
    region: Optional[Tuple[int, int, int, int]] = None
    if not cfg.blind_mode and cfg.window_title:
        region = find_window(cfg.window_title)
        if region is None:
            console.print(f"[red]Window not found: '{cfg.window_title}'[/]")
            _exit()
        console.print(f"[green]Window found:[/] {region}")

    start_time = time.time()

    # 热键线程
    t_hk = Thread(target=hotkey_listener, args=(cfg.pause_hotkey,), daemon=True)
    t_hk.start()

    # 主循环：每秒刷新仪表盘，按间隔执行检测
    next_check_time = time.time()  # 首次立即检测
    try:
        while not shutdown:
            now = time.time()

            # 热键处理
            if hotkey_flag:
                hotkey_flag = False
                paused = not paused

            # 到时间了且未暂停 → 检测
            if not paused and now >= next_check_time:
                do_check(cfg, region)
                next_check_time = time.time() + cfg.interval

            show_dashboard(cfg, next_check_time)
            time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        shutdown = True
        t_hk.join(timeout=1)
        console.print()
        console.print(f"[bold]Final:[/] checks={check_count} detected={detect_count} enters={enter_count}")
        console.print("[dim]Exited[/]")
        input("\n按回车键退出...")

if __name__ == "__main__":
    main()
