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
import re
import time
import uuid
from typing import Any, Dict, Iterator, List, Optional, Union

from ..blender.client import BlenderClient
from ..llm.base import BaseLLM
from .visual_verifier import VisualVerifierAgent


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


PHYSICAL_RULES_PROMPT = """你是 Blender/Infinigen 场景编辑 planner。
遵守这些写死的物理规则：
- 把cube删掉
- 严格按照用户当前指令执行，只做用户明确要求的动作。
- 不要乱加东西；不要为了“更自然”“更丰富”“更好看”添加、移动、删除或修改用户没有要求的物体。
- 如果用户只要求添加草莓并放到椅子上，就只添加/移动指令中明确提到的草莓和椅子相关对象，并执行必要的物理/索引更新；不要添加桌子或其他未提到的家具。
- 符合物理常识，例如：家具通常放在地面上
- 水果比家具小，地毯比家具大但很薄，灯具需要支撑面。
- 苹果、草莓、黑莓等水果必须保持真实桌面物件大小；除非用户明确要求巨大水果，否则不要给水果使用 1.0 这类家具级 scale。
- 不要让对象悬空；空间编辑后对被编辑对象调用 apply_physics_rules，再调用 rebuild_scene_index。
- 表达“放到上面”时优先用 place_on，不要用裸 move_object。
- 对椅子/沙发表达“放在上面”时，目标是坐垫/承托面，不是椅背或靠背顶部。
- 表达“旁边/靠墙”时优先用 place_near/place_against_wall。
- 大型家具默认落地；地毯必须落地。
- 缩放保持在合理范围，执行层会把极端 scale clamp 到安全范围。
- 用户要求调整视角、构图、相机位置、让渲染主体居中或变大/变小时，优先调用 adjust_camera_from_render。
不要生成 Python 代码，只使用提供的 function call。
任务完成后回复“全部完成”，不要主动提出或执行额外优化。
"""


ASSET_REQUEST_ALIASES = {
    "bed": ("bed", "床"),
    "desk": ("desk", "书桌", "桌子", "办公桌"),
    "table": ("table", "桌", "桌子", "餐桌"),
    "side_table": ("side_table", "床头柜", "边几", "nightstand"),
    "desk_lamp": ("desk_lamp", "lamp", "台灯", "灯"),
    "chair": ("chair", "椅子", "座椅"),
    "sofa": ("sofa", "沙发"),
    "cabinet": ("cabinet", "柜子"),
    "bookcase": ("bookcase", "书架"),
    "rug": ("rug", "地毯"),
    "plant": ("plant", "植物", "盆栽"),
    "apple": ("apple", "苹果", "青苹果", "绿苹果"),
    "blackberry": ("blackberry", "黑莓"),
    "green_coconut": ("green_coconut", "coconutgreen", "青椰子", "椰青"),
    "hairy_coconut": ("hairy_coconut", "coconuthairy", "椰子", "毛椰子"),
    "durian": ("durian", "榴莲"),
    "pineapple": ("pineapple", "菠萝", "凤梨"),
    "starfruit": ("starfruit", "杨桃"),
    "strawberry": ("strawberry", "草莓"),
    "compositional_fruit": ("compositional_fruit", "组合水果", "复合水果"),
}


