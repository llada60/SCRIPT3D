"""Visual verifier agent for render-driven Blender editing loops."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from ..llm.base import BaseLLM


logger = logging.getLogger(__name__)


VISUAL_VERIFIER_SYSTEM_PROMPT = """你是 Blender 场景的 visual verifier。
你会看到一次 render 结果、用户原始目标和当前场景信息。你的任务不是美化画面，而是校验生成结果是否与用户 prompt 一致，并且是否符合物理常识和生活习惯。

只返回 JSON，不要返回 Markdown：
{
  "done": true | false,
  "reason": "一句话说明判断依据",
  "instruction": "如果 done=false，写给 Blender code generator 的具体中文调整指令；如果 done=true 留空"
}

核心职责：
- 只校验用户 prompt 中要求的内容是否出现、是否多出未要求物体、属性是否一致、空间关系是否正确。
- 校验物理常识和生活习惯：支撑接触、悬浮、穿模、重叠/碰撞、相对比例、摆放朝向、人与物日常使用方式。
- 使用相对比例和上下文判断大小，不要使用固定绝对尺寸阈值。例如判断苹果、草莓相对桌子和彼此是否像真实桌面物件，而不是输出固定米数。
- 用户说“在桌子旁边放张椅子”时，椅子应放在桌边且坐垫/正面朝向桌子，像可以坐下使用；不要只检查位置距离。
- 椅子靠桌时要检查是否穿进桌面、桌腿或其他物体；椅子应从可坐的一侧面向桌子，而不是从桌腿阻挡的一侧硬塞进去。
- 如果渲染太暗导致 prompt 相关物体无法辨认，或相机太远/裁切导致无法确认所有物体关系，可以返回 done=false，但修复只能调整已有 Light 或已有 Camera。

明确禁止：
- 不要因为主观构图不够好、材质不够清晰、渲染不够漂亮而返回 done=false，除非用户 prompt 明确要求调整相机、构图、材质或渲染效果。
- 不要新增光源。场景太暗时只能要求移动或调整已有 Light 的位置/能量，使 prompt 相关物体可辨认。
- 相机太远、主体太小或物体被裁切导致无法验证 prompt 时，可以要求调整已有 Camera；不要为了“更好看”调整相机。
- 不要要求添加 prompt 中没有的物体；不要把未要求的物体当作“更自然”的改进。
- 不要输出“添加补光灯”“占据画面 xx%”“确保材质清晰可见”等美化建议，除非这些就是用户原始目标。

返回规则：
- 如果 prompt 所需物体、属性、位置关系、相对比例、支撑/碰撞和生活习惯都基本正确，返回 done=true。
- 只要缺少 prompt 要求的物体、出现未要求物体、物体关系错误、明显重叠/穿模/悬浮、尺寸比例不符合生活常识、椅子/家具朝向不符合日常使用，就返回 done=false。
- 当需要调整时，instruction 必须只描述 prompt 一致性、物理常识、生活习惯或可验证性问题的具体修正，例如“把苹果移到草莓右侧一点，避免和草莓重叠，并保持两者都在桌面上”“旋转并移动椅子，使坐垫从未被桌腿阻挡的一侧面向桌子且不穿模”“移动已有 Light 到桌面前上方，不新增光源”“调整已有 Camera，使所有 prompt 相关物体可辨认且不裁切”。
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
                reason="没有可用 render 结果，跳过 Visual Verifier。",
            )

        verifier_messages = [
            {"role": "system", "content": VISUAL_VERIFIER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"用户原始目标：{user_goal or '未提供'}\n\n"
                            f"当前场景信息：\n{scene_text or '未获取'}\n\n"
                            "请检查这张 render 图是否已经满足目标。"
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
            logger.error("Visual Verifier 调用失败: %s", exc)
            return VisualVerifierResult(done=True, reason=f"Visual Verifier 调用失败：{exc}")

        content = (response or {}).get("content") or ""
        verdict = self._extract_json_object(content)
        if not verdict:
            lowered = content.lower()
            done = any(key in lowered for key in ("done", "ok", "acceptable", "可接受", "差不多", "完成"))
            return VisualVerifierResult(
                done=done,
                reason=content.strip() or "Verifier 未返回结构化结果。",
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
    def _apply_scope_guard(cls, user_goal: str, result: VisualVerifierResult) -> VisualVerifierResult:
        if result.done or not result.instruction:
            return result

        user_allows_visual_edits = cls._contains_any(user_goal or "", PROMPT_ALLOWED_VISUAL_KEYWORDS)
        if user_allows_visual_edits:
            return result

        instruction = result.instruction
        reason = result.reason or ""
        combined = f"{reason}\n{instruction}"
        if cls._contains_any(combined, ADD_LIGHT_KEYWORDS):
            return VisualVerifierResult(
                done=False,
                reason=reason or "渲染太暗，但不能新增 prompt 中没有的光源。",
                instruction="不要新增光源；只移动或调整场景中已有的 Light，使 prompt 相关物体可辨认。",
            )

        has_visibility_repair = cls._contains_any(combined, VISIBILITY_REPAIR_KEYWORDS)
        if has_visibility_repair:
            return result

        has_out_of_scope_terms = cls._contains_any(instruction, OUT_OF_SCOPE_VERIFIER_KEYWORDS)
        has_objective_terms = cls._contains_any(instruction, OBJECTIVE_VERIFIER_KEYWORDS)
        has_strong_objective_terms = cls._contains_any(instruction, STRONG_OBJECTIVE_VERIFIER_KEYWORDS)
        looks_visual_only = cls._contains_any(instruction, VISUAL_ONLY_PHRASES)
        if has_out_of_scope_terms and (not has_objective_terms or (looks_visual_only and not has_strong_objective_terms)):
            reason = result.reason or "Verifier 只提出了画面美化建议。"
            return VisualVerifierResult(
                done=True,
                reason=f"忽略超出用户 prompt 的 Visual Verifier 建议：{reason}",
                instruction="",
            )
        return result
