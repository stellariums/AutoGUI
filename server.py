import json
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP, Context
from mcp.types import TextContent, ImageContent
from openai import AsyncOpenAI

from agent import ScreenAgent, Action

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个电脑操作助手。你的任务是根据用户的指令，通过一系列操作来完成用户的任务。

每次响应必须返回一个 JSON 对象，格式如下：
{
    "thought": "你的思考过程，分析当前屏幕状态和下一步该做什么",
    "action": "动作类型",
    "parameters": {
        "参数1": "值1"
    },
    "dangerous": false
}

可用的动作类型：
- click: 点击，参数：x, y (0-1000 的归一化坐标)
- double_click: 双击，参数：x, y
- right_click: 右键点击，参数：x, y
- type: 输入文本，参数：text
- press: 按键，参数：keys (按键数组，如 ["ctrl", "c"])
- scroll: 滚动，参数：amount, x, y (可选)
- drag: 拖拽，参数：start_x, start_y, end_x, end_y, duration (可选)
- move: 移动鼠标，参数：x, y, duration (可选)
- wait: 等待，参数：seconds
- task_complete: 任务完成，参数：result (任务结果描述)

注意：
1. 坐标系统使用 1000x1000 的归一化坐标，(0,0) 是左上角，(1000,1000) 是右下角
2. 每次只执行一个动作
3. 仔细观察屏幕内容，做出合理的决策
4. 如果任务完成，使用 task_complete 动作
5. 如果遇到困难，尝试不同的方法
6. "dangerous" 字段：如果该操作可能造成不可逆后果（删除文件、关闭程序、系统操作等），设为 true
"""


# --- Lifespan ---

@asynccontextmanager
async def app_lifespan(server: FastMCP):
    config_path = Path(__file__).parent / "config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    api_cfg = config["api"]
    client = AsyncOpenAI(base_url=api_cfg["base_url"], api_key=api_cfg["api_key"])
    agent = ScreenAgent(config)
    yield {
        "config": config,
        "client": client,
        "agent": agent,
        "lock": asyncio.Lock(),
    }


mcp = FastMCP("autogui", lifespan=app_lifespan)


# --- Helper ---

def trim_history(history: list, max_rounds: int) -> list:
    # Keep system message + last N user/assistant pairs
    if len(history) <= 1 + max_rounds * 2:
        return history
    return history[:1] + history[-(max_rounds * 2):]


# --- Tool ---

@mcp.tool()
async def autogui_execute_task(task: str, ctx: Context) -> list[TextContent | ImageContent]:
    """Execute a screen automation task using AI-driven visual analysis.
    The internal AI will capture screenshots, analyze them, and perform mouse/keyboard
    actions to complete the given natural language task.

    Args:
        task: Natural language description of the task to perform on screen.
    """
    state = ctx.request_context.lifespan_context
    config = state["config"]
    client: AsyncOpenAI = state["client"]
    agent: ScreenAgent = state["agent"]
    lock: asyncio.Lock = state["lock"]

    if lock.locked():
        return [TextContent(type="text", text=json.dumps({"error": "Another task is already running"}))]

    async with lock:
        api_cfg = config["api"]
        history = [{"role": "system", "content": SYSTEM_PROMPT}]
        last_screenshot_b64 = None

        for iteration in range(1, agent.max_iterations + 1):
            # Capture screenshot
            try:
                screenshot_b64 = await asyncio.to_thread(agent.capture_screen_compressed)
            except asyncio.CancelledError:
                return [TextContent(type="text", text=json.dumps({"status": "cancelled", "iteration": iteration}))]

            last_screenshot_b64 = screenshot_b64
            await ctx.report_progress(iteration, agent.max_iterations)
            ctx.info(f"Iteration {iteration}/{agent.max_iterations}")

            user_msg = {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"当前任务：{task}\n请分析屏幕并决定下一步操作。"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
                ],
            }
            history.append(user_msg)
            history = trim_history(history, agent.max_history_rounds)

            # Call AI
            try:
                response = await client.chat.completions.create(
                    model=api_cfg["model"],
                    messages=history,
                    max_tokens=api_cfg["max_tokens"],
                    temperature=api_cfg["temperature"],
                )
            except asyncio.CancelledError:
                return [TextContent(type="text", text=json.dumps({"status": "cancelled", "iteration": iteration}))]

            ai_text = response.choices[0].message.content
            history.append({"role": "assistant", "content": ai_text})
            ctx.info(f"AI response: {ai_text[:200]}")

            # Parse action
            action = agent.parse_action(ai_text)
            if action is None:
                ctx.warning("Failed to parse action, retrying...")
                continue

            # Safety checks
            is_dangerous = action.dangerous or agent.detect_dangerous_rules(action)
            if is_dangerous and agent.enable_confirmation:
                desc = f"[{action.action_type}] {json.dumps(action.parameters, ensure_ascii=False)}"
                try:
                    result = await ctx.elicit(
                        message=f"Dangerous action detected: {desc}\nThought: {action.thought}",
                        schema={"type": "object", "properties": {"confirm": {"type": "boolean", "description": "Allow this action?"}}, "required": ["confirm"]},
                    )
                    if result and result.action == "accept" and result.data and result.data.get("confirm"):
                        pass  # approved
                    else:
                        if agent.fallback_action == "block":
                            ctx.warning(f"Dangerous action blocked: {desc}")
                            history.append({"role": "user", "content": [{"type": "text", "text": "该操作被用户阻止，请尝试其他方法。"}]})
                            continue
                except Exception:
                    # elicit not supported
                    if agent.fallback_action == "block":
                        ctx.warning(f"Dangerous action blocked (no elicit): {desc}")
                        history.append({"role": "user", "content": [{"type": "text", "text": "该操作被安全策略阻止，请尝试其他方法。"}]})
                        continue

            # Region bounds check
            if not agent.check_region_bounds(action):
                ctx.warning("Action out of allowed region, skipping")
                history.append({"role": "user", "content": [{"type": "text", "text": "操作坐标超出允许区域，请调整。"}]})
                continue

            # Execute
            try:
                exec_result = await asyncio.to_thread(agent.execute_action, action)
            except asyncio.CancelledError:
                return [TextContent(type="text", text=json.dumps({"status": "cancelled", "iteration": iteration}))]

            ctx.info(f"Action: {action.action_type} -> {exec_result}")

            if action.action_type.lower() == "task_complete":
                result_obj = {"status": "completed", "result": action.parameters.get("result", exec_result), "iterations": iteration}
                contents: list[TextContent | ImageContent] = [TextContent(type="text", text=json.dumps(result_obj, ensure_ascii=False))]
                if last_screenshot_b64:
                    contents.append(ImageContent(type="image", data=last_screenshot_b64, mimeType="image/png"))
                return contents

            await asyncio.sleep(agent.delay)

        # Max iterations reached
        result_obj = {"status": "incomplete", "message": "Max iterations reached", "iterations": agent.max_iterations}
        contents: list[TextContent | ImageContent] = [TextContent(type="text", text=json.dumps(result_obj, ensure_ascii=False))]
        if last_screenshot_b64:
            contents.append(ImageContent(type="image", data=last_screenshot_b64, mimeType="image/png"))
        return contents


# --- Entry point ---

if __name__ == "__main__":
    mcp.run(transport="stdio")