class BlenderAgent:
    """Agent that converts LLM function calls into Infinigen-aware Blender edits."""

    def __init__(
        self,
        llm: BaseLLM,
        blender_client: BlenderClient,
        visual_verifier: VisualVerifierAgent | None = None,
    ):
        self.llm = llm
        self.blender_client = blender_client
        self.visual_verifier = visual_verifier
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": PHYSICAL_RULES_PROMPT}]
        self.current_run_id: str | None = None
        self.current_user_request_text = ""
        self._last_cancel_check = 0.0
        self._init_functions()

    def update_blender_client(self, blender_client: BlenderClient):
        self.blender_client = blender_client

    def update_visual_verifier(self, visual_verifier: VisualVerifierAgent | None):
        self.visual_verifier = visual_verifier

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
                    "scale": {"type": "number", "description": "整体缩放，可选；水果已有小尺寸默认值，例如苹果约 0.12、草莓约 0.15，除非用户明确要求不要传 1.0。"},
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
                "description": "把 source 放到 target 的可承托上表面中心，例如桌面或椅子坐垫。",
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
                "description": "渲染当前场景并返回预览路径。默认会先检查相机视角，如果主体不够近或没有看见所有非结构物体，会自动调整 camera 后再渲染。",
                "parameters": {
                    "output_path": {"type": "string", "description": "输出图片路径，可选。"},
                    "resolution_x": {"type": "integer", "description": "宽度，可选。"},
                    "resolution_y": {"type": "integer", "description": "高度，可选。"},
                    "auto_adjust_camera": {"type": "boolean", "description": "是否在渲染前自动检查并调整 camera，默认 true。"},
                    "camera_target": {"type": "string", "description": "可选，指定用于检查构图的目标对象；不填则使用所有非结构资产。"},
                    "camera_target_fill": {"type": "number", "description": "目标主体画面占比，默认 0.72。"},
                },
                "required": [],
            },
            {
                "name": "adjust_camera_from_render",
                "description": "Camera agent：先渲染透明 mask 图片，分析目标/场景在图片中的像素位置和占比，再自动平移/推拉 Blender camera，最后渲染新的预览图。适合用户要求调整视角、让对象居中、让画面构图更好或渲染主体太小/太大时使用。",
                "parameters": {
                    "target": {"type": "string", "description": "要构图的目标对象/类别/自然语言描述；不填则使用场景中的非结构资产。"},
                    "output_path": {"type": "string", "description": "调整后预览图输出路径，可选。"},
                    "target_fill": {"type": "number", "description": "目标主体画面占比，0.2-0.95，默认 0.72。"},
                    "max_iterations": {"type": "integer", "description": "根据渲染图迭代调整次数，默认 3。"},
                    "tolerance": {"type": "number", "description": "居中和缩放误差容忍度，默认 0.06。"},
                    "resolution_x": {"type": "integer", "description": "分析用 mask 渲染宽度，默认 768。"},
                    "resolution_y": {"type": "integer", "description": "分析用 mask 渲染高度，默认 432。"},
                    "final_resolution_x": {"type": "integer", "description": "最终预览图宽度，默认 1280。"},
                    "final_resolution_y": {"type": "integer", "description": "最终预览图高度，默认 720。"},
                },
                "required": [],
            },
            {
                "name": "adjust_existing_light",
                "description": "移动并增强场景中已有的 Blender Light，使 prompt 相关物体可辨认；不会新增光源。仅在渲染太暗、物体看不清、Verifier 明确要求调整已有 Light，或用户要求调整光照时使用。",
                "parameters": {
                    "target": {"type": "string", "description": "需要照亮的目标对象/类别/自然语言描述；不填则使用所有非结构资产。"},
                    "light": {"type": "string", "description": "已有 Light 名称，可选；不填则使用场景中的已有 Light。"},
                    "min_energy": {"type": "number", "description": "已有 Light 的最低能量，默认 900。"},
                    "height": {"type": "number", "description": "相对目标中心向上的高度，可选。"},
                    "distance": {"type": "number", "description": "相对目标中心沿相机方向的水平距离，可选。"},
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

    def _message_to_text(self, message: Union[str, List[Dict[str, Any]]]) -> str:
        if isinstance(message, str):
            return message
        parts: list[str] = []
        for item in message:
            if item.get("type") == "text":
                parts.append(str(item.get("text") or item.get("content") or ""))
        return " ".join(part for part in parts if part)

    def _category_from_asset_request(self, value: Any) -> str:
        text = str(value or "").lower()
        for category, aliases in ASSET_REQUEST_ALIASES.items():
            if category in text or any(str(alias).lower() in text for alias in aliases):
                return category
        return text

    def _mentioned_asset_categories(self) -> set[str]:
        text = self.current_user_request_text.lower()
        requested: set[str] = set()
        for category, aliases in ASSET_REQUEST_ALIASES.items():
            if category in text or any(str(alias).lower() in text for alias in aliases):
                requested.add(category)
        return requested

    def _validate_function_call_against_request(self, function_call: Dict[str, Any]) -> Dict[str, Any] | None:
        if function_call.get("name") != "add_infinigen_asset":
            return None

        arguments = function_call.get("arguments", {})
        category = self._category_from_asset_request(
            arguments.get("category_or_factory") or arguments.get("category")
        )
        requested = self._mentioned_asset_categories()
        if category in requested:
            return None

        return {
            "status": "blocked",
            "message": (
                f"已阻止添加未在原始指令中明确要求的资产：{category}。"
                "Agent 将严格按照用户指令执行，不主动丰富场景。"
            ),
            "function": function_call.get("name"),
            "requested_assets": sorted(requested),
            "blocked_asset": category,
        }

    def chat_stream(
        self,
        user_message: Union[str, List[Dict[str, Any]]],
        functions: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> Iterator[Dict[str, Any]]:
        functions_to_use = functions if functions is not None else self.functions
        if user_message:
            user_text = self._message_to_text(user_message).strip()
            if user_text and "继续完成原始用户指令" not in user_text:
                self.current_user_request_text = user_text
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
            function_call["arguments"] = arguments

            if self.blender_client is None:
                return {"status": "error", "message": "Blender 未连接，请先连接 Blender 插件服务。"}
            if not hasattr(self.blender_client, function_name):
                return {"status": "error", "message": f"函数 {function_name} 不存在"}

            blocked = self._validate_function_call_against_request(function_call)
            if blocked is not None:
                return blocked

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
