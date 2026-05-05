"""Natural-language to tool-plan layer.

This file ships with a deterministic Chinese/English rule planner so the demo can
run offline. It is deliberately separated from execution so an LLM planner can
replace it later while keeping the same action schema.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .asset_registry import resolve_asset


@dataclass(frozen=True)
class Action:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


class RulePlanner:
    SPATIAL_EDIT_ACTIONS = {
        "add_infinigen_asset",
        "edit_generated_asset",
        "move_object",
        "scale_object",
        "rotate_object",
        "place_on",
        "place_near",
        "place_against_wall",
    }

    def plan(self, text: str) -> list[Action]:
        raw = text.strip()
        lowered = raw.lower()
        actions: list[Action] = []

        editing = self._plan_editing(raw)
        if editing:
            return self._finalize_actions([editing])

        blend_path = self._find_blend_path(raw)
        if blend_path:
            return [Action("open_blend", {"path": blend_path}), Action("rebuild_scene_index")]

        if any(key in lowered for key in ("help", "帮助", "怎么用")):
            return [Action("help")]

        if any(key in lowered for key in ("列出", "查看", "有哪些", "scene info", "objects", "物体")):
            return [Action("get_scene_info"), Action("rebuild_scene_index")]

        if any(key in lowered for key in ("相机", "摄像机", "视角", "构图", "居中", "camera", "framing", "frame")):
            spec = resolve_asset(raw)
            target = self._extract_target(raw) or (spec.category if spec else None)
            return [Action("adjust_camera_from_render", {"target": target}), Action("rebuild_scene_index")]

        if any(key in lowered for key in ("渲染", "预览", "render", "preview")):
            return [Action("render_scene")]

        if any(key in lowered for key in ("保存", "save")):
            return [Action("save_blend"), Action("rebuild_scene_index")]

        add_action = self._plan_add(raw)
        if add_action:
            actions.extend(add_action)

        placement = self._plan_place_on(raw)
        if placement:
            actions.append(placement)

        near = self._plan_place_near(raw)
        if near:
            actions.append(near)

        wall = self._plan_against_wall(raw)
        if wall:
            actions.append(wall)

        move = self._plan_move(raw)
        if move:
            actions.append(move)

        scale = self._plan_scale(raw)
        if scale:
            actions.append(scale)

        rotate = self._plan_rotate(raw)
        if rotate:
            actions.append(rotate)

        material = self._plan_material(raw)
        if material:
            actions.append(material)

        delete = self._plan_delete(raw)
        if delete:
            actions.append(delete)

        if actions:
            return self._finalize_actions(actions)

        return [Action("query_objects", {"text": raw})]

    def _finalize_actions(self, actions: list[Action]) -> list[Action]:
        finalized: list[Action] = []
        for action in actions:
            finalized.append(action)
            physics = self._physics_action_for(action)
            if physics:
                finalized.append(physics)
        finalized.append(Action("rebuild_scene_index"))
        return finalized

    def _physics_action_for(self, action: Action) -> Action | None:
        if action.name not in self.SPATIAL_EDIT_ACTIONS:
            return None
        if action.name in {"add_infinigen_asset"}:
            return None
        if action.name in {"place_on", "place_near"}:
            target = action.args.get("source")
        else:
            target = action.args.get("target")
        return Action("apply_physics_rules", {"target": target}) if target else None

    def _plan_editing(self, text: str) -> Action | None:
        lowered = text.lower().strip()
        prefixes = ("\\editing", "/editing", "editing", "编辑生成", "编辑物体")
        if not lowered.startswith(prefixes):
            return None
        prompt = text
        for prefix in prefixes:
            if lowered.startswith(prefix):
                prompt = text[len(prefix) :].strip()
                break
        target = self._extract_target(prompt) or self._extract_edit_target(prompt) or prompt
        color = self._extract_color(prompt)
        args: dict[str, Any] = {"target": target, "prompt": prompt or text, "preserve_size": True}
        if color:
            args["color"] = color
        return Action("edit_generated_asset", args)

    def _plan_add(self, text: str) -> list[Action] | None:
        if not any(key in text.lower() for key in ("添加", "加一", "加个", "放一个", "add", "create")):
            return None
        spec = resolve_asset(text)
        if spec is None:
            return None
        return [
            Action(
                "add_infinigen_asset",
                {"category_or_factory": spec.category, "scale": spec.default_scale},
            )
        ]

    def _plan_move(self, text: str) -> Action | None:
        if not any(key in text.lower() for key in ("移动", "移到", "往", "move")):
            return None
        target = self._extract_target(text) or text
        direction = "right"
        direction_map = {
            "左": "left",
            "右": "right",
            "前": "front",
            "后": "back",
            "上": "up",
            "下": "down",
            "left": "left",
            "right": "right",
            "front": "front",
            "back": "back",
            "up": "up",
            "down": "down",
        }
        for key, value in direction_map.items():
            if key in text.lower():
                direction = value
                break
        distance = self._extract_number(text, default=0.3)
        return Action("move_object", {"target": target, "direction": direction, "distance": distance})

    def _plan_scale(self, text: str) -> Action | None:
        lowered = text.lower()
        if not any(key in lowered for key in ("放大", "缩小", "scale", "变大", "变小")):
            return None
        target = self._extract_target(text) or text
        number = self._extract_number(text, default=1.2)
        if any(key in lowered for key in ("缩小", "变小", "smaller", "down")):
            factor = number if number < 1 else 1 / number if number > 1.01 else 0.8
        elif "scale" in lowered and number != 1.2:
            factor = number
        else:
            factor = number if number > 1.01 else 1.2
        return Action("scale_object", {"target": target, "factor": factor})

    def _plan_rotate(self, text: str) -> Action | None:
        lowered = text.lower()
        if not any(key in lowered for key in ("旋转", "rotate")):
            return None
        target = self._extract_target(text) or text
        angle = self._extract_number(text, default=90.0)
        return Action("rotate_object", {"target": target, "axis": "z", "angle_degrees": angle})

    def _plan_delete(self, text: str) -> Action | None:
        lowered = text.lower()
        if not any(key in lowered for key in ("删除", "移除", "delete", "remove")):
            return None
        return Action("delete_object", {"target": self._extract_target(text) or text})

    def _plan_material(self, text: str) -> Action | None:
        lowered = text.lower()
        if not any(key in lowered for key in ("颜色", "材质", "变成", "color", "material")):
            return None
        colors = {
            "红": "red",
            "蓝": "blue",
            "绿": "green",
            "白": "white",
            "黑": "black",
            "木": "wood",
            "red": "red",
            "blue": "blue",
            "green": "green",
            "white": "white",
            "black": "black",
            "wood": "wood",
        }
        color = None
        for key, value in colors.items():
            if key in lowered:
                color = value
                break
        return Action("set_material", {"target": self._extract_target(text) or text, "color": color})

    def _extract_color(self, text: str) -> str | None:
        colors = {
            "红": "red",
            "红色": "red",
            "蓝": "blue",
            "蓝色": "blue",
            "绿": "green",
            "绿色": "green",
            "白": "white",
            "白色": "white",
            "黑": "black",
            "黑色": "black",
            "木": "wood",
            "木色": "wood",
            "red": "red",
            "blue": "blue",
            "green": "green",
            "white": "white",
            "black": "black",
            "wood": "wood",
        }
        lowered = text.lower()
        hex_match = re.search(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?", text)
        if hex_match:
            return hex_match.group(0)
        for key, value in colors.items():
            if key in lowered:
                return value
        return None

    def _extract_edit_target(self, text: str) -> str | None:
        patterns = [
            r"(?:场景中的|场景里(?:的)?|把|将)?\s*(?P<target>[^，。,\.]+?)(?:改成|变成|换成|编辑成|edit|change)",
            r"(?:edit|change)\s+(?P<target>[a-zA-Z0-9_\- .]+?)\s+(?:to|into)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                target = match.group("target").strip()
                target = re.sub(r"^(场景中的|场景里的|场景里|的)", "", target).strip()
                if target:
                    spec = resolve_asset(target)
                    return spec.category if spec else target
        spec = resolve_asset(text)
        return spec.category if spec else None

    def _plan_place_on(self, text: str) -> Action | None:
        lowered = text.lower()
        if not any(key in lowered for key in ("放到", "放在", "on top", "onto")):
            return None
        if not any(key in lowered for key in ("上", "桌", "table", "desk", "床头柜")):
            return None
        source = self._extract_source_before_place(text) or "lamp"
        target = self._extract_support_after_place(text) or "desk"
        return Action("place_on", {"source": source, "target": target})

    def _plan_place_near(self, text: str) -> Action | None:
        lowered = text.lower()
        if not any(key in lowered for key in ("旁边", "附近", "near", "beside")):
            return None
        source = self._extract_target(text) or text
        target = "bed" if any(key in lowered for key in ("床", "bed")) else "desk"
        side = "right" if any(key in lowered for key in ("右", "right")) else "left"
        return Action("place_near", {"source": source, "target": target, "side": side, "gap": 0.25})

    def _plan_against_wall(self, text: str) -> Action | None:
        lowered = text.lower()
        if not any(key in lowered for key in ("靠墙", "against wall", "贴墙")):
            return None
        return Action("place_against_wall", {"target": self._extract_target(text) or text})

    def _extract_target(self, text: str) -> str | None:
        patterns = [
            r"[把将]\s*(?P<target>[^，。,\.]+?)(往|向|移动|放大|缩小|旋转|删除|变成|改成|靠墙|放到|放在)",
            r"(move|scale|rotate|delete|remove)\s+(?P<target>[a-zA-Z0-9_\- .]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group("target").strip()
        spec = resolve_asset(text)
        return spec.category if spec else None

    def _extract_source_before_place(self, text: str) -> str | None:
        match = re.search(r"[把将]\s*(?P<source>[^，。,\.]+?)放[到在]", text)
        if match:
            return match.group("source").strip()
        spec = resolve_asset(text)
        return spec.category if spec else None

    def _extract_support_after_place(self, text: str) -> str | None:
        alias_values = {
            "桌": "desk",
            "桌子": "desk",
            "书桌": "desk",
            "餐桌": "table",
            "床头柜": "side_table",
            "椅": "chair",
            "椅子": "chair",
            "座椅": "chair",
            "沙发": "sofa",
            "床": "bed",
            "table": "table",
            "desk": "desk",
            "nightstand": "side_table",
            "chair": "chair",
            "sofa": "sofa",
            "bed": "bed",
        }
        match = re.search(r"放[到在]\s*(?P<support>[^，。,\.]+?)上", text, re.IGNORECASE)
        if match:
            support = match.group("support").strip()
            lowered_support = support.lower()
            for key in sorted(alias_values, key=len, reverse=True):
                if key in lowered_support:
                    return alias_values[key]
            spec = resolve_asset(support)
            if spec:
                return spec.category

        support_aliases = {
            "桌": "desk",
            "桌子": "desk",
            "书桌": "desk",
            "餐桌": "table",
            "床头柜": "side_table",
            "椅": "chair",
            "椅子": "chair",
            "座椅": "chair",
            "沙发": "sofa",
            "床": "bed",
            "table": "table",
            "desk": "desk",
            "nightstand": "side_table",
            "chair": "chair",
            "sofa": "sofa",
            "bed": "bed",
        }
        for key, value in sorted(support_aliases.items(), key=lambda item: len(item[0]), reverse=True):
            if key in text.lower():
                return value
        return None

    def _extract_number(self, text: str, default: float) -> float:
        match = re.search(r"(?P<number>\d+(?:\.\d+)?)", text)
        if not match:
            return default
        number = float(match.group("number"))
        if "厘米" in text or "cm" in text.lower():
            return number / 100
        return number

    def _find_blend_path(self, text: str) -> str | None:
        match = re.search(r"(?P<path>(?:/|\.)[^\s]+\.blend)", text)
        return match.group("path") if match else None


def make_planner() -> Any:
    import os

    if os.getenv("GOSIM_PLANNER", "").lower() == "llm":
        from .llm_planner import OpenAICompatiblePlanner

        return OpenAICompatiblePlanner()
    return RulePlanner()
