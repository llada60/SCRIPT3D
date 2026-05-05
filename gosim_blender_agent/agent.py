"""Agent orchestration: plan natural language into Blender commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .client import BlenderClient
from .planner import Action, RulePlanner, make_planner


HELP_TEXT = """可用示例：
- 查看场景里有哪些物体
- 添加一张书桌
- 把台灯放到桌子上
- 把床往右移动 0.3 米
- 把桌子放大 1.2
- 把椅子靠墙
- 把柜子变成黑色
- 渲染预览
- 保存场景
"""


@dataclass
class AgentResult:
    text: str
    raw_results: list[dict[str, Any]]
    preview_path: str | None = None


class GosimAgent:
    def __init__(self, client: BlenderClient | None = None, planner: RulePlanner | None = None):
        self.client = client or BlenderClient()
        self.planner = planner or make_planner()

    def handle(self, user_text: str) -> AgentResult:
        actions = self.planner.plan(user_text)
        raw_results: list[dict[str, Any]] = []
        preview_path: str | None = None
        lines: list[str] = []

        for action in actions:
            if action.name == "help":
                lines.append(HELP_TEXT)
                raw_results.append({"action": action.name, "result": HELP_TEXT})
                continue
            result = self._execute(action)
            raw_results.append({"action": action.name, "args": action.args, "result": result})
            if action.name == "render_scene" and isinstance(result, dict):
                preview_path = result.get("path")
            lines.append(self._summarize(action, result))

        return AgentResult(text="\n".join(line for line in lines if line), raw_results=raw_results, preview_path=preview_path)

    def _execute(self, action: Action) -> Any:
        method = getattr(self.client, action.name)
        return method(**action.args)

    def _summarize(self, action: Action, result: Any) -> str:
        if action.name == "get_scene_info":
            return f"场景已连接：{result.get('object_count', 0)} 个对象，当前文件：{result.get('blend_path') or '未保存'}。"
        if action.name == "rebuild_scene_index":
            return f"索引已更新：{result.get('asset_count', 0)} 个资产。"
        if action.name == "query_objects":
            matches = result.get("matches", []) if isinstance(result, dict) else []
            if not matches:
                return "没有找到明确匹配的物体。"
            names = ", ".join(item.get("name", item.get("object_id", "?")) for item in matches[:8])
            return f"找到 {len(matches)} 个匹配物体：{names}"
        if action.name == "add_infinigen_asset":
            return f"已添加 Infinigen 资产：{result.get('object_id')} ({result.get('category')})。"
        if action.name == "edit_generated_asset":
            return (
                f"已编辑并替换生成资产：{result.get('old_object_id')} -> {result.get('object_id')}；"
                f"生成脚本：{result.get('generation_script')}"
            )
        if action.name in {"move_object", "scale_object", "rotate_object", "set_material", "place_on", "place_near", "place_against_wall", "delete_object"}:
            return result.get("message", f"{action.name} 完成。") if isinstance(result, dict) else f"{action.name} 完成。"
        if action.name == "apply_physics_rules":
            if not isinstance(result, dict):
                return "物理规则检查完成。"
            corrections = len(result.get("corrections", []))
            warnings = len(result.get("warnings", []))
            return f"物理规则检查完成：{corrections} 个修正，{warnings} 个提示。"
        if action.name == "render_scene":
            return f"预览已渲染：{result.get('path')}"
        if action.name == "save_blend":
            return f"场景已保存：{result.get('path')}"
        if action.name == "open_blend":
            return f"已打开场景：{result.get('path')}"
        return f"{action.name}: {result}"
