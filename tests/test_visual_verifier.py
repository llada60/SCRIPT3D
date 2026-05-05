import importlib.util
import sys
import types
import unittest
from pathlib import Path


def _load_visual_verifier_module():
    root = Path(__file__).resolve().parents[1]
    module_name = "src.agent.visual_verifier"

    src_pkg = types.ModuleType("src")
    src_pkg.__path__ = [str(root / "src")]
    agent_pkg = types.ModuleType("src.agent")
    agent_pkg.__path__ = [str(root / "src" / "agent")]
    llm_pkg = types.ModuleType("src.llm")
    llm_pkg.__path__ = [str(root / "src" / "llm")]
    base_mod = types.ModuleType("src.llm.base")
    base_mod.BaseLLM = type("BaseLLM", (), {})

    sys.modules.setdefault("src", src_pkg)
    sys.modules.setdefault("src.agent", agent_pkg)
    sys.modules.setdefault("src.llm", llm_pkg)
    sys.modules.setdefault("src.llm.base", base_mod)

    spec = importlib.util.spec_from_file_location(
        module_name,
        root / "src" / "agent" / "visual_verifier.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


visual_verifier = _load_visual_verifier_module()
VisualVerifierAgent = visual_verifier.VisualVerifierAgent
VisualVerifierResult = visual_verifier.VisualVerifierResult


class VisualVerifierScopeGuardTest(unittest.TestCase):
    def test_ignores_existing_unrequested_objects_for_incremental_add(self):
        result = VisualVerifierAgent._apply_scope_guard(
            "增加一个凳子",
            VisualVerifierResult(
                done=False,
                reason="场景中缺少凳子，且有未要求的苹果。",
                instruction="添加一个凳子，并删除苹果。",
            ),
        )

        self.assertFalse(result.done)
        self.assertEqual(result.reason, "场景中缺少凳子")
        self.assertEqual(result.instruction, "添加一个凳子")

    def test_keeps_delete_when_user_requested_delete(self):
        result = VisualVerifierAgent._apply_scope_guard(
            "删除苹果并增加一个凳子",
            VisualVerifierResult(
                done=False,
                reason="场景中缺少凳子，且有未要求的苹果。",
                instruction="添加一个凳子，并删除苹果。",
            ),
        )

        self.assertFalse(result.done)
        self.assertEqual(result.reason, "场景中缺少凳子，且有未要求的苹果。")
        self.assertEqual(result.instruction, "添加一个凳子，并删除苹果。")


if __name__ == "__main__":
    unittest.main()
