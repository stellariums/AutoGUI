中文 | [English](README.md)

# AutoGUI

AI 驱动的屏幕自动化 MCP Server。发送自然语言任务，内部 AI 自主截屏分析并执行鼠标/键盘操作。

## 架构

```
MCP Client (Claude Code 等)
    |  stdio
    v
server.py (FastMCP 异步编排循环)
    |
    v
agent.py (ScreenAgent 工具集: 截屏、执行、解析、安全检查)
```

## 安装

```bash
pip install -r requirements.txt
```

## 配置

复制 `config.json.example` 为 `config.json` 并填入 API Key：

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

## 使用

### 作为 MCP Server（推荐）

在 Claude Code 的 MCP 配置（`.mcp.json`）中添加：

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

然后让 Claude Code 执行屏幕任务：

> "用 AutoGUI 打开记事本并输入 Hello World"

### 使用 MCP Inspector 测试

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

## 许可证

MIT
