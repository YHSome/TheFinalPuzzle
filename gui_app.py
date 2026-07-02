#!/usr/bin/env python3
"""
TheFinalPuzzle — GUI Frontend
=============================
PySide6 图形界面，替代原命令行仪表盘。

功能:
  - 实时统计面板 (检测次数、按下次数、在线时长)
  - 活动时间线可视化
  - OCR 预览区
  - 事件日志表
  - 系统托盘支持 (最小化到托盘)
  - 设置对话框 (OCR/盲模式、间隔、冷却、窗口标题等)

用法:
    python gui_app.py

依赖:
    pip install PySide6 pyautogui pillow pytesseract pynput pywin32
"""

from __future__ import annotations

import os
import re
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from typing import Deque, List, Optional, Tuple

# ============================================================================
# 依赖检查
# ============================================================================

MISSING_DEPS: List[str] = []

try:
    import pyautogui
except ImportError:
    MISSING_DEPS.append("pyautogui")

try:
    from PIL import Image
except ImportError:
    MISSING_DEPS.append("pillow")

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    pytesseract = None
    HAS_TESSERACT = False

try:
    from pynput.keyboard import Controller as KBController, Key, Listener
    HAS_PYNPUT = True
except ImportError:
    MISSING_DEPS.append("pynput")

try:
    import win32gui
    import win32con
    HAS_WIN32 = True
except ImportError:
    MISSING_DEPS.append("pywin32")

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QTextEdit, QTableWidget, QTableWidgetItem,
        QSplitter, QGroupBox, QGridLayout, QStatusBar, QSystemTrayIcon,
        QMenu, QMessageBox, QDialog, QDialogButtonBox, QFormLayout,
        QLineEdit, QDoubleSpinBox, QCheckBox, QFrame, QHeaderView,
        QStyle, QSizePolicy, QAbstractItemView,
    )
    from PySide6.QtCore import (
        Qt, QThread, Signal, Slot, QTimer, QRect, QSize,
    )
    from PySide6.QtGui import (
        QIcon, QPainter, QColor, QPen, QBrush, QFont, QAction,
        QPalette,
    )
    HAS_PYSIDE6 = True
except ImportError:
    MISSING_DEPS.append("PySide6")
    HAS_PYSIDE6 = False


def check_deps() -> None:
    if MISSING_DEPS:
        print("缺少依赖，请运行:")
        print(f"  pip install {' '.join(MISSING_DEPS)}")
        print("\nTesseract OCR 需要单独安装: https://github.com/UB-Mannheim/tesseract/wiki")
        sys.exit(1)
    if not HAS_TESSERACT:
        print("警告: pytesseract 未安装，仅支持盲模式 (Blind Mode)")


# ============================================================================
# 样式常量
# ============================================================================

