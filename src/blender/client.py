"""
Blender MCP client adapted from LLM-Blender-Agent for GOSIM/Infinigen.

The public class name and UI-facing response shape are kept compatible with the
original project. The command set now targets the Infinigen-aware Blender addon
instead of Rodin/Hunyuan3D.
"""

from __future__ import annotations

import base64
import json
import os
import socket
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class BlenderClient:
    """Stateless JSON socket client for the GOSIM Blender addon."""

    def __init__(self, host: str = "localhost", port: int = 9876):
        self.host = host
        self.port = port
        try:
            scene_info = self.get_scene_info()
            self.is_connected = scene_info.get("status") != "error"
        except Exception:
            self.is_connected = False

    def close(self):
        self.is_connected = False

    def send_command(self, command_type: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if params is None:
            params = {}

        command = {"type": command_type, "params": params}
        timeout = (
            180
            if command_type in {"add_infinigen_asset", "edit_generated_asset", "render_scene", "adjust_camera_from_render"}
            else 30
        )

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect((self.host, self.port))
                command_data = json.dumps(command, ensure_ascii=False).encode("utf-8")
                sock.sendall(command_data)
                sock.shutdown(socket.SHUT_WR)

                response_data = b""
                while True:
                    data = sock.recv(65536)
                    if not data:
                        break
                    response_data += data

            if not response_data:
                return {"status": "error", "message": "没有收到 Blender 响应"}

            response = json.loads(response_data.decode("utf-8"))
            if "status" not in response:
                response["status"] = "success" if response.get("ok") else "error"
            if response.get("status") == "error" and "message" not in response:
                response["message"] = response.get("error", "未知错误")
            return response
        except socket.timeout:
            return {"status": "error", "message": "连接 Blender MCP 服务器超时"}
        except Exception as exc:
            return {"status": "error", "message": f"连接 Blender MCP 服务器失败: {exc}"}

    def get_scene_info(self) -> Dict[str, Any]:
        return self.send_command("get_scene_info")

    def set_agent_status(
        self,
        state: str,
        message: str = "",
        run_id: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"state": state, "message": message}
        if run_id:
            params["run_id"] = run_id
        if operation:
            params["operation"] = operation
        return self.send_command("set_agent_status", params)

    def get_agent_status(self) -> Dict[str, Any]:
        return self.send_command("get_agent_status")

    def cancel_agent_run(self) -> Dict[str, Any]:
        return self.send_command("cancel_agent_run")

    def rebuild_scene_index(self, save_path: Optional[str] = None) -> Dict[str, Any]:
        params = {}
        if save_path:
            params["save_path"] = save_path
        return self.send_command("rebuild_scene_index", params)

    def query_objects(self, text: str = "", category: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"text": text}
        if category:
            params["category"] = category
        return self.send_command("query_objects", params)

    def open_blend(self, path: str) -> Dict[str, Any]:
        return self.send_command("open_blend", {"path": path})

    def save_blend(self, path: Optional[str] = None) -> Dict[str, Any]:
        params = {}
        if path:
            params["path"] = path
        return self.send_command("save_blend", params)

    def add_infinigen_asset(
        self,
        category_or_factory: str,
        seed: int = 0,
        location: Tuple[float, float, float] = (0, 0, 0),
        scale: Optional[float] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "category_or_factory": category_or_factory,
            "seed": seed,
            "location": location,
        }
        if scale is not None:
            params["scale"] = scale
        return self.send_command(
            "add_infinigen_asset",
            params,
        )

    def generate_3d_model(
        self,
        text: Optional[str] = None,
        image_path: Optional[str] = None,
        object_name: Optional[str] = None,
        octree_resolution: int = 256,
        num_inference_steps: int = 20,
        guidance_scale: float = 5.5,
        texture: bool = False,
    ) -> Dict[str, Any]:
        """Compatibility wrapper.

        The original LLM-Blender-Agent exposed `generate_3d_model` for Hunyuan3D.
        In this fork the same call creates an Infinigen asset from the text/category.
        Image-based generation and texture flags are intentionally ignored.
        """
        category = object_name or text
        if not category:
            return {"status": "error", "message": "请提供要生成的 Infinigen 资产类别"}
        return self.add_infinigen_asset(category_or_factory=category)

    def edit_generated_asset(
        self,
        target: str,
        prompt: str,
        color: Optional[str] = None,
        preserve_size: bool = True,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "target": target,
            "prompt": prompt,
            "preserve_size": preserve_size,
        }
        if color:
            params["color"] = color
        return self.send_command("edit_generated_asset", params)

    def move_object(self, target: str, direction: str = "right", distance: float = 0.3) -> Dict[str, Any]:
        return self.send_command(
            "move_object",
            {"target": target, "direction": direction, "distance": distance},
        )

    def scale_object(self, target: str, factor: float = 1.2) -> Dict[str, Any]:
        return self.send_command("scale_object", {"target": target, "factor": factor})

    def rotate_object(
        self,
        target: str,
        axis: str = "z",
        angle_degrees: float = 90,
    ) -> Dict[str, Any]:
        return self.send_command(
            "rotate_object",
            {"target": target, "axis": axis, "angle_degrees": angle_degrees},
        )

    def delete_object(self, target: Optional[str] = None, name: Optional[str] = None) -> Dict[str, Any]:
        return self.send_command("delete_object", {"target": target or name})

    def get_object_info(self, name: str) -> Dict[str, Any]:
        result = self.query_objects(name)
        if result.get("status") == "success":
            matches = result.get("result", {}).get("matches", [])
            if matches:
                return {"status": "success", "result": matches[0]}
        return {"status": "error", "message": f"未找到对象: {name}"}

    def set_material(
        self,
        object_name: Optional[str] = None,
        target: Optional[str] = None,
        material_name: Optional[str] = None,
        create_if_missing: bool = True,
        color: Optional[List[float] | str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"target": target or object_name}
        if material_name:
            params["material_name"] = material_name
        if color:
            params["color"] = color
        return self.send_command("set_material", params)

    def place_on(self, source: str, target: str) -> Dict[str, Any]:
        return self.send_command("place_on", {"source": source, "target": target})

    def place_near(
        self,
        source: str,
        target: str,
        side: str = "right",
        gap: float = 0.25,
    ) -> Dict[str, Any]:
        return self.send_command(
            "place_near",
            {"source": source, "target": target, "side": side, "gap": gap},
        )

    def place_against_wall(
        self,
        target: str,
        wall: Optional[str] = None,
        gap: float = 0.05,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"target": target, "gap": gap}
        if wall:
            params["wall"] = wall
        return self.send_command("place_against_wall", params)

    def apply_physics_rules(self, target: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if target:
            params["target"] = target
        return self.send_command("apply_physics_rules", params)

    def adjust_existing_light(
        self,
        target: Optional[str] = None,
        light: Optional[str] = None,
        min_energy: float = 900.0,
        height: Optional[float] = None,
        distance: Optional[float] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"min_energy": min_energy}
        if target:
            params["target"] = target
        if light:
            params["light"] = light
        if height is not None:
            params["height"] = height
        if distance is not None:
            params["distance"] = distance
        return self.send_command("adjust_existing_light", params)

    def adjust_camera_from_render(
        self,
        target: Optional[str] = None,
        output_path: Optional[str] = None,
        resolution_x: int = 768,
        resolution_y: int = 432,
        target_fill: float = 0.72,
        max_iterations: int = 3,
        tolerance: float = 0.06,
        recenter_strength: float = 0.75,
        zoom_strength: float = 0.65,
        final_resolution_x: int = 1280,
        final_resolution_y: int = 720,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "resolution_x": resolution_x,
            "resolution_y": resolution_y,
            "target_fill": target_fill,
            "max_iterations": max_iterations,
            "tolerance": tolerance,
            "recenter_strength": recenter_strength,
            "zoom_strength": zoom_strength,
            "final_resolution_x": final_resolution_x,
            "final_resolution_y": final_resolution_y,
        }
        if target:
            params["target"] = target
        if output_path:
            params["output_path"] = output_path
        return self.send_command("adjust_camera_from_render", params)

    def render_scene(
        self,
        output_path: Optional[str] = None,
        resolution_x: Optional[int] = None,
        resolution_y: Optional[int] = None,
        return_image: bool = True,
        auto_save: bool = True,
        save_dir: str = "renders",
        auto_adjust_camera: bool = True,
        camera_target: Optional[str] = None,
        camera_target_fill: float = 0.72,
    ) -> Dict[str, Any]:
        if output_path is None and auto_save:
            os.makedirs(save_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(save_dir, f"render_{timestamp}.png")

        params: Dict[str, Any] = {"output_path": output_path}
        if resolution_x is not None:
            params["resolution_x"] = resolution_x
        if resolution_y is not None:
            params["resolution_y"] = resolution_y
        params["return_image"] = return_image
        params["auto_adjust_camera"] = auto_adjust_camera
        params["camera_target_fill"] = camera_target_fill
        if camera_target:
            params["camera_target"] = camera_target

        response = self.send_command("render_scene", params)
        result = response.get("result", {})
        if response.get("status") == "success" and isinstance(result, dict):
            if "saved_to" not in result and result.get("path"):
                result["saved_to"] = result["path"]
        return response

    def save_render_image(self, render_result: Dict[str, Any], save_path: str, create_dirs: bool = True) -> bool:
        try:
            if render_result.get("status") != "success":
                return False
            result = render_result.get("result", {})
            if "image_data" not in result:
                return False
            save_dir = os.path.dirname(save_path)
            if save_dir and not os.path.exists(save_dir) and create_dirs:
                os.makedirs(save_dir)
            with open(save_path, "wb") as img_file:
                img_file.write(base64.b64decode(result["image_data"]))
            return True
        except Exception:
            return False


def main():
    client = BlenderClient()
    print(json.dumps(client.get_scene_info(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
