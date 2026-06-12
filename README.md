# Claude Auto-Responder

自动监测 Claude Code 窗口，当出现选项提示（Yes/No、Continue? 等）时自动按下 Enter 键。

> **⚠️ 整活项目，仅供娱乐！**
>
> 本项目仅为好玩而写，**请勿在任何正式开发、生产环境或重要项目中使用**。
> 自动按键意味着你可能在不了解具体操作的情况下盲目同意文件修改、命令执行等行为，
> 可能导致数据丢失、系统损坏或其他不可预知的后果。作者不承担任何使用本脚本造成的责任。

## 原理

```
┌─────────────────────┐
│   窗口上部 70%       │  ← 对话内容，不监控
│   (对话历史)         │
├─────────────────────┤
│   窗口下部 30%       │  ← 只截取这部分做 OCR
│   (提示区域)         │     Yes/No 选项都在这里
└─────────────────────┘
         ↓
  截图 → OCR 识别文字 → 正则匹配提示词 → 自动按 Enter
         ↓
  刷新终端仪表盘（实时显示 OCR 结果、统计、事件日志）
```

只截取窗口**底部 30%** 的提示区域做 OCR，不扫描上部大段对话历史，减少误触发、提高识别速度。

## 安装

### 1. Python 依赖

```bash
pip install pyautogui pillow pytesseract pynput rich pywin32
```

### 2. Tesseract OCR（OCR 模式需要）

| 平台 | 安装方式 |
|------|----------|
| Windows | [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) |
| macOS | `brew install tesseract` |
| Linux | `sudo apt install tesseract-ocr tesseract-ocr-chi-sim` |

> 盲模式（`--blind`）不需要 Tesseract，直接定时按键。

## 用法

```bash
# OCR 智能检测（默认每 5 秒检测一次）
python claude_auto_responder.py

# 试运行：只检测不按键
python claude_auto_responder.py --dry-run

# 盲模式：每 10 秒按一次 Enter，不需要 OCR
python claude_auto_responder.py --blind --interval 10

# 指定要监控的窗口标题（不区分大小写）
python claude_auto_responder.py --title "claude"

# 查看所有参数
python claude_auto_responder.py --help
```

## 参数

| 参数 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--title` | `-t` | 活动窗口 | 窗口标题匹配 |
| `--interval` | `-i` | `5` | 检测间隔（秒） |
| `--cooldown` | `-c` | `5` | 两次按键最小间隔（秒） |
| `--blind` | `-b` | 关闭 | 盲模式，不做 OCR，定时按键 |
| `--dry-run` | `-n` | 关闭 | 仅检测不实际按键 |
| `--tesseract-cmd` | | 自动检测 | Tesseract 可执行文件路径 |
| `--save-screenshots` | | 关闭 | 保存截图到 `./screenshots/` 用于调试 |
| `--pause-hotkey` | | `f8` | 暂停/恢复热键 |

## 仪表盘

运行后会显示实时监控面板：

```
┌──────────────────────────────────────────┐
│  Claude Auto-Responder                   │
│  > 运行中  Mode: OCR  Interval: 5s       │
├──────────────────────────────────────────┤
│  Checks: 12  Detected: 3  Enter: 3       │
│  Last check: 2s ago  Hit rate: 25%       │
├──────────────────────────────────────────┤
│  ||#|||#|||   活动时间线（最近60次）       │
│  空格=无  |=检测到  #=已按键              │
├──────────────────┬───────────────────────┤
│  OCR 识别结果     │  事件日志              │
│  │ [y/N]         │  14:32:05 OK 已按键    │
│  │ Do you want   │  14:31:55 OK 已按键    │
│  │ to proceed?   │  14:31:42 .. 冷却中    │
│                  │  14:31:39 -- 无匹配    │
├──────────────────┴───────────────────────┤
│  F8: 暂停  |  Ctrl+C: 退出  |  LIVE 模式  │
└──────────────────────────────────────────┘
```

## 快捷键

| 按键 | 作用 |
|------|------|
| `F8` | 暂停 / 恢复监控 |
| `Ctrl+C` | 退出程序 |

## 检测逻辑

极简规则：OCR 识别文字中**同时出现 `Yes` + `No`**（或中文 **`是` + `否`**）即触发按键。

| 触发条件 | 说明 |
|----------|------|
| `Yes` + `No` 同时出现 | 覆盖所有英文选项：`[y/N]`、`yes/no`、`Do you want to...?`、`1. Yes / 2. No` 等 |
| `是` + `否` 同时出现 | 覆盖所有中文选项：`是/否`、`是否继续`、`确认执行` 等 |
| `是否...` | 如 `是否继续` `是否确认` `是否执行` |
| `确认...` | 如 `确认继续` `确认执行` `确认操作` |

> 无需穷举每种提示句式，只要提示区域里 yes 和 no 成对出现就触发。

## 注意事项

- **终端兼容性**: Windows Terminal / cmd 支持原位刷新仪表盘；PyCharm 内置终端不支持 ANSI 清屏，会以滚动日志显示
- **窗口定位**: OCR 截取屏幕画面，Claude 窗口需可见且在前台，或通过 `--title` 指定窗口
- **监控区域**: 默认截取窗口底部 30%，仅包含提示区域，跳过上方对话历史
- **权限**: macOS 需在"隐私与安全性"中授权终端辅助功能权限
