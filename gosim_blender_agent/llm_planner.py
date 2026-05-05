"""Optional OpenAI-compatible JSON planner.

The execution layer is provider-agnostic. This planner only converts natural
language into the same Action schema used by RulePlanner.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .planner import Action, RulePlanner


SYSTEM_PROMPT = """You are a Blender scene-editing planner.
Return JSON only with this shape:
{"actions":[{"name":"tool_name","args":{...}}]}

Allowed tools:
- get_scene_info {}
- rebuild_scene_index {}
- query_objects {"text": "..."}
- open_blend {"path": "/absolute/file.blend"}
- save_blend {}
- render_scene {}
- adjust_camera_from_render {"target": "object/category/name", "target_fill": 0.72}
- add_infinigen_asset {"category_or_factory": "bed|desk|table|side_table|desk_lamp|chair|sofa|cabinet|bookcase|rug|plant|apple|blackberry|green_coconut|hairy_coconut|durian|pineapple|starfruit|strawberry|compositional_fruit", "scale": 1.0}
- edit_generated_asset {"target": "object/category/name", "prompt": "full editing instruction", "color": "red|blue|green|white|black|wood|#RRGGBB", "preserve_size": true}
- move_object {"target": "object/category/name", "direction": "left|right|front|back|up|down", "distance": 0.3}
- scale_object {"target": "object/category/name", "factor": 1.2}
- rotate_object {"target": "object/category/name", "axis": "x|y|z", "angle_degrees": 90}
- delete_object {"target": "object/category/name"}
- set_material {"target": "object/category/name", "color": "red|blue|green|white|black|wood|#RRGGBB"}
- place_on {"source": "object/category/name", "target": "object/category/name"}
- place_near {"source": "object/category/name", "target": "object/category/name", "side": "left|right|front|back", "gap": 0.25}
- place_against_wall {"target": "object/category/name"}
- apply_physics_rules {"target": "object/category/name"} or {}

Hard physical rules:
- Never intentionally leave objects floating. Use place_on for supported placement and apply_physics_rules after spatial edits.
- Large furniture should rest on the floor unless explicitly placed on another support.
- Small supported objects such as lamps and fruit should use place_on when the user names a support surface.
- Rugs must rest on the floor.
- Do not use raw move_object to express "on", "beside", or "against wall" when a placement tool fits.
- Keep scale factors within a practical range; executor will clamp unsafe values.
- Use adjust_camera_from_render when the user asks to adjust camera position, view, framing, centering, or render composition.

Always add apply_physics_rules with the edited target/source after spatial edit operations, then add rebuild_scene_index.
Only omit the apply_physics_rules target when the user asks to check the whole scene.
When the user message starts with "\\editing", use edit_generated_asset.
Use semantic categories when object ids are unknown.
When adding strawberry, omit scale or use 0.15 unless the user asks for a different size.
Do not generate Python code.
"""


class OpenAICompatiblePlanner:
    def __init__(self) -> None:
        self.base_url = os.environ.get("GOSIM_LLM_BASE_URL", "").rstrip("/")
        self.api_key = os.environ.get("GOSIM_LLM_API_KEY", "")
        self.model = os.environ.get("GOSIM_LLM_MODEL", "")
        self.fallback = RulePlanner()
        if not self.base_url or not self.api_key or not self.model:
            raise ValueError("Set GOSIM_LLM_BASE_URL, GOSIM_LLM_API_KEY and GOSIM_LLM_MODEL")

    def plan(self, text: str) -> list[Action]:
        try:
            content = self._complete(text)
            data = json.loads(content)
            actions = data.get("actions", [])
            parsed = [Action(str(item["name"]), dict(item.get("args") or {})) for item in actions]
            return parsed or self.fallback.plan(text)
        except Exception:
            return self.fallback.plan(text)

    def _complete(self, text: str) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(message) from exc
        return data["choices"][0]["message"]["content"]
