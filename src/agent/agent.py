"""
LLM-Blender-Agent compatible agent, adapted for Infinigen scene editing.

This keeps the original Agent/UI workflow: the LLM receives function definitions,
emits function calls, and the agent dispatches them to `BlenderClient`. The old
Rodin/Hunyuan3D generation function list is replaced by Infinigen and scene-graph
tools.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, Iterator, List, Optional, Union

from ..blender.client import BlenderClient
from ..llm.base import BaseLLM


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


PHYSICAL_RULES_PROMPT = """你是 Blender/Infinigen 场景编辑 planner。
遵守这些写死的物理规则：
- 不要让对象悬空；空间编辑后对被编辑对象调用 apply_physics_rules，再调用 rebuild_scene_index。
- 表达“放到上面”时优先用 place_on，不要用裸 move_object。
- 表达“旁边/靠墙”时优先用 place_near/place_against_wall。
- 大型家具默认落地；地毯必须落地；灯和水果等小物体需要支撑面。
- 缩放保持在合理范围，执行层会把极端 scale clamp 到安全范围。
不要生成 Python 代码，只使用提供的 function call。
"""


class BlenderAgent:
    """Agent that converts LLM function calls into Infinigen-aware Blender edits."""

    def __init__(self, llm: BaseLLM, blender_client: BlenderClient):
        self.llm = llm
        self.blender_client = blender_client
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": PHYSICAL_RULES_PROMPT}]
        self.current_run_id: str | None = None
        self._last_cancel_check = 0.0
        self._init_functions()

    def update_blender_client(self, blender_client: BlenderClient):
        self.blender_client = blender_client

    def _init_functions(self):
        self.functions = [
            {
                "name": "get_scene_info",
                "description": "获取当前 Blender/Infinigen 场景信息和对象列表。",
                "parameters": {},
                "required": [],
            },
            {
                "name": "rebuild_scene_index",
                "description": "重建当前场景的语义索引，返回每个资产的类别、尺寸、位置、材质和空间关系。",
                "parameters": {
                    "save_path": {"type": "string", "description": "索引 JSON 保存路径，可选。"}
                },
                "required": [],
            },
            {
                "name": "query_objects",
                "description": "根据自然语言、类别、对象名或 object_id 查询当前场景资产。",
                "parameters": {
                    "text": {"type": "string", "description": "查询文本，例如：床旁边的桌子、台灯、desk"},
                    "category": {
                        "type": "string",
                        "description": "可选类别：bed, desk, table, side_table, lamp, chair, sofa, cabinet, bookcase, rug, plant, apple, blackberry, green_coconut, hairy_coconut, durian, pineapple, starfruit, strawberry, compositional_fruit, wall, floor, room",
                    },
                },
                "required": [],
            },
            {
                "name": "open_blend",
                "description": "打开一个 .blend 场景文件。",
                "parameters": {
                    "path": {"type": "string", "description": "要打开的 .blend 文件绝对路径。"}
                },
                "required": ["path"],
            },
            {
                "name": "save_blend",
                "description": "保存当前 .blend 文件。",
                "parameters": {
                    "path": {"type": "string", "description": "保存路径，可选；不填则保存当前文件。"}
                },
                "required": [],
            },
            {
                "name": "add_infinigen_asset",
                "description": "通过 Infinigen factory 在当前场景中添加家具或物体，替代 Rodin/Hunyuan3D 生成。",
                "parameters": {
                    "category_or_factory": {
                        "type": "string",
                        "description": "资产类别或 Infinigen factory，例如 bed, desk, side_table, desk_lamp, chair, sofa, cabinet, bookcase, rug, plant, apple, blackberry, green_coconut, hairy_coconut, durian, pineapple, starfruit, strawberry, compositional_fruit。",
                    },
                    "seed": {"type": "integer", "description": "随机种子，可选。"},
                    "location": {"type": "array", "description": "放置位置 [x, y, z]，可选。"},
                    "scale": {"type": "number", "description": "整体缩放，可选；草莓默认 0.15，其他资产默认 1.0。"},
                },
                "required": ["category_or_factory"],
            },
            {
                "name": "edit_generated_asset",
                "description": "编辑已生成资产的生成脚本，重新生成并替换场景中的旧资产，同时保持原位置和大小对齐。用户以 \\editing 开头时优先使用。",
                "parameters": {
                    "target": {"type": "string", "description": "目标对象，例如 桌子、desk、asset_xxx。"},
                    "prompt": {"type": "string", "description": "完整编辑指令，例如：场景中的桌子改成绿色。"},
                    "color": {
                        "type": "string",
                        "description": "可选颜色：red, blue, green, white, black, wood 或 #RRGGBB。",
                    },
                    "preserve_size": {"type": "boolean", "description": "是否保持原资产大小，默认 true。"},
                },
                "required": ["target", "prompt"],
            },
            {
                "name": "move_object",
                "description": "按方向移动对象。target 可以是 object_id、对象名、类别或自然语言描述。",
                "parameters": {
                    "target": {"type": "string", "description": "目标对象，例如 bed、桌子、asset_xxx。"},
                    "direction": {
                        "type": "string",
                        "description": "方向：left, right, front, back, up, down。",
                        "enum": ["left", "right", "front", "back", "up", "down"],
                    },
                    "distance": {"type": "number", "description": "移动距离，单位米。"},
                },
                "required": ["target", "direction", "distance"],
            },
            {
                "name": "scale_object",
                "description": "缩放对象。factor 大于 1 为放大，小于 1 为缩小。",
                "parameters": {
                    "target": {"type": "string", "description": "目标对象。"},
                    "factor": {"type": "number", "description": "缩放倍数，例如 1.2 或 0.8。"},
                },
                "required": ["target", "factor"],
            },
            {
                "name": "rotate_object",
                "description": "旋转对象。",
                "parameters": {
                    "target": {"type": "string", "description": "目标对象。"},
                    "axis": {"type": "string", "description": "旋转轴：x, y, z。", "enum": ["x", "y", "z"]},
                    "angle_degrees": {"type": "number", "description": "旋转角度，单位度。"},
                },
                "required": ["target", "axis", "angle_degrees"],
            },
            {
                "name": "place_on",
                "description": "把 source 放到 target 的上表面中心，例如把台灯放到桌子上。",
                "parameters": {
                    "source": {"type": "string", "description": "要移动的对象。"},
                    "target": {"type": "string", "description": "承载对象。"},
                },
                "required": ["source", "target"],
            },
            {
                "name": "place_near",
                "description": "把 source 放到 target 旁边。",
                "parameters": {
                    "source": {"type": "string", "description": "要移动的对象。"},
                    "target": {"type": "string", "description": "参考对象。"},
                    "side": {
                        "type": "string",
                        "description": "相对方向：left, right, front, back。",
                        "enum": ["left", "right", "front", "back"],
                    },
                    "gap": {"type": "number", "description": "间距，单位米。"},
                },
                "required": ["source", "target"],
            },
            {
                "name": "place_against_wall",
                "description": "将目标对象靠近最近墙面或指定墙面。",
                "parameters": {
                    "target": {"type": "string", "description": "目标对象。"},
                    "wall": {"type": "string", "description": "墙对象，可选。"},
                    "gap": {"type": "number", "description": "离墙间距，单位米。"},
                },
                "required": ["target"],
            },
            {
                "name": "apply_physics_rules",
                "description": "对场景或指定对象应用写死的物理规则：防悬空、贴地、缩放/放置后的基础碰撞提示。",
                "parameters": {
                    "target": {"type": "string", "description": "目标对象；不填则检查整个场景。"}
                },
                "required": [],
            },
            {
                "name": "set_material",
                "description": "修改对象材质颜色。",
                "parameters": {
                    "target": {"type": "string", "description": "目标对象。"},
                    "object_name": {"type": "string", "description": "兼容旧字段，目标对象名。"},
                    "material_name": {"type": "string", "description": "材质名，可选。"},
                    "color": {
                        "type": "string",
                        "description": "颜色：red, blue, green, white, black, wood 或 #RRGGBB。",
                    },
                },
                "required": [],
            },
            {
                "name": "delete_object",
                "description": "删除对象。",
                "parameters": {
                    "target": {"type": "string", "description": "目标对象。"},
                    "name": {"type": "string", "description": "兼容旧字段，目标对象名。"},
                },
                "required": [],
            },
            {
                "name": "render_scene",
                "description": "渲染当前场景并返回预览路径。",
                "parameters": {
                    "output_path": {"type": "string", "description": "输出图片路径，可选。"},
                    "resolution_x": {"type": "integer", "description": "宽度，可选。"},
                    "resolution_y": {"type": "integer", "description": "高度，可选。"},
                },
                "required": [],
            },
        ]

    def add_message(self, role: str, content: Union[str, List[Dict[str, Any]]]):
        if isinstance(content, list) and role == "user":
            text_content = ""
            image_urls = []
            for item in content:
                if item.get("type") == "text":
                    text_content += item.get("text", "")
                elif item.get("type") == "image_url" and "image_url" in item:
                    image_urls.append(item["image_url"].get("url", ""))
            if image_urls:
                if text_content:
                    text_content += "，"
                text_content += f"图片url为: {', '.join(image_urls)}"
            if text_content:
                content = text_content

        self.messages.append({"role": role, "content": content})
        n_keep_first, n_keep_latest = 1, 5
        max_messages = (n_keep_first * 2) + (n_keep_latest * 2)
        if len(self.messages) > max_messages:
            self.messages = self.messages[:n_keep_first] + self.messages[-(n_keep_latest * 2) :]

    def reset_messages(self):
        self.messages = [{"role": "system", "content": PHYSICAL_RULES_PROMPT}]

    def chat_stream(
        self,
        user_message: Union[str, List[Dict[str, Any]]],
        functions: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> Iterator[Dict[str, Any]]:
        functions_to_use = functions if functions is not None else self.functions
        if user_message:
            self.add_message("user", user_message)

        if not hasattr(self.llm, "chat_stream"):
            raise NotImplementedError("当前 LLM 不支持流式响应")

        self.current_run_id = uuid.uuid4().hex
        self._last_cancel_check = 0.0
        self._set_agent_status("running", "LLM 正在生成回复", operation="llm")
        response_stream = self.llm.chat_stream(
            messages=self.messages,
            functions=functions_to_use,
            temperature=temperature,
        )

        accumulated_content = ""
        function_call = None
        try:
            for chunk in response_stream:
                self._raise_if_blender_cancelled()
                content_chunk = chunk.get("content")
                function_call_chunk = chunk.get("function_call")
                if content_chunk:
                    accumulated_content += content_chunk
                if function_call_chunk:
                    function_call = function_call_chunk
                yield chunk

            self._raise_if_blender_cancelled(force=True)

            if accumulated_content:
                self.add_message("assistant", accumulated_content)
            elif function_call:
                self.add_message("assistant", f"我将执行工具: {function_call['name']}")

            if function_call:
                function_result = self._execute_function(function_call)
                self.add_message(
                    "user",
                    f"函数 {function_call['name']} 的执行结果: {json.dumps(function_result, ensure_ascii=False)}",
                )
                yield {
                    "content": None,
                    "function_call": function_call,
                    "function_result": function_result,
                }
        except GeneratorExit:
            self._set_agent_status("cancelled", "UI 已停止 Agent 运行")
            raise
        except RuntimeError as exc:
            if str(exc) != "Agent run cancelled from Blender":
                raise
            self._set_agent_status("cancelled", "Blender 已请求停止 Agent 运行")
            yield {
                "content": "已停止运行。",
                "function_call": None,
                "function_result": {"status": "cancelled", "message": "Blender 已请求停止 Agent 运行"},
            }
        finally:
            if self.current_run_id:
                self.current_run_id = None

    def _execute_function(self, function_call: Dict[str, Any]) -> Dict[str, Any]:
        try:
            function_name = function_call["name"]
            arguments = function_call.get("arguments", {})
            if isinstance(arguments, str):
                arguments = json.loads(arguments) if arguments.strip() else {}

            if self.blender_client is None:
                return {"status": "error", "message": "Blender 未连接，请先连接 Blender 插件服务。"}
            if not hasattr(self.blender_client, function_name):
                return {"status": "error", "message": f"函数 {function_name} 不存在"}

            self._raise_if_blender_cancelled(force=True)
            self._set_agent_status("running", f"正在 Blender 中执行：{function_name}", operation=function_name)
            func = getattr(self.blender_client, function_name)
            logger.info("执行函数: %s, 参数: %s", function_name, arguments)
            result = func(**arguments)
            logger.info("函数执行结果: %s", result)
            self._raise_if_blender_cancelled(force=True)
            return result
        except RuntimeError as exc:
            if str(exc) == "Agent run cancelled from Blender":
                raise
            logger.error("执行函数 %s 时出错: %s", function_call.get("name", "未知"), exc)
            return {"status": "error", "message": f"执行函数时出错: {exc}"}
        except Exception as exc:
            logger.error("执行函数 %s 时出错: %s", function_call.get("name", "未知"), exc)
            return {"status": "error", "message": f"执行函数时出错: {exc}"}

    def _set_agent_status(self, state: str, message: str = "", operation: str | None = None) -> None:
        if self.blender_client is None or not hasattr(self.blender_client, "set_agent_status"):
            return
        try:
            self.blender_client.set_agent_status(
                state=state,
                message=message,
                run_id=self.current_run_id,
                operation=operation,
            )
        except Exception as exc:
            logger.debug("同步 Agent 状态到 Blender 失败: %s", exc)

    def _raise_if_blender_cancelled(self, force: bool = False) -> None:
        if self.blender_client is None or not hasattr(self.blender_client, "get_agent_status"):
            return
        now = time.monotonic()
        if not force and now - self._last_cancel_check < 0.5:
            return
        self._last_cancel_check = now
        try:
            status = self.blender_client.get_agent_status()
        except Exception as exc:
            logger.debug("读取 Blender Agent 状态失败: %s", exc)
            return
        result = status.get("result", status)
        if isinstance(result, dict) and result.get("cancel_requested"):
            raise RuntimeError("Agent run cancelled from Blender")

    def update_blender_client(self, blender_client: BlenderClient):
        self.blender_client = blender_client
        logger.info("已更新 Agent 中的 Blender 客户端引用")