DARK_STYLE = """
QMainWindow {
    background-color: #1a1a2e;
    color: #e0e0e0;
}

QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 13px;
}

QGroupBox {
    border: 2px solid #2d2d5e;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 16px;
    font-weight: bold;
    color: #7ec8e3;
    background-color: #16213e;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
    color: #7ec8e3;
}

QPushButton {
    background-color: #2d2d5e;
    color: #e0e0e0;
    border: 1px solid #3d3d7e;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
    min-width: 80px;
}

QPushButton:hover {
    background-color: #3d3d7e;
    border-color: #5d5dae;
}

QPushButton:pressed {
    background-color: #1d1d4e;
}

QPushButton:disabled {
    background-color: #2a2a3a;
    color: #666;
    border-color: #333;
}

QPushButton#startBtn {
    background-color: #1a6b3c;
    border-color: #2a8b5c;
}

QPushButton#startBtn:hover {
    background-color: #2a8b5c;
}

QPushButton#pauseBtn {
    background-color: #8b6f00;
    border-color: #ab8f20;
}

QPushButton#pauseBtn:hover {
    background-color: #ab8f20;
}

QLabel {
    color: #e0e0e0;
    background: transparent;
}

QLabel#statValue {
    color: #4fc3f7;
    font-size: 18px;
    font-weight: bold;
    font-family: "Consolas", "Cascadia Code", monospace;
}

QLabel#statLabel {
    color: #999;
    font-size: 12px;
}

QLabel#headerTitle {
    color: #7ec8e3;
    font-size: 20px;
    font-weight: bold;
}

QTextEdit {
    background-color: #0d1117;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 4px;
    font-family: "Consolas", "Cascadia Code", "Courier New", monospace;
    font-size: 12px;
}

QTableWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 4px;
    gridline-color: #21262d;
    font-size: 12px;
    alternate-background-color: #161b22;
}

QTableWidget::item {
    padding: 2px 8px;
}

QHeaderView::section {
    background-color: #161b22;
    color: #8b949e;
    border: 1px solid #30363d;
    padding: 4px 8px;
    font-weight: bold;
}

QLineEdit, QDoubleSpinBox, QComboBox {
    background-color: #0d1117;
    color: #e0e0e0;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 4px 8px;
}

QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #58a6ff;
}

QCheckBox {
    color: #e0e0e0;
}

QStatusBar {
    background-color: #16213e;
    color: #8b949e;
    border-top: 1px solid #30363d;
}

QSplitter::handle {
    background-color: #30363d;
    width: 2px;
}

QScrollBar:vertical {
    background-color: #0d1117;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #30363d;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #484f58;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

# 颜色映射（用于状态指示灯等）
COLOR_GREEN = QColor(0x2e, 0xcc, 0x71)
COLOR_YELLOW = QColor(0xf1, 0xc4, 0x0f)
COLOR_RED = QColor(0xe7, 0x4c, 0x3c)
COLOR_CYAN = QColor(0x4f, 0xc3, 0xf7)
COLOR_DIM = QColor(0x66, 0x66, 0x66)
COLOR_BG_DARK = QColor(0x0d, 0x11, 0x17)

# ============================================================================
# 核心功能（从原 claude_auto_responder.py 移植）
# ============================================================================

def detect_prompt(text: str) -> Tuple[bool, str]:
    """检测文本中是否包含选项提示 (Yes/No 或 是/否)。"""
    t = text.lower()
    if re.search(r'\byes\b', t) and re.search(r'\bno\b', t):
        return True, "Yes + No"
    if '是' in text and '否' in text:
        return True, "是 + 否"
    if re.search(r'是否\s*(?:继续|确认|执行|运行)?', text):
        return True, "是否..."
    if re.search(r'确认\s*(?:继续|执行|操作)?', text):
        return True, "确认..."
    return False, ""


def find_window(title_pattern: str) -> Optional[Tuple[int, int, int, int]]:
    """根据标题查找窗口，返回 (x, y, w, h)。"""
    if HAS_WIN32:
        result: Optional[Tuple[int, int, int, int]] = None

        def _cb(hwnd, _):
            nonlocal result
            if not win32gui.IsWindowVisible(hwnd):
                return True
            try:
                text = win32gui.GetWindowText(hwnd)
            except Exception:
                return True
            if title_pattern.lower() in text.lower():
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    time.sleep(0.3)
                rect = win32gui.GetWindowRect(hwnd)
                result = (rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])
                return False
            return True

        win32gui.EnumWindows(_cb, None)
        if result:
            return result
    # fallback: pyautogui
    try:
        wins = pyautogui.getWindowsWithTitle(title_pattern)
        if wins:
            w = wins[0]
            if w.isMinimized:
                w.restore()
                time.sleep(0.3)
            return (w.left, w.top, w.width, w.height)
    except Exception:
        pass
    return None


def get_active_window_region() -> Tuple[int, int, int, int]:
    """获取当前活动窗口的区域。"""
    if HAS_WIN32:
        hwnd = win32gui.GetForegroundWindow()
        rect = win32gui.GetWindowRect(hwnd)
        return (rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])
    size = pyautogui.size()
    return (0, 0, size.width, size.height)


def capture_screenshot(region: Tuple[int, int, int, int],
                       crop_bottom_ratio: float = 1.0) -> Image.Image:
    """截取指定区域的屏幕截图。"""
    left, top, width, height = region
    if 0 < crop_bottom_ratio < 1:
        ct = top + int(height * (1 - crop_bottom_ratio))
        ch = int(height * crop_bottom_ratio)
        return pyautogui.screenshot(region=(left, ct, width, ch))
    return pyautogui.screenshot(region=(left, top, width, height))


def ocr_image(image: Image.Image, tesseract_cmd: Optional[str] = None) -> str:
    """对图像执行 OCR，返回识别文本。"""
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    gray = image.convert("L")
    enhanced = gray.point(lambda x: min(255, max(0, int((x - 30) * 1.5))))
    try:
        return pytesseract.image_to_string(enhanced, lang="eng+chi_sim",
                                           config="--psm 3")
    except pytesseract.TesseractError:
        return pytesseract.image_to_string(enhanced, lang="eng", config="--psm 3")


def press_enter_key() -> bool:
    """模拟按下 Enter 键。"""
    try:
        kb = KBController()
        kb.press(Key.enter)
        kb.release(Key.enter)
        return True
    except Exception:
        return False


def find_tesseract() -> Optional[str]:
    """自动查找 tesseract 可执行文件路径。"""
    search_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/opt/homebrew/bin/tesseract",
    ]
    for p in search_paths:
        if os.path.exists(p):
            return p
    return None


# ============================================================================
# 监控工作线程
# ============================================================================

class MonitorWorker(QThread):
    """后台监控线程：定时截图 → OCR → 检测 → 按键。"""

    # ---- 信号 ----
    stats_update = Signal(dict)          # 统计数据
    ocr_update = Signal(str)             # OCR 识别文本 (多行)
    event_log = Signal(str, str, str)    # (timestamp, type, message)
    status_change = Signal(str)          # "running" / "paused" / "stopped"
    timeline_tick = Signal(int)          # 0=none, 1=detected, 2=pressed
    error_msg = Signal(str)              # 错误消息

    def __init__(self, parent=None):
        super().__init__(parent)

        # ---- 配置 ----
        self.window_title: str = ""
        self.interval: float = 5.0
        self.cooldown: float = 5.0
        self.dry_run: bool = False
        self.blind_mode: bool = False
        self.tesseract_cmd: Optional[str] = None
        self.crop_bottom_ratio: float = 1.0
        self.pause_hotkey: str = "f8"

        # ---- 状态 ----
        self._paused: bool = False
        self._stop_requested: bool = False

        # ---- 统计 ----
        self.check_count: int = 0
        self.detect_count: int = 0
        self.enter_count: int = 0
        self.start_time: float = 0.0
        self.last_check_time: float = 0.0
        self.last_enter_time: float = 0.0
        self.last_detect_time: float = 0.0
        self.last_error: str = ""

        # ---- 用户键盘活动追踪 ----
        self.last_user_key_time: float = 0.0

        # ---- 窗口区域缓存 ----
        self._cached_region: Optional[Tuple[int, int, int, int]] = None

        # ---- 热键监听线程 ----
        self._hotkey_thread: Optional[Thread] = None
        self._hotkey_flag: bool = False
        self._hotkey_shutdown: bool = False

    # ------------------------------------------------------------------
    def run(self) -> None:
        """主监控循环（在后台线程中运行）。"""
        self._stop_requested = False
        self._paused = False
        self.start_time = time.time()

        # 查找窗口
        if not self.blind_mode and self.window_title:
            region = find_window(self.window_title)
            if region:
                self._cached_region = region
                self.event_log.emit(
                    datetime.now().strftime("%H:%M:%S"), "info",
                    f"窗口已找到: {self.window_title} ({region[2]}x{region[3]})"
                )
            else:
                self.event_log.emit(
                    datetime.now().strftime("%H:%M:%S"), "error",
                    f"未找到窗口: {self.window_title}，使用活动窗口"
                )
                self._cached_region = None
        else:
            self._cached_region = None

        # 启动热键监听
        self._start_hotkey_listener()

        # 主循环
        next_check = time.time()  # 首次立即检测
        self.status_change.emit("running")

        while not self._stop_requested:
            now = time.time()

            # 处理热键
            if self._hotkey_flag:
                self._hotkey_flag = False
                self._paused = not self._paused
                self.status_change.emit("paused" if self._paused else "running")

            # 输出统计
            self._emit_stats(now)

            # 检测
            if not self._paused and now >= next_check:
                self._do_check(now)
                next_check = time.time() + self.interval

            time.sleep(1)

        # 清理
        self._hotkey_shutdown = True
        self.status_change.emit("stopped")

    # ------------------------------------------------------------------
    def _start_hotkey_listener(self) -> None:
        """启动热键监听线程（pynput）。"""
        hotkey = self.pause_hotkey

        def _on_press(key):
            if self._hotkey_shutdown or self._stop_requested:
                return False  # 停止监听
            try:
                self.last_user_key_time = time.time()
                key_name = getattr(key, 'name', None) or str(key)
                if key_name.lower() == hotkey.lower():
                    self._hotkey_flag = True
            except Exception:
                pass

        def _listen():
            try:
                listener = Listener(on_press=_on_press)
                listener.daemon = True
                listener.start()
                while not self._hotkey_shutdown:
                    time.sleep(0.5)
                listener.stop()
            except Exception:
                pass

        self._hotkey_thread = Thread(target=_listen, daemon=True)
        self._hotkey_thread.start()

    # ------------------------------------------------------------------
    def _emit_stats(self, now: float) -> None:
        """发送统计信号。"""
        uptime = now - self.start_time if self.start_time > 0 else 0
        cooldown_active = (now - self.last_enter_time < self.cooldown) and \
                          self.last_enter_time > 0
        next_check_remaining = 0.0  # 由 UI 层计算

        self.stats_update.emit({
            "check_count": self.check_count,
            "detect_count": self.detect_count,
            "enter_count": self.enter_count,
            "uptime": uptime,
            "last_check_time": self.last_check_time,
            "last_detect_time": self.last_detect_time,
            "last_enter_time": self.last_enter_time,
            "cooldown_active": cooldown_active,
            "paused": self._paused,
            "blind_mode": self.blind_mode,
            "dry_run": self.dry_run,
        })

    # ------------------------------------------------------------------
    def _do_check(self, now: float) -> None:
        """执行一轮检测。"""
        self.last_check_time = now
        user_active = (now - self.last_user_key_time < self.cooldown)

        # ---- 盲模式 ----
        if self.blind_mode:
            if now - self.last_enter_time < self.cooldown:
                self.event_log.emit(
                    datetime.now().strftime("%H:%M:%S"), "cool",
                    "盲模式，冷却中"
                )
                self.timeline_tick.emit(0)
                return
            if user_active:
                self.event_log.emit(
                    datetime.now().strftime("%H:%M:%S"), "cool",
                    "盲模式，用户打字中，跳过"
                )
                self.timeline_tick.emit(1)
                return
            if self.dry_run:
                self.enter_count += 1
                self.last_enter_time = now
                self.event_log.emit(
                    datetime.now().strftime("%H:%M:%S"), "dry",
                    "盲模式，模拟 Enter"
                )
                self.timeline_tick.emit(2)
            else:
                if press_enter_key():
                    self.enter_count += 1
                    self.last_enter_time = now
                    self.event_log.emit(
                        datetime.now().strftime("%H:%M:%S"), "ok",
                        "盲模式，Enter 已按下"
                    )
                    self.timeline_tick.emit(2)
                else:
                    self.last_error = "按键失败"
                    self.event_log.emit(
                        datetime.now().strftime("%H:%M:%S"), "error",
                        "盲模式，按键失败！"
                    )
                    self.timeline_tick.emit(0)
            self.check_count += 1
            return

        # ---- OCR 模式 ----
        region = self._cached_region
        if region is None:
            try:
                region = get_active_window_region()
            except Exception:
                region = (0, 0, 1920, 1080)

        # 截图
        try:
            img = capture_screenshot(region, self.crop_bottom_ratio)
        except Exception as e:
            self.last_error = f"截图失败: {e}"
            self.error_msg.emit(self.last_error)
            self.timeline_tick.emit(0)
            return

        # OCR
        try:
            text = ocr_image(img, self.tesseract_cmd)
        except pytesseract.TesseractNotFoundError:
            self.last_error = "Tesseract 未安装! 请安装后重试或使用盲模式"
            self.error_msg.emit(self.last_error)
            self.timeline_tick.emit(0)
            return
        except Exception as e:
            self.last_error = f"OCR 失败: {e}"
            self.error_msg.emit(self.last_error)
            self.timeline_tick.emit(0)
            return

        # 更新 OCR 预览
        ocr_lines = [l.strip() for l in text.splitlines() if l.strip()]
        self.ocr_update.emit("\n".join(ocr_lines[-20:]))
        self.last_error = ""
        self.check_count += 1

        # 检测提示词
        detected, matched = detect_prompt(text)
        if not detected:
            self.timeline_tick.emit(0)
            return

        self.detect_count += 1
        self.last_detect_time = now

        # 冷却检查
        if now - self.last_enter_time < self.cooldown:
            self.event_log.emit(
                datetime.now().strftime("%H:%M:%S"), "cool",
                f"检测到: {matched} (冷却中)"
            )
            self.timeline_tick.emit(1)
            return

        # 用户键盘活动
        if user_active:
            self.event_log.emit(
                datetime.now().strftime("%H:%M:%S"), "cool",
                f"检测到: {matched} (用户打字中，跳过)"
            )
            self.timeline_tick.emit(1)
            return

        # 按键
        if self.dry_run:
            self.enter_count += 1
            self.last_enter_time = now
            self.event_log.emit(
                datetime.now().strftime("%H:%M:%S"), "dry",
                f"检测到: {matched} (模拟)"
            )
            self.timeline_tick.emit(2)
        else:
            if press_enter_key():
                self.enter_count += 1
                self.last_enter_time = now
                self.event_log.emit(
                    datetime.now().strftime("%H:%M:%S"), "ok",
                    f"检测到: {matched} → Enter 已按下"
                )
                self.timeline_tick.emit(2)
            else:
                self.last_error = "按键失败"
                self.event_log.emit(
                    datetime.now().strftime("%H:%M:%S"), "error",
                    f"检测到: {matched} → 按键失败！"
                )
                self.timeline_tick.emit(1)

    # ------------------------------------------------------------------
    # 控制方法（从主线程调用）
    # ------------------------------------------------------------------
    def pause(self) -> None:
        self._paused = True
        self.status_change.emit("paused")

    def resume(self) -> None:
        self._paused = False
        self.status_change.emit("running")

    def toggle_pause(self) -> None:
        if self._paused:
            self.resume()
        else:
            self.pause()

    def stop(self) -> None:
        self._stop_requested = True
        self._hotkey_shutdown = True


# ============================================================================
# 自定义控件：活动时间线
# ============================================================================

class TimelineWidget(QFrame):
    """绘制最近 N 次检测活动的条形图。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(50)
        self.setMaximumHeight(70)
        self._data: Deque[int] = deque(maxlen=60)
        self.setStyleSheet("background-color: #0d1117; border: 1px solid #30363d; border-radius: 4px;")
        self.setToolTip("活动时间线: - 无  |  检测到   # 已按下  > 当前位置")

    def add_tick(self, value: int) -> None:
        """添加一个检测结果：0=无, 1=检测到, 2=已按下。"""
        self._data.append(value)
        self.update()

    def clear(self) -> None:
        self._data.clear()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin_x = 8
        margin_y = 12
        bar_w = max(4, (w - margin_x * 2) // max(1, len(self._data) or 1) - 2)
        bar_max_h = h - margin_y * 2

        # 背景
        painter.fillRect(self.rect(), COLOR_BG_DARK)

        data = list(self._data)
        if not data:
            painter.setPen(QColor(0x66, 0x66, 0x66))
            painter.setFont(QFont("Microsoft YaHei UI", 10))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "等待数据...")
            painter.end()
            return

        n = len(data)
        for i, val in enumerate(data):
            x = margin_x + i * (w - margin_x * 2) // max(1, n)
            if val == 0:
                color = QColor(0x30, 0x30, 0x3d)  # 暗灰
                bh = 6
            elif val == 1:
                color = QColor(0xf1, 0xc4, 0x0f)  # 黄色
                bh = bar_max_h // 2
            else:  # val == 2
                color = QColor(0x2e, 0xcc, 0x71)  # 绿色
                bh = bar_max_h

            painter.fillRect(
                int(x), int(margin_y + bar_max_h - bh),
                max(2, int(bar_w)), int(bh),
                color
            )

        # 当前位置指示器
        painter.setPen(QPen(QColor(0x4f, 0xc3, 0xf7), 2))
        cx = margin_x + n * (w - margin_x * 2) // max(1, n)
        painter.drawLine(int(cx), margin_y, int(cx), margin_y + bar_max_h)

        painter.end()


