"""Visual verifier agent for render-driven Blender editing loops."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from ..llm.base import BaseLLM


logger = logging.getLogger(__name__)


VISUAL_VERIFIER_SYSTEM_PROMPT = """You are the visual verifier for a Blender scene.
You will see one render result, the user's original goal, and current scene information. Your job is not to beautify the image; your job is to verify whether the generated result matches the user's prompt and follows physical common sense and everyday-use plausibility.

Return JSON only. Do not return Markdown:
{
  "done": true | false,
  "reason": "One sentence explaining the judgment.",
  "instruction": "If done=false, write a specific adjustment instruction for the Blender code generator in English. If done=true, leave this empty."
}

Core responsibilities:
- Check only whether the content requested by the user's prompt is present, whether requested attributes match, and whether requested spatial relations are correct.
- This is an incremental scene-editing workflow. The current scene may already contain objects not mentioned in the current prompt. Do not treat those existing objects as errors, and do not ask to delete, hide, or move them, unless the current prompt explicitly asks to delete, replace, or clear the scene.
- Only flag an unrequested object when it was clearly added by this edit and it interferes with the prompt goal or violates physical common sense. If you cannot tell whether it was newly added, ignore it.
- Check physical common sense and everyday-use plausibility: support contact, floating, interpenetration, overlap/collision, relative scale, placement orientation, and normal human/object usage.
- Judge size by relative scale and context, not fixed absolute thresholds. For example, judge whether apples and strawberries look like realistic tabletop objects relative to the table and each other, instead of outputting fixed meter values.
- If the user asks for a chair beside a table, the chair should be at the table edge with the seat/front facing the table in a usable way. Do not check only distance.
- When a chair is near a table, check whether it intersects the tabletop, table legs, or other objects. The chair should face the table from a usable side, not be forced in from a side blocked by table legs.
- If the render is too dark to recognize prompt-related objects, or the camera is too far/cropped to confirm all object relations, you may return done=false, but the fix may only adjust an existing Light or existing Camera.

Hard prohibitions:
- Do not return done=false because the subjective composition is not good enough, the material is not clear enough, or the render is not pretty enough, unless the user's prompt explicitly asks to adjust camera, composition, material, or render appearance.
- Do not add new lights. If the scene is too dark, only ask to move or adjust the position/energy of an existing Light so prompt-related objects are recognizable.
- If the camera is too far, the subject is too small, or objects are cropped so the prompt cannot be verified, you may ask to adjust the existing Camera. Do not adjust the camera just to make the image prettier.
- Do not ask to add objects that are not in the prompt, and do not treat unrequested objects as improvements that make the scene more natural.
- Do not ask to delete, hide, or move existing objects not mentioned in the prompt.
- For example, if the user only says "add a stool" and there is already an apple in the scene, only check whether the stool exists and is placed plausibly; do not label the apple as an unrequested object.
- Do not output beautification suggestions such as "add a fill light", "occupies xx% of the image", or "ensure the material is clearly visible" unless that is part of the user's original goal.

Return rules:
- If the prompt-required objects, attributes, spatial relations, relative scale, support/collision behavior, and everyday-use plausibility are basically correct, return done=true.
- Return done=false when a prompt-required object is missing, object relations are wrong, there is obvious overlap/interpenetration/floating, size proportions violate everyday common sense, or chair/furniture orientation is not usable.
- When adjustment is needed, instruction must describe only concrete fixes for prompt consistency, physical common sense, everyday-use plausibility, or verifiability.
- For example: "Move the apple slightly to the right of the strawberry, avoid overlap, and keep both objects on the tabletop";
  "Rotate and move the chair so the seat faces the table from a side not blocked by table legs and does not intersect the table";
  "Move the existing Light to the front-above area of the tabletop; do not add a new light";
  "Adjust the existing Camera so all prompt-related objects are recognizable and not cropped."
