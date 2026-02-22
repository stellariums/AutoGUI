[中文](https://github.com/stellariums/AutoGUI/blob/master/README_CN.md) | English

# AutoGUI

AI-driven screen automation MCP Server. Send natural language tasks, and the internal AI captures screenshots, analyzes them, and performs mouse/keyboard actions autonomously.

## Architecture

```
MCP Client (Claude Code, Claude Desktop, Cursor, etc.)
    |  stdio
    v
server.py (FastMCP async orchestration loop)
    |
    v
agent.py (ScreenAgent toolkit: capture, execute, parse, safety)
```

## Quick Start

```bash
git clone https://github.com/stellariums/AutoGUI.git
cd AutoGUI
pip install -r requirements.txt
```

## Configuration

AutoGUI supports layered configuration: **environment variables** (highest priority) > **config.json** > **defaults**.

### Option A: Environment Variables Only (Simplest)

Only 3 variables needed to get started:

```bash
set AUTOGUI_API_KEY=your-api-key
set AUTOGUI_BASE_URL=https://api.openai.com/v1
set AUTOGUI_MODEL=gpt-4o
```

Or copy `.env.example` to `.env` and pass via your MCP client config (see below).

### Option B: Config File

```bash
cp config.json.example config.json
```

Edit `config.json` — only the `api` section is required, everything else has sensible defaults:

```json
{
  "api": {
    "base_url": "https://your-api-endpoint/v1",
    "api_key": "your-api-key",
    "model": "your-model-name"
  }
}
```

<details>
<summary>Advanced config options</summary>

```json
{
  "screen": {
    "max_width": 1280,
    "max_height": 720,
    "allowed_region": null
  },
  "agent": {
    "max_iterations": 20,
    "delay_between_actions": 1.0,
    "max_history_rounds": 10
  },
  "safety": {
    "enable_confirmation": true,
    "fallback_action": "block",
    "dangerous_keys": ["delete", "backspace", "escape"],
    "dangerous_hotkeys": [["ctrl", "w"], ["alt", "f4"]],
    "dangerous_patterns": ["rm ", "del ", "format ", "shutdown"]
  }
}
```

</details>

## MCP Client Setup

### Claude Code

```bash
claude mcp add AutoGUI -- python /path/to/AutoGUI/server.py
```

Or add to `.mcp.json`:

```json
{
  "mcpServers": {
    "AutoGUI": {
      "command": "python",
      "args": ["/path/to/AutoGUI/server.py"],
      "env": {
        "AUTOGUI_API_KEY": "your-api-key",
        "AUTOGUI_BASE_URL": "https://api.openai.com/v1",
        "AUTOGUI_MODEL": "gpt-4o"
      }
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "AutoGUI": {
      "command": "python",
      "args": ["C:/path/to/AutoGUI/server.py"],
      "env": {
        "AUTOGUI_API_KEY": "your-api-key",
        "AUTOGUI_BASE_URL": "https://api.openai.com/v1",
        "AUTOGUI_MODEL": "gpt-4o"
      }
    }
  }
}
```

### Cursor

Add to Cursor MCP settings (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "AutoGUI": {
      "command": "python",
      "args": ["/path/to/AutoGUI/server.py"],
      "env": {
        "AUTOGUI_API_KEY": "your-api-key",
        "AUTOGUI_BASE_URL": "https://api.openai.com/v1",
        "AUTOGUI_MODEL": "gpt-4o"
      }
    }
  }
}
```

### MCP Inspector (Testing)

```bash
npx @modelcontextprotocol/inspector python server.py
```

## Tool

| Tool | Description |
|------|-------------|
| `autogui_execute_task` | Execute a screen automation task via natural language |

## Supported Actions

| Action | Description |
|--------|-------------|
| click | Click at position |
| double_click | Double click |
| right_click | Right click |
| type | Input text (supports CJK via clipboard) |
| press | Key combination |
| scroll | Scroll |
| drag | Drag |
| move | Move cursor |
| wait | Wait |
| task_complete | Mark task as done |

## Safety

- Dangerous action detection (rule-based + AI self-labeling)
- Configurable dangerous keys, hotkeys, and text patterns
- Optional region restriction (`allowed_region`)
- Elicit-based confirmation for dangerous operations
- Configurable fallback: `block` or `allow`

## FAQ

**Q: Screenshot is black or empty**
A: Make sure the screen is not locked. On Windows, pyautogui/mss cannot capture the lock screen.

**Q: Chinese input not working**
A: AutoGUI uses clipboard (`pyperclip` + `Ctrl+V`) for text input, which supports CJK characters. Make sure `pyperclip` is installed.

**Q: "API key required" error**
A: Set `AUTOGUI_API_KEY` env var or add `api.api_key` in `config.json`.

**Q: "Another task is already running" error**
A: AutoGUI processes one task at a time. Wait for the current task to finish.

## Requirements

- Windows 10/11
- Python >= 3.10
- An OpenAI-compatible vision API (GPT-4o, Qwen-VL, etc.)

## License

MIT
