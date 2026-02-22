import json
import base64
import re
import io
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

import mss
import mss.tools
import pyautogui
import pyperclip
from PIL import Image


@dataclass
class Action:
    action_type: str
    parameters: Dict[str, Any]
    thought: str
    dangerous: bool = False


class ScreenAgent:
    def __init__(self, config: dict):
        self.config = config
        self.max_iterations = config["agent"]["max_iterations"]
        self.delay = config["agent"]["delay_between_actions"]
        self.max_history_rounds = config["agent"].get("max_history_rounds", 10)

        screen_cfg = config.get("screen", {})
        self.max_width = screen_cfg.get("max_width", 1280)
        self.max_height = screen_cfg.get("max_height", 720)
        self.allowed_region = screen_cfg.get("allowed_region", None)

        safety_cfg = config.get("safety", {})
        self.enable_confirmation = safety_cfg.get("enable_confirmation", True)
        self.fallback_action = safety_cfg.get("fallback_action", "block")
        self.dangerous_keys = [k.lower() for k in safety_cfg.get("dangerous_keys", [])]
        self.dangerous_hotkeys = [
            [k.lower() for k in combo]
            for combo in safety_cfg.get("dangerous_hotkeys", [])
        ]
        self.dangerous_patterns = safety_cfg.get("dangerous_patterns", [])

        self.screen_width, self.screen_height = pyautogui.size()

    def capture_screen(self) -> str:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            img_data = mss.tools.to_png(screenshot.rgb, screenshot.size)
            return base64.b64encode(img_data).decode("utf-8")

    def compress_screenshot(self, base64_png: str) -> str:
        raw = base64.b64decode(base64_png)
        img = Image.open(io.BytesIO(raw))
        img.thumbnail((self.max_width, self.max_height), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def capture_screen_compressed(self) -> str:
        return self.compress_screenshot(self.capture_screen())

    def map_coordinates(self, x: float, y: float) -> tuple[int, int]:
        real_x = int(x / 1000 * self.screen_width)
        real_y = int(y / 1000 * self.screen_height)
        return real_x, real_y

    def check_region_bounds(self, action: Action) -> bool:
        if self.allowed_region is None:
            return True
        region = self.allowed_region
        params = action.parameters
        for kx, ky in [("x", "y"), ("start_x", "start_y"), ("end_x", "end_y")]:
            if kx in params and ky in params:
                nx, ny = params[kx] / 1000, params[ky] / 1000
                if not (region["x1"] <= nx <= region["x2"] and region["y1"] <= ny <= region["y2"]):
                    return False
        return True

    def detect_dangerous_rules(self, action: Action) -> bool:
        at = action.action_type.lower()
        params = action.parameters
        if at == "press":
            keys = params.get("keys", [])
            if isinstance(keys, str):
                keys = [keys]
            keys_lower = [k.lower() for k in keys]
            if len(keys_lower) == 1 and keys_lower[0] in self.dangerous_keys:
                return True
            for combo in self.dangerous_hotkeys:
                if sorted(keys_lower) == sorted(combo):
                    return True
        if at == "type":
            text = params.get("text", "").lower()
            for pat in self.dangerous_patterns:
                if pat.lower() in text:
                    return True
        return False

    def execute_action(self, action: Action) -> str:
        action_type = action.action_type.lower()
        params = action.parameters

        try:
            if action_type == "click":
                x, y = self.map_coordinates(params.get("x", 500), params.get("y", 500))
                pyautogui.click(x, y)
                return f"Clicked at ({x}, {y})"

            elif action_type == "double_click":
                x, y = self.map_coordinates(params.get("x", 500), params.get("y", 500))
                pyautogui.doubleClick(x, y)
                return f"Double clicked at ({x}, {y})"

            elif action_type == "right_click":
                x, y = self.map_coordinates(params.get("x", 500), params.get("y", 500))
                pyautogui.rightClick(x, y)
                return f"Right clicked at ({x}, {y})"

            elif action_type == "type":
                text = params.get("text", "")
                pyperclip.copy(text)
                pyautogui.hotkey("ctrl", "v")
                return f"Typed: {text}"

            elif action_type == "press":
                keys = params.get("keys", [])
                if isinstance(keys, str):
                    keys = [keys]
                pyautogui.hotkey(*keys)
                return f"Pressed: {'+'.join(keys)}"

            elif action_type == "scroll":
                amount = params.get("amount", 100)
                x = params.get("x")
                y = params.get("y")
                if x is not None and y is not None:
                    x, y = self.map_coordinates(x, y)
                    pyautogui.scroll(amount, x=x, y=y)
                else:
                    pyautogui.scroll(amount)
                return f"Scrolled: {amount}"

            elif action_type == "drag":
                start_x, start_y = self.map_coordinates(params.get("start_x", 500), params.get("start_y", 500))
                end_x, end_y = self.map_coordinates(params.get("end_x", 500), params.get("end_y", 500))
                duration = params.get("duration", 1.0)
                pyautogui.moveTo(start_x, start_y)
                pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration)
                return f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})"

            elif action_type == "move":
                x, y = self.map_coordinates(params.get("x", 500), params.get("y", 500))
                duration = params.get("duration", 0.5)
                pyautogui.moveTo(x, y, duration=duration)
                return f"Moved to ({x}, {y})"

            elif action_type == "wait":
                seconds = params.get("seconds", 1.0)
                time.sleep(seconds)
                return f"Waited for {seconds} seconds"

            elif action_type == "task_complete":
                return "Task completed successfully"

            else:
                return f"Unknown action type: {action_type}"

        except Exception as e:
            return f"Error executing action: {str(e)}"

    def parse_action(self, response_text: str) -> Optional[Action]:
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                action_json = json.loads(json_match.group())
                return Action(
                    action_type=action_json.get("action", "wait"),
                    parameters=action_json.get("parameters", {}),
                    thought=action_json.get("thought", ""),
                    dangerous=action_json.get("dangerous", False),
                )
        except Exception:
            pass
        return None