"""


OUT_OF_SCOPE_VERIFIER_KEYWORDS = (
    "光照",
    "灯光",
    "主光源",
    "环境光",
    "补光",
    "明亮",
    "变亮",
    "曝光",
    "阴影",
    "相机",
    "镜头",
    "视角",
    "构图",
    "画面",
    "拉近",
    "拉远",
    "占据",
    "面积",
    "清晰",
    "可见",
    "渲染效果",
    "camera",
    "lighting",
    "light",
    "framing",
)

VISIBILITY_REPAIR_KEYWORDS = (
    "太暗",
    "过暗",
    "看不清",
    "无法辨认",
    "难以辨认",
    "不可辨认",
    "主体太小",
    "太远",
    "过远",
    "被裁切",
    "裁切",
    "看不到",
    "不可见",
    "所有物体",
    "prompt 相关物体",
    "已有 light",
    "现有 light",
    "已有灯",
    "现有灯",
    "已有 camera",
    "现有 camera",
    "too dark",
    "too dim",
    "underexposed",
    "hard to see",
    "difficult to see",
    "cannot see",
    "can't see",
    "not visible",
    "cannot recognize",
    "can't recognize",
    "cannot identify",
    "can't identify",
    "cannot confirm",
    "can't confirm",
    "cannot verify",
    "can't verify",
    "unable to confirm",
    "unable to verify",
    "hard to confirm",
    "difficult to confirm",
    "cropped",
    "too far",
)

ADD_LIGHT_KEYWORDS = (
    "添加光",
    "添加灯",
    "添加补光",
    "新增光",
    "新增灯",
    "新增补光",
    "额外的光",
    "额外的灯",
    "额外补光",
    "add light",
    "add a light",
    "new light",
    "extra light",
)

PROMPT_ALLOWED_VISUAL_KEYWORDS = (
    "光照",
    "灯光",
    "亮",
    "暗",
    "相机",
    "镜头",
    "视角",
    "构图",
    "画面",
    "渲染",
    "材质",
    "颜色",
    "清晰",
    "可见",
    "camera",
    "lighting",
    "light",
    "framing",
    "render",
    "material",
    "color",
)

OBJECTIVE_VERIFIER_KEYWORDS = (
    "缺少",
    "没有",
    "未生成",
    "多余",
    "未要求",
    "不一致",
    "不符合",
    "错误",
    "不是",
    "位置",
    "放在",
    "放到",
    "桌面",
    "坐垫",
    "旁边",
    "靠近",
    "支撑",
    "接触",
    "悬浮",
    "漂浮",
    "穿模",
    "重叠",
    "碰撞",
    "相交",
    "大小",
    "尺寸",
    "比例",
    "过大",
    "太大",
    "过小",
    "太小",
    "朝向",
    "面向",
    "方向",
    "旋转",
    "角度",
    "生活习惯",
    "物理",
    "常识",
    "数量",
)

STRONG_OBJECTIVE_VERIFIER_KEYWORDS = (
    "缺少",
    "没有",
    "未生成",
    "多余",
    "未要求",
    "不一致",
    "不符合",
    "错误",
    "不是",
    "位置",
    "放在",
    "放到",
    "桌面",
    "坐垫",
    "旁边",
    "靠近",
    "支撑",
    "接触",
    "悬浮",
    "漂浮",
    "穿模",
    "重叠",
    "重合",
    "碰撞",
    "相交",
    "过大",
    "太大",
    "过小",
    "太小",
    "朝向",
    "面向",
    "方向",
    "旋转",
    "角度",
    "生活习惯",
    "物理",
    "常识",
    "数量",
)

VISUAL_ONLY_PHRASES = (
    "画面比例",
    "画面占比",
    "占据画面",
    "占画面",
    "画面约",
    "画面面积",
    "构图比例",
    "主体太小",
    "主体太大",
)

USER_DELETE_REQUEST_KEYWORDS = (
    "删除",
    "移除",
    "去掉",
    "去除",
    "清除",
    "删掉",
    "拿掉",
    "不要",
    "delete",
    "remove",
    "clear",
)

EXTRA_OBJECT_CLAIM_KEYWORDS = (
    "未要求",
    "没要求",
    "没有要求",
    "多余",
    "额外",
    "不需要",
    "不应出现",
    "不该出现",
    "无关物体",
    "extra",
    "unrequested",
    "unwanted",
    "not requested",
)

DELETE_OBJECT_ACTION_KEYWORDS = (
    "删除",
    "移除",
    "去掉",
    "去除",
    "清除",
    "删掉",
    "拿掉",
    "隐藏",
    "delete",
    "remove",
    "clear",
    "hide",
)

DELETE_ACTION_PATTERN = r"删除|移除|去掉|去除|清除|删掉|拿掉|隐藏"
CLAUSE_SPLIT_RE = re.compile(
    rf"(?:[。；;！!\n]+|，且|,?\s+and\s+|且|并且|同时|另外|此外|"
    rf"[，,]\s*(?={DELETE_ACTION_PATTERN})|并(?={DELETE_ACTION_PATTERN}))",
    re.IGNORECASE,
)


@dataclass
class VisualVerifierResult:
    done: bool
    reason: str
    instruction: str = ""


class VisualVerifierAgent:
    """Checks render images and emits text instructions for the code generator."""

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    def verify(self, user_goal: str, render_path: str, scene_text: str) -> VisualVerifierResult:
        if not render_path:
            return VisualVerifierResult(
                done=True,
                reason="No render result is available, so Visual Verifier was skipped.",
            )

        verifier_messages = [
            {"role": "system", "content": VISUAL_VERIFIER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Original user goal: {user_goal or 'Not provided'}\n\n"
                            f"Current scene information:\n{scene_text or 'Not available'}\n\n"
                            "Check whether this render already satisfies the goal."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": render_path}},
                ],
            },
        ]

        try:
            response = self.llm.chat(
                messages=verifier_messages,
                functions=[],
                temperature=0.2,
                max_tokens=512,
            )
        except Exception as exc:
            logger.error("Visual Verifier call failed: %s", exc)
            return VisualVerifierResult(done=True, reason=f"Visual Verifier call failed: {exc}")

        content = (response or {}).get("content") or ""
        verdict = self._extract_json_object(content)
        if not verdict:
            lowered = content.lower()
            done = any(key in lowered for key in ("done", "ok", "acceptable", "可接受", "差不多", "完成"))
            return VisualVerifierResult(
                done=done,
                reason=content.strip() or "Verifier did not return a structured result.",
                instruction="" if done else content.strip(),
            )

        instruction = str(verdict.get("instruction") or "").strip()
        raw_done = verdict.get("done")
        done = self._coerce_done(raw_done) if raw_done is not None else not instruction
        result = VisualVerifierResult(
            done=done,
            reason=str(verdict.get("reason") or "").strip(),
            instruction="" if done else instruction,
        )
        return self._apply_scope_guard(user_goal, result)

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any]:
        if not text:
            return {}
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            if stripped.lower().startswith("json"):
                stripped = stripped[4:].strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(stripped[start : end + 1])
                except json.JSONDecodeError:
                    return {}
        return {}

    @staticmethod
    def _coerce_done(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "yes", "y", "1", "done", "ok", "完成", "可接受"}
        return bool(value)

    @staticmethod
    def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
        lowered = text.lower()
        return any(keyword.lower() in lowered for keyword in keywords)

    @classmethod
    def _strip_unrequested_object_clauses(cls, text: str) -> str:
        if not text:
            return text

        clauses = [clause.strip(" ，,。；;！!\n") for clause in CLAUSE_SPLIT_RE.split(text)]
        kept = [
            clause
            for clause in clauses
            if clause
            and not (
                cls._contains_any(clause, EXTRA_OBJECT_CLAIM_KEYWORDS)
                or (
                    cls._contains_any(clause, DELETE_OBJECT_ACTION_KEYWORDS)
                    and "不要" not in clause
                    and not cls._contains_any(clause, OBJECTIVE_VERIFIER_KEYWORDS)
                )
            )
        ]
        return "；".join(kept).strip()

    @classmethod
    def _has_visibility_repair_issue(cls, result: VisualVerifierResult) -> bool:
        combined = f"{result.reason or ''}\n{result.instruction or ''}"
        return cls._contains_any(combined, VISIBILITY_REPAIR_KEYWORDS)

    @classmethod
    def _visibility_repair_instruction(cls, result: VisualVerifierResult) -> str:
        instruction = result.instruction or ""
        combined = f"{result.reason or ''}\n{instruction}"
        lowered = combined.lower()
        if any(keyword in lowered for keyword in ("camera", "相机", "镜头", "cropped", "too far", "裁切", "太远", "过远")):
            return "Adjust the existing Camera so all prompt-related objects are recognizable and not cropped."
        return "Move or adjust an existing Light in the scene so prompt-related objects and requested attributes are recognizable; do not add a new light."

    @classmethod
    def _apply_scope_guard(
        cls,
        user_goal: str,
        result: VisualVerifierResult,
    ) -> VisualVerifierResult:
        if result.done and cls._has_visibility_repair_issue(result):
            return VisualVerifierResult(
                done=False,
                reason=result.reason or "The render is not recognizable enough to verify the prompt.",
                instruction=cls._visibility_repair_instruction(result),
            )

        if result.done or not result.instruction:
            return result

        user_requests_delete = cls._contains_any(user_goal or "", USER_DELETE_REQUEST_KEYWORDS)
        if not user_requests_delete:
            sanitized_reason = cls._strip_unrequested_object_clauses(result.reason or "")
            sanitized_instruction = cls._strip_unrequested_object_clauses(result.instruction or "")
            if (
                sanitized_reason != (result.reason or "")
                or sanitized_instruction != (result.instruction or "")
            ):
                if not sanitized_instruction:
                    return VisualVerifierResult(
                        done=True,
                        reason=(
                            f"Ignored Visual Verifier advice that asks to handle existing objects not mentioned in the prompt: "
                            f"{result.reason or result.instruction}"
                        ),
                        instruction="",
                    )
                result = VisualVerifierResult(
                    done=False,
                    reason=sanitized_reason or "Kept only adjustment advice related to the current prompt.",
                    instruction=sanitized_instruction,
                )

        user_allows_visual_edits = cls._contains_any(
            user_goal or "",
            PROMPT_ALLOWED_VISUAL_KEYWORDS,
        )
        if user_allows_visual_edits:
            return result

        instruction = result.instruction
        reason = result.reason or ""
        combined = f"{reason}\n{instruction}"
        if cls._contains_any(combined, ADD_LIGHT_KEYWORDS):
            return VisualVerifierResult(
                done=False,
                reason=reason or "The render is too dark, but lights not requested by the prompt must not be added.",
                instruction="Do not add a new light; only move or adjust an existing Light in the scene so prompt-related objects are recognizable.",
            )

        if cls._has_visibility_repair_issue(result):
            return result

        has_out_of_scope_terms = cls._contains_any(instruction, OUT_OF_SCOPE_VERIFIER_KEYWORDS)
        has_objective_terms = cls._contains_any(instruction, OBJECTIVE_VERIFIER_KEYWORDS)
        has_strong_objective_terms = cls._contains_any(
            instruction,
            STRONG_OBJECTIVE_VERIFIER_KEYWORDS,
        )
        looks_visual_only = cls._contains_any(instruction, VISUAL_ONLY_PHRASES)
        if has_out_of_scope_terms and (
            not has_objective_terms or (looks_visual_only and not has_strong_objective_terms)
        ):
            reason = result.reason or "The verifier only suggested visual beautification."
            return VisualVerifierResult(
                done=True,
                reason=f"Ignored Visual Verifier advice outside the user's prompt: {reason}",
                instruction="",
            )
        return result
