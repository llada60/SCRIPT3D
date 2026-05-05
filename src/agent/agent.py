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


PHYSICAL_RULES_PROMPT = """You are a Blender/Infinigen scene-editing planner.
Follow these fixed physical and behavioral rules:
- Remove the default cube when it is not relevant.
- Follow only the user's current instruction. Perform only explicitly requested actions.
- Do not add, delete, move, or modify objects that the user did not request, even if it would make the scene more natural, richer, or prettier.
- If the user only asks to add a strawberry and place it on a chair, only add/move the explicitly requested strawberry and chair-related objects; do not add a table or any other unrequested furniture.
- Follow basic physical plausibility: furniture usually rests on the floor.
- Fruit should be smaller than furniture; rugs should be larger than furniture but thin; lights need plausible support or placement.
- Apples, strawberries, blackberries, and other fruit must stay at realistic tabletop-object sizes unless the user explicitly requests giant fruit. Do not use furniture-scale values such as 1.0 for fruit.
- Do not leave objects floating. After spatial edits, call apply_physics_rules for edited objects, then call rebuild_scene_index.
- For "put on top of" requests, prefer place_on instead of raw move_object.
- For chairs/sofas, "put on top of" means the seat/support surface, not the chair back.
- For "beside" or "against the wall" requests, prefer place_near/place_against_wall.
- Large furniture should rest on the floor by default. Rugs must rest on the floor.
- Keep scale values reasonable; the execution layer will clamp extreme scales.
- If the user asks to adjust the view, composition, camera position, centering, or subject size in the render, prefer adjust_camera_from_render.
Do not generate Python code. Use only the provided function calls.
When the task is complete, reply exactly: All done.
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
                "description": "Get current Blender/Infinigen scene information and object list.",
                "parameters": {},
                "required": [],
            },
            {
                "name": "rebuild_scene_index",
                "description": "Rebuild the semantic index for the current scene, including asset categories, dimensions, locations, materials, and spatial relations.",
                "parameters": {
                    "save_path": {"type": "string", "description": "Optional path for saving the index JSON."}
                },
                "required": [],
            },
            {
                "name": "query_objects",
                "description": "Query scene assets by natural language, category, object name, or object_id.",
                "parameters": {
                    "text": {"type": "string", "description": "Query text, for example: table beside the bed, desk lamp, desk."},
                    "category": {
                        "type": "string",
                        "description": "Optional category: bed, desk, table, side_table, lamp, chair, sofa, cabinet, bookcase, rug, plant, apple, blackberry, green_coconut, hairy_coconut, durian, pineapple, starfruit, strawberry, compositional_fruit, wall, floor, room.",
                    },
                },
                "required": [],
            },
            {
                "name": "open_blend",
                "description": "Open a .blend scene file.",
                "parameters": {
                    "path": {"type": "string", "description": "Absolute path to the .blend file to open."}
                },
                "required": ["path"],
            },
            {
                "name": "save_blend",
                "description": "Save the current .blend file.",
                "parameters": {
                    "path": {"type": "string", "description": "Optional save path. If omitted, save the current file."}
                },
                "required": [],
            },
            {
                "name": "add_infinigen_asset",
                "description": "Add furniture or an object to the current scene through an Infinigen factory.",
                "parameters": {
                    "category_or_factory": {
                        "type": "string",
                        "description": "Asset category or Infinigen factory, for example: bed, bed_frame, mattress, pillow, desk, side_table, chair, bar_chair, office_chair, sofa, armchair, beverage_fridge, dishwasher, microwave, oven, tv, monitor, apple, strawberry.",
                    },
                    "seed": {"type": "integer", "description": "Optional random seed."},
                    "location": {"type": "array", "description": "Optional placement location [x, y, z]."},
                    "scale": {"type": "number", "description": "Optional uniform scale. Fruit already has small defaults, for example apple around 0.12 and strawberry around 0.15; do not pass 1.0 unless the user explicitly asks for a large fruit."},
                },
                "required": ["category_or_factory"],
            },
            {
                "name": "edit_generated_asset",
                "description": "Edit a generated asset's generation script, regenerate it, and replace the old scene asset while preserving position and size alignment. Prefer this when the user starts with \\editing.",
                "parameters": {
                    "target": {"type": "string", "description": "Target object, for example: desk or asset_xxx."},
                    "prompt": {"type": "string", "description": "Complete edit instruction, for example: make the desk in the scene green."},
                    "color": {
                        "type": "string",
                        "description": "Optional color/material: red, blue, green, white, black, wood, ceramic, glass, marble, tile, advanced_tiles, metal, aluminum, brushed_metal, plastic, black_plastic, rubber, or #RRGGBB.",
                    },
                    "preserve_size": {"type": "boolean", "description": "Whether to preserve the original asset size. Defaults to true."},
                },
                "required": ["target", "prompt"],
            },
            {
                "name": "move_object",
                "description": "Move an object in a direction. target may be an object_id, object name, category, or natural-language description.",
                "parameters": {
                    "target": {"type": "string", "description": "Target object, for example: bed, desk, or asset_xxx."},
                    "direction": {
                        "type": "string",
                        "description": "Direction: left, right, front, back, up, down.",
                        "enum": ["left", "right", "front", "back", "up", "down"],
                    },
                    "distance": {"type": "number", "description": "Move distance in meters."},
                },
                "required": ["target", "direction", "distance"],
            },
            {
                "name": "scale_object",
                "description": "Scale an object. factor greater than 1 enlarges it; factor less than 1 shrinks it.",
                "parameters": {
                    "target": {"type": "string", "description": "Target object."},
                    "factor": {"type": "number", "description": "Scale factor, for example 1.2 or 0.8."},
                },
                "required": ["target", "factor"],
            },
            {
                "name": "rotate_object",
                "description": "Rotate an object.",
                "parameters": {
                    "target": {"type": "string", "description": "Target object."},
                    "axis": {"type": "string", "description": "Rotation axis: x, y, z.", "enum": ["x", "y", "z"]},
                    "angle_degrees": {"type": "number", "description": "Rotation angle in degrees."},
                },
                "required": ["target", "axis", "angle_degrees"],
            },
            {
                "name": "place_on",
                "description": "Place source on the center of target's supportable top surface, such as a tabletop or chair seat.",
                "parameters": {
                    "source": {"type": "string", "description": "Object to move."},
                    "target": {"type": "string", "description": "Support object."},
                },
                "required": ["source", "target"],
            },
            {
                "name": "place_near",
                "description": "Place source beside target.",
                "parameters": {
                    "source": {"type": "string", "description": "Object to move."},
                    "target": {"type": "string", "description": "Reference object."},
                    "side": {
                        "type": "string",
                        "description": "Relative side: left, right, front, back.",
                        "enum": ["left", "right", "front", "back"],
                    },
                    "gap": {"type": "number", "description": "Gap in meters."},
                },
                "required": ["source", "target"],
            },
            {
                "name": "place_against_wall",
                "description": "Place the target object near the nearest wall or a specified wall.",
                "parameters": {
                    "target": {"type": "string", "description": "Target object."},
                    "wall": {"type": "string", "description": "Optional wall object."},
                    "gap": {"type": "number", "description": "Distance from the wall in meters."},
                },
                "required": ["target"],
            },
            {
                "name": "apply_physics_rules",
                "description": "Apply fixed physical rules to the scene or a target object: prevent floating, snap to ground, and provide basic collision hints after scaling/placement.",
                "parameters": {
                    "target": {"type": "string", "description": "Target object. If omitted, check the whole scene."}
                },
                "required": [],
            },
            {
                "name": "set_material",
                "description": "Change an object's material color.",
                "parameters": {
                    "target": {"type": "string", "description": "Target object."},
                    "object_name": {"type": "string", "description": "Legacy-compatible field for the target object name."},
                    "material_name": {"type": "string", "description": "Optional material name."},
                    "color": {
                        "type": "string",
                        "description": "Color/material: red, blue, green, white, black, wood, ceramic, glass, marble, tile, advanced_tiles, metal, aluminum, brushed_metal, plastic, black_plastic, rubber, or #RRGGBB.",
                    },
                },
                "required": [],
            },
            {
                "name": "delete_object",
                "description": "Delete an object.",
                "parameters": {
                    "target": {"type": "string", "description": "Target object."},
                    "name": {"type": "string", "description": "Legacy-compatible field for the target object name."},
                },
                "required": [],
            },
            {
                "name": "render_scene",
                "description": "Render the current scene and return the preview path. By default, camera view is checked first and adjusted when subjects are too far away or non-structural objects are not visible.",
                "parameters": {
                    "output_path": {"type": "string", "description": "Optional output image path."},
                    "resolution_x": {"type": "integer", "description": "Optional width."},
                    "resolution_y": {"type": "integer", "description": "Optional height."},
                    "auto_adjust_camera": {"type": "boolean", "description": "Whether to check and adjust the camera before rendering. Defaults to true."},
                    "camera_target": {"type": "string", "description": "Optional target object for composition checking. If omitted, use all non-structural assets."},
                    "camera_target_fill": {"type": "number", "description": "Target subject fill ratio. Defaults to 0.72."},
                },
                "required": [],
            },
            {
                "name": "adjust_camera_from_render",
                "description": "Camera agent: render a transparent mask, analyze target/scene pixel position and fill ratio, move/dolly the Blender camera, then render a new preview. Use when the user asks to adjust view, center an object, improve composition, or resize the rendered subject.",
                "parameters": {
                    "target": {"type": "string", "description": "Target object/category/natural-language description for composition. If omitted, use non-structural scene assets."},
                    "output_path": {"type": "string", "description": "Optional output path for the adjusted preview image."},
                    "target_fill": {"type": "number", "description": "Target subject fill ratio, 0.2-0.95. Defaults to 0.72."},
                    "max_iterations": {"type": "integer", "description": "Number of camera adjustment iterations based on renders. Defaults to 3."},
                    "tolerance": {"type": "number", "description": "Centering and scale tolerance. Defaults to 0.06."},
                    "resolution_x": {"type": "integer", "description": "Mask render width for analysis. Defaults to 768."},
                    "resolution_y": {"type": "integer", "description": "Mask render height for analysis. Defaults to 432."},
                    "final_resolution_x": {"type": "integer", "description": "Final preview width. Defaults to 1280."},
                    "final_resolution_y": {"type": "integer", "description": "Final preview height. Defaults to 720."},
                },
                "required": [],
            },
            {
                "name": "adjust_existing_light",
                "description": "Move and strengthen an existing Blender Light so prompt-relevant objects are visible. Does not add new lights. Use only when the render is too dark, objects are hard to see, the verifier asks to adjust an existing Light, or the user asks to adjust lighting.",
                "parameters": {
                    "target": {"type": "string", "description": "Target object/category/natural-language description to illuminate. If omitted, use all non-structural assets."},
                    "light": {"type": "string", "description": "Optional existing Light name. If omitted, use an existing scene Light."},
                    "min_energy": {"type": "number", "description": "Minimum energy for the existing Light. Defaults to 900."},
                    "height": {"type": "number", "description": "Optional height above the target center."},
                    "distance": {"type": "number", "description": "Optional horizontal distance from the target center along the camera direction."},
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
                    text_content += ", "
                text_content += f"image URLs: {', '.join(image_urls)}"
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
                f"Blocked an attempt to add an asset not explicitly requested in the original instruction: {category}. "
                "The Agent will strictly follow the user instruction and will not enrich the scene proactively."
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
            if user_text and "Continue completing the original user instruction" not in user_text:
                self.current_user_request_text = user_text
            self.add_message("user", user_message)

        if not hasattr(self.llm, "chat_stream"):
            raise NotImplementedError("The current LLM does not support streaming responses")

        self.current_run_id = uuid.uuid4().hex
        self._last_cancel_check = 0.0
        self._set_agent_status("running", "LLM is generating a response", operation="llm")
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
                self.add_message("assistant", f"I will run tool: {function_call['name']}")

            if function_call:
                function_result = self._execute_function(function_call)
                self.add_message(
                    "user",
                    f"Execution result for tool {function_call['name']}: {json.dumps(function_result, ensure_ascii=False)}",
                )
                yield {
                    "content": None,
                    "function_call": function_call,
                    "function_result": function_result,
                }
        except GeneratorExit:
            self._set_agent_status("cancelled", "The UI stopped the Agent run")
            raise
        except RuntimeError as exc:
            if str(exc) != "Agent run cancelled from Blender":
                raise
            self._set_agent_status("cancelled", "Blender requested the Agent run to stop")
            yield {
                "content": "Run stopped.",
                "function_call": None,
                "function_result": {"status": "cancelled", "message": "Blender requested the Agent run to stop"},
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
                return {"status": "error", "message": "Blender is not connected. Please connect the Blender add-on service first."}
            if not hasattr(self.blender_client, function_name):
                return {"status": "error", "message": f"Tool {function_name} does not exist"}

            blocked = self._validate_function_call_against_request(function_call)
            if blocked is not None:
                return blocked

            self._raise_if_blender_cancelled(force=True)
            self._set_agent_status("running", f"Running in Blender: {function_name}", operation=function_name)
            func = getattr(self.blender_client, function_name)
            logger.info("Executing function: %s, args: %s", function_name, arguments)
            result = func(**arguments)
            logger.info("Function result: %s", result)
            self._raise_if_blender_cancelled(force=True)
            return result
        except RuntimeError as exc:
            if str(exc) == "Agent run cancelled from Blender":
                raise
            logger.error("Error executing function %s: %s", function_call.get("name", "Unknown"), exc)
            return {"status": "error", "message": f"Error executing function: {exc}"}
        except Exception as exc:
            logger.error("Error executing function %s: %s", function_call.get("name", "Unknown"), exc)
            return {"status": "error", "message": f"Error executing function: {exc}"}

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
            logger.debug("Failed to sync Agent status to Blender: %s", exc)

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
            logger.debug("Failed to read Blender Agent status: %s", exc)
            return
        result = status.get("result", status)
        if isinstance(result, dict) and result.get("cancel_requested"):
            raise RuntimeError("Agent run cancelled from Blender")

    def update_blender_client(self, blender_client: BlenderClient):
        self.blender_client = blender_client
        logger.info("Updated the Agent Blender client reference")
