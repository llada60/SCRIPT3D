"""Visual verifier agent for render-driven Blender editing loops."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from ..llm.base import BaseLLM


logger = logging.getLogger(__name__)


VISUAL_VERIFIER_SYSTEM_PROMPT = """你是 Blender 场景的 visual verifier。
你会看到一次 render 结果、用户原始目标和当前场景信息。你的任务是判断画面是否已经接近用户目标。

只返回 JSON，不要返回 Markdown：
{
  "done": true | false,
  "reason": "一句话说明判断依据",
  "instruction": "如果 done=false，写给 Blender code generator 的具体中文调整指令；如果 done=true 留空"
}

当结果已经基本可接受，或只能做主观审美微调时，返回 done=true。
当需要调整时，instruction 必须具体、可执行，优先描述物体位置、camera、lighting、缩放、旋转、材质或构图参数，不要要求人工检查。
"""


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
        done = self._coerce_done(verdict.get("done")) or not instruction
        return VisualVerifierResult(
            done=done,
            reason=str(verdict.get("reason") or "").strip(),
            instruction="" if done else instruction,
        )

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