# ============================================================================
# 设置对话框
# ============================================================================

class SettingsDialog(QDialog):
    """配置对话框：修改所有监控参数。"""

    def __init__(self, parent=None,
                 window_title: str = "",
                 interval: float = 5.0,
                 cooldown: float = 5.0,
                 blind_mode: bool = False,
                 dry_run: bool = False,
                 tesseract_cmd: str = "",
                 pause_hotkey: str = "f8",
                 crop_bottom_ratio: float = 1.0):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(420)
        self.setStyleSheet(DARK_STYLE)

        layout = QFormLayout(self)
        layout.setSpacing(12)

        # 窗口标题
        self.window_title_edit = QLineEdit(window_title)
        self.window_title_edit.setPlaceholderText("留空则监控当前活动窗口")
        layout.addRow("窗口标题:", self.window_title_edit)

        # 检测间隔
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(1.0, 300.0)
        self.interval_spin.setValue(interval)
        self.interval_spin.setSuffix(" 秒")
        self.interval_spin.setDecimals(0)
        layout.addRow("检测间隔:", self.interval_spin)

        # 冷却时间
        self.cooldown_spin = QDoubleSpinBox()
        self.cooldown_spin.setRange(1.0, 300.0)
        self.cooldown_spin.setValue(cooldown)
        self.cooldown_spin.setSuffix(" 秒")
        self.cooldown_spin.setDecimals(0)
        layout.addRow("冷却时间:", self.cooldown_spin)

        # 盲模式
        self.blind_mode_check = QCheckBox("不使用 OCR，定时按 Enter")
        self.blind_mode_check.setChecked(blind_mode)
        layout.addRow("盲模式:", self.blind_mode_check)

        # Dry-run
        self.dry_run_check = QCheckBox("仅检测不按键（模拟运行）")
        self.dry_run_check.setChecked(dry_run)
        layout.addRow("模拟运行:", self.dry_run_check)

        # Tesseract 路径
        self.tesseract_edit = QLineEdit(tesseract_cmd)
        self.tesseract_edit.setPlaceholderText("自动检测或手动指定路径")
        layout.addRow("Tesseract 路径:", self.tesseract_edit)

        # 暂停热键
        self.hotkey_edit = QLineEdit(pause_hotkey)
        layout.addRow("暂停热键:", self.hotkey_edit)

        # 截图裁剪比例
        self.crop_spin = QDoubleSpinBox()
        self.crop_spin.setRange(0.1, 1.0)
        self.crop_spin.setValue(crop_bottom_ratio)
        self.crop_spin.setSingleStep(0.1)
        self.crop_spin.setDecimals(1)
        self.crop_spin.setToolTip("只截取窗口底部比例（1.0=整个窗口）")
        layout.addRow("截取底部比例:", self.crop_spin)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_values(self) -> dict:
        return {
            "window_title": self.window_title_edit.text(),
            "interval": self.interval_spin.value(),
            "cooldown": self.cooldown_spin.value(),
            "blind_mode": self.blind_mode_check.isChecked(),
            "dry_run": self.dry_run_check.isChecked(),
            "tesseract_cmd": self.tesseract_edit.text(),
            "pause_hotkey": self.hotkey_edit.text(),
            "crop_bottom_ratio": self.crop_spin.value(),
        }


