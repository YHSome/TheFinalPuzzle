# TheFinalPuzzle

> Claude Auto-Responder — automatically monitors a Claude Code window and presses Enter when option prompts (Yes/No, Continue?, etc.) are detected.

[简体中文](README.md) | **English**

> **⚠️ This is a meme project — for entertainment purposes only!**
>
> Do NOT use this in any real development, production, or important project.
> Auto-pressing Enter means you may blindly agree to file modifications, command executions,
> etc. without understanding the consequences. This could lead to data loss, system damage,
> or other unpredictable outcomes. The author assumes no liability.

## How It Works

```
┌─────────────────────┐
│   Top 70%            │  ← Conversation history, ignored
│   (chat history)     │
├─────────────────────┤
│   Bottom 30%         │  ← Only this part is OCR'd
│   (prompt area)      │     Yes/No options live here
└─────────────────────┘
         ↓
  Screenshot → OCR → Keyword match → Press Enter
         ↓
  Refresh terminal dashboard (live OCR results, stats, event log)
```

Only the **bottom 30%** of the window is captured for OCR, ignoring the conversation history above — faster and fewer false positives.

## Installation

### 1. Python Dependencies

```bash
pip install pyautogui pillow pytesseract pynput rich pywin32
```

### 2. Tesseract OCR (required for OCR mode)

| Platform | Install |
|----------|---------|
| Windows | [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) |
| macOS | `brew install tesseract` |
| Linux | `sudo apt install tesseract-ocr tesseract-ocr-chi-sim` |

> Blind mode (`--blind`) does not require Tesseract.

## Usage

```bash
# OCR smart detection (default: every 5 seconds)
python claude_auto_responder.py

# Dry run: detect only, no key press
python claude_auto_responder.py --dry-run

# Blind mode: press Enter every 10 seconds (no OCR needed)
python claude_auto_responder.py --blind --interval 10

# Target a specific window by title (case-insensitive)
python claude_auto_responder.py --title "claude"

# Show all options
python claude_auto_responder.py --help
```

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--title` | `-t` | Active window | Window title match (case-insensitive) |
| `--interval` | `-i` | `5` | Check interval in seconds |
| `--cooldown` | `-c` | `5` | Minimum seconds between Enter presses |
| `--blind` | `-b` | Off | Blind mode: periodic Enter, no OCR |
| `--dry-run` | `-n` | Off | Detect only, do not press Enter |
| `--tesseract-cmd` | | Auto-detect | Path to tesseract executable |
| `--save-screenshots` | | Off | Save screenshots to `./screenshots/` for debugging |
| `--pause-hotkey` | | `f8` | Pause/resume hotkey |

## Dashboard

A live monitoring panel is displayed at runtime:

```
┌──────────────────────────────────────────┐
│  TheFinalPuzzle                          │
│  > Running  Mode: OCR  Interval: 5s     │
├──────────────────────────────────────────┤
│  Checks: 12  Detected: 3  Enter: 3      │
│  Last check: 2s ago  Hit rate: 25%      │
├──────────────────────────────────────────┤
│  --|--#--|--#>  Activity timeline (last 60)│
│  -=none  |=detected  #=pressed  >=now   │
├──────────────────┬───────────────────────┤
│  OCR Result      │  Event Log            │
│  │ [y/N]         │  14:32:05 OK pressed  │
│  │ Do you want   │  14:31:55 OK pressed  │
│  │ to proceed?   │  14:31:42 .. skipped  │
│                  │  14:31:39 -- no match │
├──────────────────┴───────────────────────┤
│  F8: pause  |  Ctrl+C: exit  |  LIVE    │
└──────────────────────────────────────────┘
```

## Hotkeys

| Key | Action |
|-----|--------|
| `F8` | Pause / Resume |
| `Ctrl+C` | Exit |

## Detection Logic

Dead simple: if the OCR text contains **both `Yes` and `No`** (or Chinese **`是` + `否`**), trigger Enter.

| Trigger | Covers |
|---------|--------|
| `Yes` + `No` both present | All English prompts: `[y/N]`, `yes/no`, `Do you want to...?`, `1. Yes / 2. No`, etc. |
| `是` + `否` both present | All Chinese prompts: `是/否`, `是否继续`, `确认执行`, etc. |
| `是否...` | e.g. `是否继续` `是否确认` `是否执行` |
| `确认...` | e.g. `确认继续` `确认执行` `确认操作` |

## Anti Keyboard-Grabbing

If the user has typed anything within the cooldown window (last 5 seconds), the script **skips** the Enter press entirely — it won't fight you for keyboard control.

## Notes

- **Terminal**: Windows Terminal / cmd support in-place dashboard refresh; PyCharm's built-in terminal does not support ANSI clear and will display as scrolling log
- **Window targeting**: OCR captures screen pixels — the Claude window must be visible and in the foreground, or targeted via `--title`
- **Capture area**: Defaults to the bottom 30% of the window (prompt area only, skipping conversation history)
- **Permissions**: macOS requires terminal accessibility permission in System Settings
