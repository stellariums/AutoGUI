# Computer Control Agent

基于视觉的电脑操作 Agent，使用 AI 模型分析屏幕并执行操作。

## 功能特点

- 🖥️ 实时屏幕截图分析
- 🤖 AI 驱动的任务规划和决策
- 🎯 自动坐标映射 (1000x1000 → 实际分辨率)
- ⌨️ 支持多种操作：点击、输入、快捷键、拖拽等
- 🔄 自动循环执行直到任务完成

## 安装

```bash
pip install -r requirements.txt
```

## 配置

编辑 `config.json` 文件：

```json
{
  "api": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "your-api-key-here",
    "model": "gpt-4o"
  }
}
```

## 使用

```bash
python agent.py
```

然后输入你的任务，例如：
- "打开记事本并输入'Hello World'"
- "搜索桌面上的 Chrome 图标并打开它"
- "最小化所有窗口"

## 支持的操作

| 操作 | 说明 |
|------|------|
| click | 点击指定位置 |
| double_click | 双击 |
| right_click | 右键点击 |
| type | 输入文本 |
| press | 按键组合 |
| scroll | 滚动 |
| drag | 拖拽 |
| move | 移动鼠标 |
| wait | 等待 |
| task_complete | 标记任务完成 |