# ============================================================================
# 主窗口
# ============================================================================

class MainWindow(QMainWindow):
    """TheFinalPuzzle GUI 主窗口。"""

    # 定时器间隔 (ms)
    UI_REFRESH_MS = 500

    def __init__(self):
        super().__init__()

        # ---- 窗口属性 ----
        self.setWindowTitle("TheFinalPuzzle — Claude Auto-Responder")
        self.setMinimumSize(1000, 700)
        self.resize(1100, 750)

        # ---- 状态 ----
        self._worker: Optional[MonitorWorker] = None
        self._running: bool = False
        self._paused: bool = False
        self._events_list: List[Tuple[str, str, str]] = []  # (ts, type, msg)

        # ---- 当前设置 ----
        self._settings = {
            "window_title": "",
            "interval": 5.0,
            "cooldown": 5.0,
            "blind_mode": False,
            "dry_run": False,
            "tesseract_cmd": find_tesseract() or "",
            "pause_hotkey": "f8",
            "crop_bottom_ratio": 1.0,
        }

        # ---- 初始化 Tesseract ----
        if not self._settings["tesseract_cmd"]:
            found = find_tesseract()
            if found:
                self._settings["tesseract_cmd"] = found
                pytesseract.pytesseract.tesseract_cmd = found

        # ---- 构建 UI ----
        self._build_ui()
        self._apply_style()

        # ---- UI 刷新定时器 ----
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_ui)
        self._refresh_timer.start(self.UI_REFRESH_MS)

        # ---- 系统托盘 ----
        self._setup_tray()

        # ---- 上一次统计快照 ----
        self._last_stats: dict = {}

    # ==================================================================
    # UI 构建
    # ==================================================================

    def _build_ui(self) -> None:
        """构建完整的 UI 布局。"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 8)
        main_layout.setSpacing(8)

        # -- 标题栏 --
        main_layout.addLayout(self._build_header())

        # -- 控制栏 --
        main_layout.addLayout(self._build_control_bar())

        # -- 统计面板 + 时间线 --
        top_split = QSplitter(Qt.Orientation.Horizontal)
        top_split.addWidget(self._build_stats_panel())
        top_split.addWidget(self._build_timeline_panel())
        top_split.setSizes([350, 650])
        main_layout.addWidget(top_split)

        # -- OCR 预览 + 事件日志 --
        bottom_split = QSplitter(Qt.Orientation.Horizontal)
        bottom_split.addWidget(self._build_ocr_panel())
        bottom_split.addWidget(self._build_event_panel())
        bottom_split.setSizes([500, 500])
        main_layout.addWidget(bottom_split, stretch=1)

        # -- 状态栏 --
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("就绪 — 点击 ▶ 开始监控")
        self._status_bar.addWidget(self._status_label)

    # ------------------------------------------------------------------
    def _build_header(self) -> QHBoxLayout:
        """标题区域。"""
        layout = QHBoxLayout()

        # 状态指示灯
        self._status_led = QLabel("●")
        self._status_led.setStyleSheet(
            "color: #666; font-size: 16px; background: transparent;"
        )
        self._status_led.setFixedWidth(24)
        layout.addWidget(self._status_led)

        # 标题
        title = QLabel("TheFinalPuzzle — Claude Auto-Responder")
        title.setObjectName("headerTitle")
        layout.addWidget(title)

        layout.addStretch()

        # 模式标签
        self._mode_label = QLabel("停止")
        self._mode_label.setStyleSheet(
            "background-color: #333; color: #999; padding: 4px 12px; "
            "border-radius: 10px; font-weight: bold; font-size: 12px;"
        )
        layout.addWidget(self._mode_label)

        # DRY-RUN 标签
        self._dry_label = QLabel("")
        self._dry_label.setStyleSheet(
            "background-color: #5a4a00; color: #f1c40f; padding: 4px 12px; "
            "border-radius: 10px; font-weight: bold; font-size: 12px;"
        )
        self._dry_label.hide()
        layout.addWidget(self._dry_label)

        # BLIND 标签
        self._blind_label = QLabel("")
        self._blind_label.setStyleSheet(
            "background-color: #4a005a; color: #c471f1; padding: 4px 12px; "
            "border-radius: 10px; font-weight: bold; font-size: 12px;"
        )
        self._blind_label.hide()
        layout.addWidget(self._blind_label)

        return layout

    # ------------------------------------------------------------------
    def _build_control_bar(self) -> QHBoxLayout:
        """控制按钮栏。"""
        layout = QHBoxLayout()

        self._start_btn = QPushButton("▶  开始")
        self._start_btn.setObjectName("startBtn")
        self._start_btn.clicked.connect(self._on_start)
        layout.addWidget(self._start_btn)

        self._pause_btn = QPushButton("⏸  暂停")
        self._pause_btn.setObjectName("pauseBtn")
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self._on_pause)
        layout.addWidget(self._pause_btn)

        layout.addStretch()

        self._settings_btn = QPushButton("⚙  设置")
        self._settings_btn.clicked.connect(self._on_settings)
        layout.addWidget(self._settings_btn)

        return layout

    # ------------------------------------------------------------------
    def _build_stats_panel(self) -> QGroupBox:
        """统计面板。"""
        group = QGroupBox("统计面板")
        grid = QGridLayout(group)
        grid.setSpacing(8)

        # 第一行：Checks, Detected, Entered, Uptime
        stats_labels = [
            ("检测次数", "check_count", "0"),
            ("检测到", "detect_count", "0"),
            ("已按下", "enter_count", "0"),
            ("运行时长", "uptime", "00:00:00"),
        ]

        self._stat_value_labels: dict = {}
        for col, (label, key, default) in enumerate(stats_labels):
            lbl_title = QLabel(label)
            lbl_title.setObjectName("statLabel")
            lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lbl_title, 0, col)

            lbl_value = QLabel(default)
            lbl_value.setObjectName("statValue")
            lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lbl_value, 1, col)
            self._stat_value_labels[key] = lbl_value

        # 第二行：Last Check, Last Detect, Last Enter, Cooldown
        last_labels = [
            ("上次检测", "last_check"),
            ("上次检测到", "last_detect"),
            ("上次按键", "last_enter"),
            ("冷却状态", "cooldown"),
        ]

        self._last_value_labels: dict = {}
        for col, (label, key) in enumerate(last_labels):
            lbl_title = QLabel(label)
            lbl_title.setObjectName("statLabel")
            lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lbl_title, 2, col)

            lbl_value = QLabel("--")
            lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_value.setStyleSheet("color: #999; font-size: 13px; background: transparent;")
            grid.addWidget(lbl_value, 3, col)
            self._last_value_labels[key] = lbl_value

        return group

    # ------------------------------------------------------------------
    def _build_timeline_panel(self) -> QGroupBox:
        """时间线面板。"""
        group = QGroupBox("活动时间线")
        layout = QVBoxLayout(group)

        self._timeline = TimelineWidget()
        layout.addWidget(self._timeline)

        # 图例
        legend = QHBoxLayout()
        for text, color in [
            ("- 无检测", "#30303d"),
            ("| 检测到", "#f1c40f"),
            ("# 已按下", "#2ecc71"),
            ("> 当前位置", "#4fc3f7"),
        ]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 10px; background: transparent;")
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #888; font-size: 11px; background: transparent;")
            legend.addWidget(dot)
            legend.addWidget(lbl)
            legend.addSpacing(12)
        legend.addStretch()
        layout.addLayout(legend)

        return group

    # ------------------------------------------------------------------
    def _build_ocr_panel(self) -> QGroupBox:
        """OCR 预览面板。"""
        group = QGroupBox("OCR 预览（窗口底部文本）")
        layout = QVBoxLayout(group)

        self._ocr_text = QTextEdit()
        self._ocr_text.setReadOnly(True)
        self._ocr_text.setPlaceholderText("等待 OCR 结果...")
        layout.addWidget(self._ocr_text)

        return group

    # ------------------------------------------------------------------
    def _build_event_panel(self) -> QGroupBox:
        """事件日志面板。"""
        group = QGroupBox("事件日志")
        layout = QVBoxLayout(group)

        self._event_table = QTableWidget(0, 3)
        self._event_table.setHorizontalHeaderLabels(["时间", "类型", "详情"])
        self._event_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self._event_table.setColumnWidth(0, 70)   # 时间
        self._event_table.setColumnWidth(1, 50)   # 类型
        self._event_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._event_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._event_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._event_table.verticalHeader().setVisible(False)
        self._event_table.setAlternatingRowColors(True)
        self._event_table.setShowGrid(True)

        # 垂直滚动始终显示最新
        self._event_table.setWordWrap(True)

        layout.addWidget(self._event_table)

        return group

    # ------------------------------------------------------------------
    def _setup_tray(self) -> None:
        """设置系统托盘图标。"""
        self._tray_icon = QSystemTrayIcon(self)
        # 使用内置图标作为占位
        self._tray_icon.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        )
        self._tray_icon.setToolTip("TheFinalPuzzle — Claude Auto-Responder")

        tray_menu = QMenu()
        show_action = tray_menu.addAction("显示窗口")
        show_action.triggered.connect(self._show_from_tray)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("退出")
        quit_action.triggered.connect(self._quit_app)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    # ==================================================================
    # 样式
    # ==================================================================

    def _apply_style(self) -> None:
        """应用暗色主题样式。"""
        self.setStyleSheet(DARK_STYLE)

    # ==================================================================
    # 事件处理
    # ==================================================================

    def closeEvent(self, event) -> None:
        """关闭窗口 → 直接退出。"""
        self._quit_app()

    def _quit_app(self) -> None:
        """安全退出应用。"""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        self._tray_icon.hide()
        QApplication.quit()

    # ------------------------------------------------------------------
    def _on_tray_activated(self, reason) -> None:
        """托盘图标双击 → 显示窗口。"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self) -> None:
        """从托盘恢复窗口。"""
        self.showNormal()
        self.activateWindow()
        self.raise_()

    # ------------------------------------------------------------------
    def _on_start(self) -> None:
        """点击开始按钮。"""
        if self._worker and self._worker.isRunning():
            return  # 已在运行

        # 检查 Tesseract
        if not self._settings["blind_mode"] and not HAS_TESSERACT:
            QMessageBox.warning(
                self, "Tesseract 未安装",
                "pytesseract 未安装，OCR 模式不可用。\n\n"
                "请安装: pip install pytesseract\n"
                "并安装 Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki\n\n"
                "或切换到盲模式（设置 → 盲模式）。"
            )
            return

        # 配置 Tesseract 路径
        if self._settings["tesseract_cmd"]:
            pytesseract.pytesseract.tesseract_cmd = self._settings["tesseract_cmd"]

        # 创建并启动工作线程
        self._worker = MonitorWorker()
        self._worker.window_title = self._settings["window_title"]
        self._worker.interval = self._settings["interval"]
        self._worker.cooldown = self._settings["cooldown"]
        self._worker.dry_run = self._settings["dry_run"]
        self._worker.blind_mode = self._settings["blind_mode"]
        self._worker.tesseract_cmd = self._settings["tesseract_cmd"] or None
        self._worker.crop_bottom_ratio = self._settings["crop_bottom_ratio"]
        self._worker.pause_hotkey = self._settings["pause_hotkey"]

        # 连接信号
        self._worker.stats_update.connect(self._on_stats_update)
        self._worker.ocr_update.connect(self._on_ocr_update)
        self._worker.event_log.connect(self._on_event_log)
        self._worker.status_change.connect(self._on_status_change)
        self._worker.timeline_tick.connect(self._timeline.add_tick)
        self._worker.error_msg.connect(self._on_error)

        self._worker.start()

        # 更新 UI 状态
        self._running = True
        self._paused = False
        self._update_button_states()

        self._status_label.setText("运行中...")
        self._status_led.setStyleSheet(
            "color: #2ecc71; font-size: 16px; background: transparent;"
        )
        self._mode_label.setText("OCR" if not self._settings["blind_mode"] else "BLIND")
        self._mode_label.setStyleSheet(
            "background-color: #1a3a2a; color: #2ecc71; padding: 4px 12px; "
            "border-radius: 10px; font-weight: bold; font-size: 12px;"
        )
        self._dry_label.setVisible(self._settings["dry_run"])
        self._blind_label.setVisible(self._settings["blind_mode"])
        if self._settings["dry_run"]:
            self._dry_label.setText("DRY-RUN")
        if self._settings["blind_mode"]:
            self._blind_label.setText("BLIND")

    # ------------------------------------------------------------------
    def _on_pause(self) -> None:
        """暂停 / 恢复。"""
        if not self._worker or not self._worker.isRunning():
            return

        if self._paused:
            self._worker.resume()
            self._pause_btn.setText("⏸  暂停")
            self._status_label.setText("运行中...")
            self._status_led.setStyleSheet(
                "color: #2ecc71; font-size: 16px; background: transparent;"
            )
            self._mode_label.setText(
                "OCR" if not self._settings["blind_mode"] else "BLIND"
            )
            self._mode_label.setStyleSheet(
                "background-color: #1a3a2a; color: #2ecc71; padding: 4px 12px; "
                "border-radius: 10px; font-weight: bold; font-size: 12px;"
            )
        else:
            self._worker.pause()
            self._pause_btn.setText("▶  继续")
            self._status_label.setText("已暂停")
            self._status_led.setStyleSheet(
                "color: #f1c40f; font-size: 16px; background: transparent;"
            )
            self._mode_label.setText("暂停")
            self._mode_label.setStyleSheet(
                "background-color: #3a2a00; color: #f1c40f; padding: 4px 12px; "
                "border-radius: 10px; font-weight: bold; font-size: 12px;"
            )

    # ------------------------------------------------------------------
    def _on_stop(self) -> None:
        """停止监控。"""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
            self._worker = None

        self._running = False
        self._paused = False
        self._update_button_states()

        self._status_label.setText("已停止")
        self._status_led.setStyleSheet(
            "color: #666; font-size: 16px; background: transparent;"
        )
        self._mode_label.setText("停止")
        self._mode_label.setStyleSheet(
            "background-color: #333; color: #999; padding: 4px 12px; "
            "border-radius: 10px; font-weight: bold; font-size: 12px;"
        )
        self._dry_label.hide()
        self._blind_label.hide()

    # ------------------------------------------------------------------
    def _on_settings(self) -> None:
        """打开设置对话框。运行时需先暂停，暂停/停止时可直接修改。"""
        # 运行中且未暂停 → 提示先暂停
        if self._running and not self._paused:
            reply = QMessageBox.question(
                self, "正在运行",
                "修改设置需要先暂停监控。\n\n是否暂停并打开设置？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._on_pause()  # 先暂停

        dlg = SettingsDialog(
            self,
            window_title=self._settings["window_title"],
            interval=self._settings["interval"],
            cooldown=self._settings["cooldown"],
            blind_mode=self._settings["blind_mode"],
            dry_run=self._settings["dry_run"],
            tesseract_cmd=self._settings["tesseract_cmd"],
            pause_hotkey=self._settings["pause_hotkey"],
            crop_bottom_ratio=self._settings["crop_bottom_ratio"],
        )

        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._settings = dlg.get_values()

            # 应用 Tesseract 路径
            if self._settings["tesseract_cmd"]:
                pytesseract.pytesseract.tesseract_cmd = self._settings["tesseract_cmd"]

            # 如果正在运行（暂停状态），同步设置到 worker
            if self._running and self._worker:
                self._worker.interval = self._settings["interval"]
                self._worker.cooldown = self._settings["cooldown"]
                self._worker.dry_run = self._settings["dry_run"]
                self._worker.blind_mode = self._settings["blind_mode"]
                self._worker.tesseract_cmd = self._settings["tesseract_cmd"] or None
                self._worker.crop_bottom_ratio = self._settings["crop_bottom_ratio"]
                self._worker.pause_hotkey = self._settings["pause_hotkey"]

            self._status_label.setText(
                f"设置已更新 — 间隔 {self._settings['interval']:.0f}s, "
                f"冷却 {self._settings['cooldown']:.0f}s "
                f"({'盲模式' if self._settings['blind_mode'] else 'OCR'})"
            )

    # ------------------------------------------------------------------
    def _update_button_states(self) -> None:
        """根据运行状态更新按钮启用/禁用。"""
        self._start_btn.setEnabled(not self._running)
        self._pause_btn.setEnabled(self._running)
        if self._running:
            self._pause_btn.setText("⏸  暂停" if not self._paused else "▶  继续")

    # ==================================================================
    # 信号处理
    # ==================================================================

    @Slot(dict)
    def _on_stats_update(self, stats: dict) -> None:
        """更新统计面板（在工作线程中调用，通过信号队列在主线程执行）。"""
        self._last_stats = stats

    @Slot(str)
    def _on_ocr_update(self, text: str) -> None:
        """更新 OCR 预览。"""
        self._ocr_text.setPlainText(text)

    @Slot(str, str, str)
    def _on_event_log(self, timestamp: str, etype: str, message: str) -> None:
        """添加事件日志条目。"""
        self._events_list.append((timestamp, etype, message))
        # 限制数量
        if len(self._events_list) > 500:
            self._events_list = self._events_list[-500:]

        self._event_table.insertRow(0)  # 插入到顶部（最新）

        # 时间
        time_item = QTableWidgetItem(timestamp)
        time_item.setForeground(QColor(0x8b, 0x94, 0x9e))
        self._event_table.setItem(0, 0, time_item)

        # 类型
        type_icons = {
            "ok": ("OK", QColor(0x2e, 0xcc, 0x71)),
            "dry": ("DRY", QColor(0xf1, 0xc4, 0x0f)),
            "cool": ("..", QColor(0x8b, 0x94, 0x9e)),
            "error": ("ERR", QColor(0xe7, 0x4c, 0x3c)),
            "info": ("INFO", QColor(0x4f, 0xc3, 0xf7)),
        }
        icon_text, icon_color = type_icons.get(etype, (etype, QColor(0x8b, 0x94, 0x9e)))
        type_item = QTableWidgetItem(icon_text)
        type_item.setForeground(icon_color)
        type_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self._event_table.setItem(0, 1, type_item)

        # 详情
        msg_item = QTableWidgetItem(message)
        self._event_table.setItem(0, 2, msg_item)

        # 限制行数
        while self._event_table.rowCount() > 200:
            self._event_table.removeRow(self._event_table.rowCount() - 1)

    @Slot(str)
    def _on_status_change(self, status: str) -> None:
        """响应工作线程的状态变化。"""
        if status == "running":
            self._paused = False
            self._status_label.setText("运行中...")
            self._status_led.setStyleSheet(
                "color: #2ecc71; font-size: 16px; background: transparent;"
            )
        elif status == "paused":
            self._paused = True
            self._status_label.setText("已暂停 (F8)")
            self._status_led.setStyleSheet(
                "color: #f1c40f; font-size: 16px; background: transparent;"
            )
        elif status == "stopped":
            self._running = False
            self._paused = False
        self._update_button_states()

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        """显示错误消息。"""
        self._status_label.setText(f"错误: {msg}")
        self._status_led.setStyleSheet(
            "color: #e74c3c; font-size: 16px; background: transparent;"
        )

    # ==================================================================
    # 定时刷新
    # ==================================================================

    def _refresh_ui(self) -> None:
        """定时刷新统计面板（从主线程调用）。"""
        if not self._last_stats:
            return

        stats = self._last_stats
        now = time.time()

        # 更新数值
        self._stat_value_labels["check_count"].setText(str(stats["check_count"]))
        self._stat_value_labels["detect_count"].setText(str(stats["detect_count"]))
        self._stat_value_labels["enter_count"].setText(str(stats["enter_count"]))

        uptime = stats["uptime"]
        self._stat_value_labels["uptime"].setText(
            f"{int(uptime // 3600):02d}:{int(uptime % 3600 // 60):02d}:{int(uptime % 60):02d}"
        )

        # 更新 "上次" 标签
        def _ago(ts: float) -> str:
            if ts == 0:
                return "--"
            ago = int(now - ts) + 1
            if ago < 60:
                return f"{ago}s 前"
            elif ago < 3600:
                return f"{ago // 60}m 前"
            else:
                return f"{ago // 3600}h 前"

        self._last_value_labels["last_check"].setText(_ago(stats["last_check_time"]))
        self._last_value_labels["last_detect"].setText(_ago(stats["last_detect_time"]))
        self._last_value_labels["last_enter"].setText(_ago(stats["last_enter_time"]))
        self._last_value_labels["cooldown"].setText(
            "冷却中" if stats["cooldown_active"] else "就绪"
        )
        if stats["cooldown_active"]:
            self._last_value_labels["cooldown"].setStyleSheet(
                "color: #f1c40f; font-size: 13px; background: transparent;"
            )
        else:
            self._last_value_labels["cooldown"].setStyleSheet(
                "color: #2ecc71; font-size: 13px; background: transparent;"
            )


# ============================================================================
# 入口
# ============================================================================

def main() -> None:
    """主入口函数。"""
    check_deps()

    # Windows 下的编码设置
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("TheFinalPuzzle")
    app.setOrganizationName("TheFinalPuzzle")
    app.setStyle("Fusion")  # 跨平台一致的风格

    # 设置字体
    font = QFont("Microsoft YaHei UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
