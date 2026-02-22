中文 | [English](https://github.com/stellariums/AutoGUI/blob/master/README.md)

# AutoGUI

[![PyPI](https://img.shields.io/pypi/v/autogui-mcp)](https://pypi.org/project/autogui-mcp/) [![Python](https://img.shields.io/pypi/pyversions/autogui-mcp)](https://pypi.org/project/autogui-mcp/) [![License](https://img.shields.io/pypi/l/autogui-mcp)](https://github.com/stellariums/AutoGUI/blob/master/LICENSE)

AI 驱动的屏幕自动化 MCP Server。发送自然语言任务，内部 AI 自主截屏分析并执行鼠标/键盘操作。

## 架构

```
MCP Client (Claude Code, Claude Desktop, Cursor 等)
    |  stdio
    v
server.py (FastMCP 异步编排循环)
    |
    v
agent.py (ScreenAgent 工具集: 截屏、执行、解析、安全检查)
```

## 快速开始

```bash
git clone https://github.com/stellariums/AutoGUI.git
cd AutoGUI
pip install -r requirements.txt
```

## 配置

AutoGUI 支持分层配置：**环境变量**（最高优先级）> **config.json** > **默认值**。

### 方式 A：仅用环境变量（最简单）

只需 3 个变量即可启动：

```bash
set AUTOGUI_API_KEY=your-api-key
set AUTOGUI_BASE_URL=https://api.openai.com/v1
set AUTOGUI_MODEL=gpt-4o
```

也可复制 `.env.example` 为 `.env`，通过 MCP 客户端配置传入（见下方）。

### 方式 B：配置文件

```bash
cp config.json.example config.json
```

编辑 `config.json` — 只需填写 `api` 部分，其余均有默认值：

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
<summary>高级配置选项</summary>

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

## MCP 客户端配置

### Claude Code

```bash
claude mcp add AutoGUI -- python /path/to/AutoGUI/server.py
```

或添加到 `.mcp.json`：

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

添加到 `claude_desktop_config.json`：

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

添加到 Cursor MCP 设置（`.cursor/mcp.json`）：

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

### MCP Inspector（测试）

```bash
npx @modelcontextprotocol/inspector python server.py
```

## 工具

| 工具 | 说明 |
|------|------|
| `autogui_execute_task` | 通过自然语言执行屏幕自动化任务 |

## 支持的操作

| 操作 | 说明 |
|------|------|
| click | 点击指定位置 |
| double_click | 双击 |
| right_click | 右键点击 |
| type | 输入文本（通过剪贴板支持中文） |
| press | 按键组合 |
| scroll | 滚动 |
| drag | 拖拽 |
| move | 移动鼠标 |
| wait | 等待 |
| task_complete | 标记任务完成 |

## 安全机制

- 危险操作检测（规则匹配 + AI 自标记双重判断）
- 可配置的危险按键、热键和文本模式
- 可选操作区域限制（`allowed_region`）
- 基于 elicit 的危险操作确认
- 可配置回退策略：`block`（阻止）或 `allow`（允许）

## 常见问题

**Q: 截图是黑屏或空白**
A: 确保屏幕未锁定。Windows 锁屏状态下 pyautogui/mss 无法截屏。

**Q: 中文输入不生效**
A: AutoGUI 使用剪贴板（`pyperclip` + `Ctrl+V`）输入文本，天然支持中文。确保已安装 `pyperclip`。

**Q: 提示 "API key required"**
A: 设置 `AUTOGUI_API_KEY` 环境变量，或在 `config.json` 中填写 `api.api_key`。

**Q: 提示 "Another task is already running"**
A: AutoGUI 同一时间只处理一个任务，请等待当前任务完成。

## 系统要求

- Windows 10/11
- Python >= 3.10
- OpenAI 兼容的视觉 API（GPT-4o、Qwen-VL 等）

## 致谢

本项目基于 [tech-shrimp/qwen_autogui](https://github.com/tech-shrimp/qwen_autogui) 改造，重构为 MCP Server 并新增安全检查、分层配置和多客户端支持。

## 许可证

MIT
