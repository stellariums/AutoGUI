import json
import os
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP, Context
from mcp.types import TextContent, ImageContent
from openai import AsyncOpenAI

from agent import ScreenAgent, Action

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a computer operation assistant. Your task is to complete the user's task through a series of screen operations.

Each response must return a JSON object in the following format:
{
    "thought": "Your reasoning process, analyzing the current screen state and what to do next",
    "action": "action type",
    "parameters": {
        "param1": "value1"
    },
    "dangerous": false
}

Available action types:
- click: Click, params: x, y (normalized coordinates 0-1000)
- double_click: Double click, params: x, y
- right_click: Right click, params: x, y
- type: Input text, params: text
- press: Key press, params: keys (key array, e.g. ["ctrl", "c"])
- scroll: Scroll, params: amount, x, y (optional)
- drag: Drag, params: start_x, start_y, end_x, end_y, duration (optional)
- move: Move cursor, params: x, y, duration (optional)
- wait: Wait, params: seconds
- task_complete: Task done, params: result (description of task result)

Notes:
1. Coordinate system uses 1000x1000 normalized coordinates, (0,0) is top-left, (1000,1000) is bottom-right
2. Execute only one action at a time
3. Carefully observe the screen content and make reasonable decisions
4. When the task is complete, use the task_complete action
5. If you encounter difficulties, try different approaches
6. "dangerous" field: set to true if the action may cause irreversible consequences (deleting files, closing programs, system operations, etc.)
"""


DEFAULT_CONFIG = {
    "api": {"base_url": "https://api.openai.com/v1", "api_key": "", "model": "gpt-4o", "max_tokens": 8192, "temperature": 0.7},
    "screen": {"capture_quality": 0.95, "compression_level": 6, "max_width": 1280, "max_height": 720, "allowed_region": None},
    "agent": {"max_iterations": 20, "delay_between_actions": 1.0, "confidence_threshold": 0.7, "max_history_rounds": 10},
    "safety": {"enable_confirmation": True, "fallback_action": "block", "dangerous_keys": ["delete", "backspace", "escape"], "dangerous_hotkeys": [["ctrl", "w"], ["alt", "f4"], ["ctrl", "shift", "delete"]], "dangerous_patterns": ["rm ", "del ", "format ", "shutdown", "reboot"]},
}


def load_config() -> dict:
    config = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            file_cfg = json.load(f)
        for section, values in file_cfg.items():
            if section in config and isinstance(values, dict):
                config[section].update(values)
            else:
                config[section] = values
    # Env vars override (highest priority)
    if v := os.environ.get("AUTOGUI_API_KEY"):
        config["api"]["api_key"] = v
    if v := os.environ.get("AUTOGUI_BASE_URL"):
        config["api"]["base_url"] = v
    if v := os.environ.get("AUTOGUI_MODEL"):
        config["api"]["model"] = v
    return config


# --- Lifespan ---

@asynccontextmanager
async def app_lifespan(server: FastMCP):
    config = load_config()
    api_cfg = config["api"]
    if not api_cfg["api_key"]:
        raise ValueError("API key required. Set AUTOGUI_API_KEY env var or api.api_key in config.json")
    client = AsyncOpenAI(base_url=api_cfg["base_url"], api_key=api_cfg["api_key"])
    agent = ScreenAgent(config)
    yield {
        "config": config,
        "client": client,
        "agent": agent,
        "lock": asyncio.Lock(),
    }


mcp = FastMCP("AutoGUI", lifespan=app_lifespan)


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
                    {"type": "text", "text": f"Current task: {task}\nAnalyze the screen and decide the next action."},
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
                            history.append({"role": "user", "content": [{"type": "text", "text": "This action was blocked by the user. Please try another approach."}]})
                            continue
                except Exception:
                    # elicit not supported
                    if agent.fallback_action == "block":
                        ctx.warning(f"Dangerous action blocked (no elicit): {desc}")
                        history.append({"role": "user", "content": [{"type": "text", "text": "This action was blocked by safety policy. Please try another approach."}]})
                        continue

            # Region bounds check
            if not agent.check_region_bounds(action):
                ctx.warning("Action out of allowed region, skipping")
                history.append({"role": "user", "content": [{"type": "text", "text": "Action coordinates are out of the allowed region. Please adjust."}]})
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
