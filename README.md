[中文](README_CN.md) | English

# AutoGUI

AI-driven screen automation MCP Server. Send natural language tasks, and the internal AI captures screenshots, analyzes them, and performs mouse/keyboard actions autonomously.

## Architecture

```
MCP Client (Claude Code, etc.)
    |  stdio
    v
server.py (FastMCP async orchestration loop)
    |
    v
agent.py (ScreenAgent toolkit: capture, execute, parse, safety)
```

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Copy `config.json.example` to `config.json` and fill in your API key:

```bash
cp config.json.example config.json
```

```json
{
  "api": {
    "base_url": "https://your-api-endpoint/v1",
    "api_key": "your-api-key",
    "model": "your-model-name",
    "max_tokens": 8192,
    "temperature": 0.7
  },
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

## Usage

### As MCP Server (Recommended)

Add to your Claude Code MCP config (`.mcp.json`):

```json
{
  "mcpServers": {
    "AutoGUI": {
      "command": "python",
      "args": ["/path/to/AutoGUI/server.py"]
    }
  }
}
```

Then ask Claude Code to perform screen tasks:

> "Use AutoGUI to open Notepad and type Hello World"

### With MCP Inspector

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

## License

MIT
