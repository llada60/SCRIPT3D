bl_info = {
    "name": "Infinigen Agent",
    "author": "Infinigen Agent",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > INFINIGEN_AGENT",
    "description": "Socket bridge for natural-language editing of Infinigen scenes.",
    "category": "3D View",
}

import json
import importlib
import math
import os
import queue
import re
import socketserver
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

import bpy
from mathutils import Euler, Vector


HOST = os.getenv("INFINIGEN_AGENT_BLENDER_HOST", "127.0.0.1")
PORT = int(os.getenv("INFINIGEN_AGENT_BLENDER_PORT", "9876"))
REQUEST_QUEUE: queue.Queue[tuple[dict[str, Any], threading.Event, dict[str, Any]]] = queue.Queue()
SERVER: socketserver.ThreadingTCPServer | None = None
SERVER_THREAD: threading.Thread | None = None
TIMER_REGISTERED = False
INFINIGEN_CONFIGURED = False
AGENT_STATUS: dict[str, Any] = {
    "state": "idle",
    "message": "Agent 空闲",
    "operation": "",
    "run_id": "",
    "cancel_requested": False,
    "updated_at": 0.0,
}


ASSET_FACTORY_ALIASES = {
    "bed": "infinigen.assets.objects.seating.BedFactory",
    "床": "infinigen.assets.objects.seating.BedFactory",
    "bed_frame": "infinigen.assets.objects.seating.BedFrameFactory",
    "bed frame": "infinigen.assets.objects.seating.BedFrameFactory",
    "bedframe": "infinigen.assets.objects.seating.BedFrameFactory",
    "mattress": "infinigen.assets.objects.seating.MattressFactory",
    "pillow": "infinigen.assets.objects.seating.PillowFactory",
    "cushion": "infinigen.assets.objects.seating.PillowFactory",
    "desk": "infinigen.assets.objects.shelves.SimpleDeskFactory",
    "书桌": "infinigen.assets.objects.shelves.SimpleDeskFactory",
    "桌子": "infinigen.assets.objects.shelves.SimpleDeskFactory",
    "table": "infinigen.assets.objects.tables.TableDiningFactory",
    "餐桌": "infinigen.assets.objects.tables.TableDiningFactory",
    "side_table": "infinigen.assets.objects.tables.SideTableFactory",
    "床头柜": "infinigen.assets.objects.tables.SideTableFactory",
    "desk_lamp": "infinigen.assets.objects.lamp.DeskLampFactory",
    "lamp": "infinigen.assets.objects.lamp.DeskLampFactory",
    "台灯": "infinigen.assets.objects.lamp.DeskLampFactory",
    "chair": "infinigen.assets.objects.seating.chairs.ChairFactory",
    "椅子": "infinigen.assets.objects.seating.chairs.ChairFactory",
    "bar_chair": "infinigen.assets.objects.seating.chairs.BarChairFactory",
    "bar chair": "infinigen.assets.objects.seating.chairs.BarChairFactory",
    "bar stool": "infinigen.assets.objects.seating.chairs.BarChairFactory",
    "stool": "infinigen.assets.objects.seating.chairs.BarChairFactory",
    "office_chair": "infinigen.assets.objects.seating.chairs.OfficeChairFactory",
    "office chair": "infinigen.assets.objects.seating.chairs.OfficeChairFactory",
    "sofa": "infinigen.assets.objects.seating.SofaFactory",
    "沙发": "infinigen.assets.objects.seating.SofaFactory",
    "armchair": "infinigen.assets.objects.seating.ArmChairFactory",
    "arm chair": "infinigen.assets.objects.seating.ArmChairFactory",
    "lounge chair": "infinigen.assets.objects.seating.ArmChairFactory",
    "beverage_fridge": "infinigen.assets.objects.appliances.BeverageFridgeFactory",
    "beverage fridge": "infinigen.assets.objects.appliances.BeverageFridgeFactory",
    "drink fridge": "infinigen.assets.objects.appliances.BeverageFridgeFactory",
    "mini fridge": "infinigen.assets.objects.appliances.BeverageFridgeFactory",
    "fridge": "infinigen.assets.objects.appliances.BeverageFridgeFactory",
    "dishwasher": "infinigen.assets.objects.appliances.DishwasherFactory",
    "microwave": "infinigen.assets.objects.appliances.MicrowaveFactory",
    "microwave oven": "infinigen.assets.objects.appliances.MicrowaveFactory",
    "oven": "infinigen.assets.objects.appliances.OvenFactory",
    "tv": "infinigen.assets.objects.appliances.TVFactory",
    "television": "infinigen.assets.objects.appliances.TVFactory",
    "monitor": "infinigen.assets.objects.appliances.MonitorFactory",
    "computer monitor": "infinigen.assets.objects.appliances.MonitorFactory",
    "display": "infinigen.assets.objects.appliances.MonitorFactory",
    "cabinet": "infinigen.assets.objects.shelves.SingleCabinetFactory",
    "柜子": "infinigen.assets.objects.shelves.SingleCabinetFactory",
    "bookcase": "infinigen.assets.objects.shelves.SimpleBookcaseFactory",
    "书架": "infinigen.assets.objects.shelves.SimpleBookcaseFactory",
    "rug": "infinigen.assets.objects.elements.RugFactory",
    "地毯": "infinigen.assets.objects.elements.RugFactory",
    "plant": "infinigen.assets.objects.tableware.PlantContainerFactory",
    "植物": "infinigen.assets.objects.tableware.PlantContainerFactory",
    "apple": "infinigen.assets.objects.fruits.FruitFactoryApple",
    "苹果": "infinigen.assets.objects.fruits.FruitFactoryApple",
    "blackberry": "infinigen.assets.objects.fruits.FruitFactoryBlackberry",
    "黑莓": "infinigen.assets.objects.fruits.FruitFactoryBlackberry",
    "green_coconut": "infinigen.assets.objects.fruits.FruitFactoryCoconutgreen",
    "coconutgreen": "infinigen.assets.objects.fruits.FruitFactoryCoconutgreen",
    "green coconut": "infinigen.assets.objects.fruits.FruitFactoryCoconutgreen",
    "青椰子": "infinigen.assets.objects.fruits.FruitFactoryCoconutgreen",
    "椰青": "infinigen.assets.objects.fruits.FruitFactoryCoconutgreen",
    "hairy_coconut": "infinigen.assets.objects.fruits.FruitFactoryCoconuthairy",
    "coconuthairy": "infinigen.assets.objects.fruits.FruitFactoryCoconuthairy",
    "hairy coconut": "infinigen.assets.objects.fruits.FruitFactoryCoconuthairy",
    "coconut": "infinigen.assets.objects.fruits.FruitFactoryCoconuthairy",
    "毛椰子": "infinigen.assets.objects.fruits.FruitFactoryCoconuthairy",
    "椰子": "infinigen.assets.objects.fruits.FruitFactoryCoconuthairy",
    "durian": "infinigen.assets.objects.fruits.FruitFactoryDurian",
    "榴莲": "infinigen.assets.objects.fruits.FruitFactoryDurian",
    "pineapple": "infinigen.assets.objects.fruits.FruitFactoryPineapple",
    "菠萝": "infinigen.assets.objects.fruits.FruitFactoryPineapple",
    "凤梨": "infinigen.assets.objects.fruits.FruitFactoryPineapple",
    "starfruit": "infinigen.assets.objects.fruits.FruitFactoryStarfruit",
    "star fruit": "infinigen.assets.objects.fruits.FruitFactoryStarfruit",
    "杨桃": "infinigen.assets.objects.fruits.FruitFactoryStarfruit",
    "strawberry": "infinigen.assets.objects.fruits.FruitFactoryStrawberry",
    "草莓": "infinigen.assets.objects.fruits.FruitFactoryStrawberry",
    "compositional_fruit": "infinigen.assets.objects.fruits.FruitFactoryCompositional",
    "mixed fruit": "infinigen.assets.objects.fruits.FruitFactoryCompositional",
    "组合水果": "infinigen.assets.objects.fruits.FruitFactoryCompositional",
    "复合水果": "infinigen.assets.objects.fruits.FruitFactoryCompositional",
}


MATERIAL_ALIASES = {
    "wood": "infinigen.assets.materials.wood.Wood",
    "wooden": "infinigen.assets.materials.wood.Wood",
    "natural wood": "infinigen.assets.materials.wood.Wood",
    "hardwood_floor": "infinigen.assets.materials.wood.HardwoodFloor",
    "hardwood floor": "infinigen.assets.materials.wood.HardwoodFloor",
    "table_wood": "infinigen.assets.materials.wood.TableWood",
    "table wood": "infinigen.assets.materials.wood.TableWood",
    "plywood": "infinigen.assets.materials.wood.BlondePlywood",
    "blonde plywood": "infinigen.assets.materials.wood.BlondePlywood",
    "white_plywood": "infinigen.assets.materials.wood.WhitePlywood",
    "white plywood": "infinigen.assets.materials.wood.WhitePlywood",
    "black_plywood": "infinigen.assets.materials.wood.BlackPlywood",
    "black plywood": "infinigen.assets.materials.wood.BlackPlywood",
    "wood_tile": "infinigen.assets.materials.wood.wood_tile.WoodTiles",
    "wood tile": "infinigen.assets.materials.wood.wood_tile.WoodTiles",
    "wood tiles": "infinigen.assets.materials.wood.wood_tile.WoodTiles",
    "ceramic": "infinigen.assets.materials.ceramic.Ceramic",
    "glazed ceramic": "infinigen.assets.materials.ceramic.Ceramic",
    "brick": "infinigen.assets.materials.ceramic.Brick",
    "ceramic brick": "infinigen.assets.materials.ceramic.Brick",
    "concrete": "infinigen.assets.materials.ceramic.Concrete",
    "glass": "infinigen.assets.materials.ceramic.Glass",
    "marble": "infinigen.assets.materials.ceramic.Marble",
    "plaster": "infinigen.assets.materials.ceramic.Plaster",
    "tile": "infinigen.assets.materials.ceramic.Tile",
    "ceramic tile": "infinigen.assets.materials.ceramic.Tile",
    "advanced_tiles": "infinigen.assets.materials.tiles.advanced_tiles.apply",
    "tiles": "infinigen.assets.materials.tiles.advanced_tiles.apply",
    "patterned tiles": "infinigen.assets.materials.tiles.advanced_tiles.apply",
    "metal": "infinigen.assets.materials.metal.MetalBasic",
    "metallic": "infinigen.assets.materials.metal.MetalBasic",
    "aluminum": "infinigen.assets.materials.metal.Aluminum",
    "aluminium": "infinigen.assets.materials.metal.Aluminum",
    "brushed_metal": "infinigen.assets.materials.metal.BrushedMetal",
    "brushed metal": "infinigen.assets.materials.metal.BrushedMetal",
    "galvanized_metal": "infinigen.assets.materials.metal.GalvanizedMetal",
    "galvanized metal": "infinigen.assets.materials.metal.GalvanizedMetal",
    "grained_metal": "infinigen.assets.materials.metal.GrainedMetal",
    "grained metal": "infinigen.assets.materials.metal.GrainedMetal",
    "polished metal": "infinigen.assets.materials.metal.GrainedMetal",
    "hammered_metal": "infinigen.assets.materials.metal.HammeredMetal",
    "hammered metal": "infinigen.assets.materials.metal.HammeredMetal",
    "mirror": "infinigen.assets.materials.metal.Mirror",
    "mirrored metal": "infinigen.assets.materials.metal.Mirror",
    "black_glass": "infinigen.assets.materials.metal.BlackGlass",
    "black glass": "infinigen.assets.materials.metal.BlackGlass",
    "black_metal": "infinigen.assets.materials.metal.BrushedBlackMetal",
    "black metal": "infinigen.assets.materials.metal.BrushedBlackMetal",
    "brushed black metal": "infinigen.assets.materials.metal.BrushedBlackMetal",
    "white_metal": "infinigen.assets.materials.metal.WhiteMetal",
    "white metal": "infinigen.assets.materials.metal.WhiteMetal",
    "plastic": "infinigen.assets.materials.plastic.Plastic",
    "black_plastic": "infinigen.assets.materials.plastic.BlackPlastic",
    "black plastic": "infinigen.assets.materials.plastic.BlackPlastic",
    "rough_plastic": "infinigen.assets.materials.plastic.PlasticRough",
    "rough plastic": "infinigen.assets.materials.plastic.PlasticRough",
    "translucent_plastic": "infinigen.assets.materials.plastic.PlasticTranslucent",
    "translucent plastic": "infinigen.assets.materials.plastic.PlasticTranslucent",
    "clear plastic": "infinigen.assets.materials.plastic.PlasticTranslucent",
    "rubber": "infinigen.assets.materials.plastic.BumpyRubberFloor",
    "bumpy rubber": "infinigen.assets.materials.plastic.BumpyRubberFloor",
}


CATEGORY_ALIASES = {
    "bed": ("bed", "床"),
    "bed_frame": ("bed_frame", "bed frame", "bedframe"),
    "mattress": ("mattress",),
    "pillow": ("pillow", "cushion"),
    "desk": ("desk", "simpledesk", "书桌", "办公桌"),
    "table": ("table", "桌", "餐桌", "sidetable", "coffeetable"),
    "side_table": ("side_table", "sidetable", "nightstand", "床头柜", "边几"),
    "lamp": ("lamp", "light", "台灯", "灯"),
    "chair": ("chair", "椅"),
    "bar_chair": ("bar_chair", "bar chair", "bar stool", "stool"),
    "office_chair": ("office_chair", "office chair"),
    "sofa": ("sofa", "沙发"),
    "armchair": ("armchair", "arm chair", "lounge chair"),
    "beverage_fridge": ("beverage_fridge", "beverage fridge", "drink fridge", "mini fridge", "fridge"),
    "dishwasher": ("dishwasher",),
    "microwave": ("microwave", "microwave oven"),
    "oven": ("oven",),
    "tv": ("tv", "television"),
    "monitor": ("monitor", "computer monitor", "display"),
    "cabinet": ("cabinet", "柜"),
    "bookcase": ("bookcase", "shelf", "书架"),
    "rug": ("rug", "地毯"),
    "plant": ("plant", "植物", "盆栽"),
    "apple": ("apple", "苹果", "青苹果", "绿苹果"),
    "blackberry": ("blackberry", "黑莓"),
    "green_coconut": ("green_coconut", "coconutgreen", "green coconut", "青椰子", "椰青"),
    "hairy_coconut": ("hairy_coconut", "coconuthairy", "hairy coconut", "coconut", "毛椰子", "椰子"),
    "durian": ("durian", "榴莲"),
    "pineapple": ("pineapple", "菠萝", "凤梨"),
    "starfruit": ("starfruit", "star fruit", "杨桃"),
    "strawberry": ("strawberry", "草莓"),
    "compositional_fruit": ("compositional_fruit", "mixed fruit", "组合水果", "复合水果"),
    "wall": ("wall", "墙"),
    "floor": ("floor", "地面"),
    "ceiling": ("ceiling", "天花"),
    "window": ("window", "窗"),
    "door": ("door", "门"),
    "room": ("room", "卧室", "bedroom", "kitchen", "bathroom", "living"),
}


DEFAULT_ASSET_SCALES = {
    "apple": 0.12,
    "blackberry": 0.06,
    "green_coconut": 0.14,
    "hairy_coconut": 0.14,
    "durian": 0.12,
    "pineapple": 0.12,
    "starfruit": 0.10,
    "strawberry": 0.15,
    "compositional_fruit": 0.12,
    "pillow": 0.35,
}

MAX_ASSET_DIMENSIONS = {
    "apple": 0.24,
    "blackberry": 0.08,
    "green_coconut": 0.30,
    "hairy_coconut": 0.30,
    "durian": 0.34,
    "pineapple": 0.42,
    "starfruit": 0.20,
    "strawberry": 0.14,
    "compositional_fruit": 0.34,
}

PHYSICS_FLOOR_Z = 0.0
PHYSICS_GROUND_EPS = 0.03
PHYSICS_SUPPORT_EPS = 0.12
PHYSICS_COLLISION_EPS = 0.02
SUPPORT_SURFACE_Z_BIN = 0.04
SUPPORT_SURFACE_MIN_AREA = 0.01
SEATING_SURFACE_MAX_RELATIVE_Z = 0.78
MIN_SPAWN_SCALE = 0.05
MAX_SPAWN_SCALE = 5.0
MIN_SCALE_FACTOR = 0.3
MAX_SCALE_FACTOR = 3.0
STRUCTURAL_CATEGORIES = {"wall", "floor", "ceiling", "room", "window", "door", "camera"}


COLOR_MAP = {
    "red": (0.9, 0.05, 0.03, 1.0),
    "blue": (0.05, 0.18, 0.85, 1.0),
    "green": (0.05, 0.55, 0.18, 1.0),
    "white": (0.95, 0.95, 0.92, 1.0),
    "black": (0.01, 0.01, 0.012, 1.0),
    "wood": (0.45, 0.25, 0.11, 1.0),
    "红": (0.9, 0.05, 0.03, 1.0),
    "蓝": (0.05, 0.18, 0.85, 1.0),
    "绿": (0.05, 0.55, 0.18, 1.0),
    "白": (0.95, 0.95, 0.92, 1.0),
    "黑": (0.01, 0.01, 0.012, 1.0),
    "木": (0.45, 0.25, 0.11, 1.0),
}

COLOR_ALIASES = {
    "red": "red",
    "红": "red",
    "红色": "red",
    "blue": "blue",
    "蓝": "blue",
    "蓝色": "blue",
    "green": "green",
    "绿": "green",
    "绿色": "green",
    "青": "green",
    "青色": "green",
    "青苹果": "green",
    "white": "white",
    "白": "white",
    "白色": "white",
    "black": "black",
    "黑": "black",
    "黑色": "black",
    "wood": "wood",
    "wooden": "wood",
    "natural wood": "wood",
    "hardwood floor": "hardwood_floor",
    "table wood": "table_wood",
    "plywood": "plywood",
    "white plywood": "white_plywood",
    "black plywood": "black_plywood",
    "wood tile": "wood_tile",
    "wood tiles": "wood_tile",
    "ceramic": "ceramic",
    "glazed ceramic": "ceramic",
    "brick": "brick",
    "ceramic brick": "brick",
    "concrete": "concrete",
    "glass": "glass",
    "marble": "marble",
    "plaster": "plaster",
    "tile": "tile",
    "ceramic tile": "tile",
    "tiles": "advanced_tiles",
    "patterned tiles": "advanced_tiles",
    "metal": "metal",
    "metallic": "metal",
    "aluminum": "aluminum",
    "aluminium": "aluminum",
    "brushed metal": "brushed_metal",
    "galvanized metal": "galvanized_metal",
    "grained metal": "grained_metal",
    "polished metal": "grained_metal",
    "hammered metal": "hammered_metal",
    "mirror": "mirror",
    "mirrored metal": "mirror",
    "black glass": "black_glass",
    "black metal": "black_metal",
    "brushed black metal": "black_metal",
    "white metal": "white_metal",
    "plastic": "plastic",
    "black plastic": "black_plastic",
    "rough plastic": "rough_plastic",
    "translucent plastic": "translucent_plastic",
    "clear plastic": "translucent_plastic",
    "rubber": "rubber",
    "bumpy rubber": "rubber",
    "木": "wood",
    "木色": "wood",
}


def _json_default(value: Any) -> Any:
    if isinstance(value, Vector):
        return [float(value.x), float(value.y), float(value.z)]
    if isinstance(value, Euler):
        return [float(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _ok(result: Any = None) -> dict[str, Any]:
    return {"ok": True, "status": "success", "result": result}


def _err(message: str) -> dict[str, Any]:
    return {"ok": False, "status": "error", "error": message, "message": message}


def _set_agent_status(
    state: str,
    message: str = "",
    *,
    run_id: str | None = None,
    operation: str | None = None,
) -> dict[str, Any]:
    if state in {"running", "idle"}:
        AGENT_STATUS["cancel_requested"] = False
    AGENT_STATUS["state"] = state
    AGENT_STATUS["message"] = message or AGENT_STATUS.get("message") or ""
    AGENT_STATUS["operation"] = operation if operation is not None else AGENT_STATUS.get("operation", "")
    if run_id is not None:
        AGENT_STATUS["run_id"] = run_id
    if state in {"idle", "cancelled", "error"}:
        AGENT_STATUS["operation"] = ""
    AGENT_STATUS["updated_at"] = time.time()
    _sync_scene_agent_status()
    return dict(AGENT_STATUS)


def _sync_scene_agent_status() -> None:
    scene = getattr(bpy.context, "scene", None)
    if scene is None:
        return
    try:
        scene.agent_state = str(AGENT_STATUS.get("state", "idle"))
        scene.agent_message = str(AGENT_STATUS.get("message", ""))
        scene.agent_operation = str(AGENT_STATUS.get("operation", ""))
        scene.agent_cancel_requested = bool(AGENT_STATUS.get("cancel_requested", False))
    except Exception:
        pass


class _ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class _RequestHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        data = b""
        while True:
            chunk = self.request.recv(65536)
            if not chunk:
                break
            data += chunk

        slot: dict[str, Any] = {}
        event = threading.Event()
        try:
            request = json.loads(data.decode("utf-8"))
            REQUEST_QUEUE.put((request, event, slot))
            if not event.wait(timeout=300):
                slot["response"] = _err("Timed out waiting for Blender main thread")
        except Exception as exc:
            slot["response"] = _err(f"Invalid request: {exc}")

        response = slot.get("response", _err("No response produced"))
        self.request.sendall(json.dumps(response, ensure_ascii=False, default=_json_default).encode("utf-8"))


def _process_queue() -> float | None:
    while True:
        try:
            request, event, slot = REQUEST_QUEUE.get_nowait()
        except queue.Empty:
            break
        try:
            command = request.get("command") or request.get("type")
            payload = request.get("payload") if "payload" in request else request.get("params")
            payload = payload or {}
            handler = COMMANDS.get(command)
            if handler is None:
                slot["response"] = _err(f"Unknown command: {command}")
            elif AGENT_STATUS.get("cancel_requested") and command not in {
                "get_agent_status",
                "set_agent_status",
                "cancel_agent_run",
                "ping",
            }:
                slot["response"] = _err("Agent run cancelled")
            else:
                previous_status = dict(AGENT_STATUS)
                if command not in {"get_agent_status", "set_agent_status", "cancel_agent_run", "ping"}:
                    _set_agent_status(
                        "running",
                        f"Blender 正在执行：{command}",
                        run_id=previous_status.get("run_id") or None,
                        operation=command,
                    )
                try:
                    slot["response"] = _ok(handler(payload))
                finally:
                    if command not in {"get_agent_status", "set_agent_status", "cancel_agent_run", "ping"}:
                        if AGENT_STATUS.get("cancel_requested"):
                            _set_agent_status("cancelled", "Agent 运行已停止")
                        else:
                            _set_agent_status(
                                previous_status.get("state", "idle"),
                                previous_status.get("message", ""),
                                run_id=previous_status.get("run_id") or None,
                                operation=previous_status.get("operation") or None,
                            )
        except Exception:
            _set_agent_status("error", "Blender 命令执行失败")
            slot["response"] = _err(traceback.format_exc())
        finally:
            event.set()
    return 0.05 if SERVER is not None else None


def start_server() -> dict[str, Any]:
    global SERVER, SERVER_THREAD, TIMER_REGISTERED
    if SERVER is not None:
        return {"host": HOST, "port": PORT, "status": "already_running"}

    SERVER = _ThreadedTCPServer((HOST, PORT), _RequestHandler)
    SERVER_THREAD = threading.Thread(target=SERVER.serve_forever, daemon=True)
    SERVER_THREAD.start()

    if not TIMER_REGISTERED:
        bpy.app.timers.register(_process_queue, persistent=True)
        TIMER_REGISTERED = True

    print(f"[InfinigenAgent] Blender agent server listening on {HOST}:{PORT}")
    return {"host": HOST, "port": PORT, "status": "running"}


def stop_server() -> dict[str, Any]:
    global SERVER, SERVER_THREAD
    if SERVER is None:
        return {"status": "not_running"}
    SERVER.shutdown()
    SERVER.server_close()
    SERVER = None
    SERVER_THREAD = None
    return {"status": "stopped"}


def _ensure_id(obj: bpy.types.Object, prefix: str = "obj") -> str:
    if not obj.get("agent_object_id"):
        obj["agent_object_id"] = f"{prefix}_{uuid.uuid4().hex[:12]}"
    return str(obj["agent_object_id"])


def _ensure_asset_id(obj: bpy.types.Object) -> str:
    if obj.get("agent_asset_id"):
        return str(obj["agent_asset_id"])
    obj["agent_asset_id"] = f"asset_{uuid.uuid4().hex[:12]}"
    return str(obj["agent_asset_id"])


def _world_corners(obj: bpy.types.Object) -> list[Vector]:
    if hasattr(obj, "bound_box") and obj.bound_box:
        return [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return [obj.matrix_world.translation.copy()]


def _bounds_for_objects(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points: list[Vector] = []
    for obj in objects:
        if obj.type in {"MESH", "CURVE", "SURFACE", "FONT", "EMPTY", "LIGHT"}:
            points.extend(_world_corners(obj))
    if not points:
        points = [Vector((0, 0, 0))]
    mins = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    maxs = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return mins, maxs


def _center_from_bbox(bbox_min: list[float], bbox_max: list[float]) -> list[float]:
    return [(bbox_min[i] + bbox_max[i]) / 2 for i in range(3)]


def _dimensions_from_bbox(bbox_min: list[float], bbox_max: list[float]) -> list[float]:
    return [max(0.0, bbox_max[i] - bbox_min[i]) for i in range(3)]


def _alias_in_text(alias: str, text: str) -> bool:
    alias_lower = alias.lower()
    if re.search(r"[a-z0-9]", alias_lower):
        pattern = rf"(?<![a-z0-9]){re.escape(alias_lower)}(?![a-z0-9])"
        return re.search(pattern, text) is not None
    return alias_lower in text


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _safe_path_component(value: str | None, fallback: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[\\/:\0]+", "_", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-")
    return text or fallback


def _scene_generation_folder_name() -> str:
    if bpy.data.filepath:
        blend_name = _safe_path_component(Path(bpy.data.filepath).stem, "blend")
        scene_name = _safe_path_component(bpy.context.scene.name, "scene")
        return _safe_path_component(f"{blend_name}_{scene_name}", "scene")

    scene = bpy.context.scene
    if not scene.get("agent_scene_id"):
        scene["agent_scene_id"] = f"scene_{uuid.uuid4().hex[:12]}"
    scene_name = _safe_path_component(scene.name, "scene")
    scene_id = _safe_path_component(str(scene["agent_scene_id"]), "scene")
    return f"{scene_name}_{scene_id}"


def _generation_script_dir() -> Path:
    base = Path(bpy.data.filepath).parent if bpy.data.filepath else _project_root()
    path = base / "generation_scripts" / _scene_generation_folder_name()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _generation_script_filename(*, asset_id: str | None, category: str) -> str:
    item_name = asset_id or category
    return f"{_safe_path_component(item_name, f'asset_{uuid.uuid4().hex[:12]}')}.py"


def _generation_script_text(
    *,
    asset_id: str,
    category: str,
    factory_path: str,
    seed: int,
    scale: float,
    location: list[float],
    material_color: str | None = None,
    source_prompt: str | None = None,
) -> str:
    scene_folder = _scene_generation_folder_name()
    payload = {
        "object_id": asset_id,
        "asset_id": asset_id,
        "category": category,
        "factory_path": factory_path,
        "seed": seed,
        "scale": scale,
        "location": location,
        "material_color": material_color,
        "source_prompt": source_prompt,
        "scene": scene_folder,
    }
    return (
        '"""Reproducible generation record for a Infinigen asset.\n'
        "Run inside Blender with the Infinigen addon loaded if you want to replay it.\n"
        '"""\n\n'
        "import json\n\n"
        f"GENERATION = {json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "def replay(client):\n"
        "    result = client.add_infinigen_asset(\n"
        "        category_or_factory=GENERATION['factory_path'],\n"
        "        seed=GENERATION['seed'],\n"
        "        location=tuple(GENERATION['location']),\n"
        "        scale=GENERATION['scale'],\n"
        "    )\n"
        "    if GENERATION.get('material_color'):\n"
        "        client.set_material(result['object_id'], color=GENERATION['material_color'])\n"
        "    return result\n"
    )


def _write_generation_script(
    *,
    asset_id: str,
    category: str,
    factory_path: str,
    seed: int,
    scale: float,
    location: list[float],
    material_color: str | None = None,
    source_prompt: str | None = None,
) -> str:
    filename = _generation_script_filename(asset_id=asset_id, category=category)
    path = _generation_script_dir() / filename
    path.write_text(
        _generation_script_text(
            asset_id=asset_id,
            category=category,
            factory_path=factory_path,
            seed=seed,
            scale=scale,
            location=location,
            material_color=material_color,
            source_prompt=source_prompt,
        ),
        encoding="utf-8",
    )
    return str(path)


def _category_from_text(text: str, obj_type: str = "") -> str:
    lowered = text.lower()
    if obj_type == "LIGHT":
        return "lamp"
    if obj_type == "CAMERA":
        return "camera"
    for category, aliases in CATEGORY_ALIASES.items():
        if any(_alias_in_text(alias, lowered) for alias in aliases):
            return category
    return "object"


def _category_from_asset_request(request: str, factory_path: str) -> str:
    lowered = f"{request} {factory_path}".lower()
    priority = (
        ("bed_frame", ("bedframefactory", "bed_frame", "bed frame", "bedframe")),
        ("mattress", ("mattressfactory", "mattress")),
        ("pillow", ("pillowfactory", "pillow", "cushion")),
        ("side_table", ("side_table", "sidetable", "nightstand", "床头柜")),
        ("lamp", ("desk_lamp", "floor_lamp", "desklamp", "floorlamp", "lamp", "台灯", "灯")),
        ("desk", ("simpledesk", "desk", "书桌")),
        ("bookcase", ("bookcase", "bookshelf", "书架")),
        ("cabinet", ("cabinet", "柜")),
        ("bar_chair", ("barchairfactory", "bar_chair", "bar chair", "bar stool", "stool")),
        ("office_chair", ("officechairfactory", "office_chair", "office chair")),
        ("armchair", ("armchairfactory", "armchair", "arm chair", "lounge chair")),
        ("chair", ("officechair", "chair", "椅")),
        ("sofa", ("sofa", "沙发")),
        ("beverage_fridge", ("beveragefridgefactory", "beverage_fridge", "beverage fridge", "drink fridge", "mini fridge", "fridge")),
        ("dishwasher", ("dishwasherfactory", "dishwasher")),
        ("microwave", ("microwavefactory", "microwave", "microwave oven")),
        ("oven", ("ovenfactory", "oven")),
        ("monitor", ("monitorfactory", "monitor", "computer monitor", "display")),
        ("tv", ("tvfactory", "tv", "television")),
        ("bed", ("bed", "床")),
        ("rug", ("rug", "地毯")),
        ("plant", ("plant", "植物")),
        ("blackberry", ("fruitfactoryblackberry", "blackberry", "黑莓")),
        ("green_coconut", ("fruitfactorycoconutgreen", "green_coconut", "coconutgreen", "green coconut", "青椰子", "椰青")),
        ("hairy_coconut", ("fruitfactorycoconuthairy", "hairy_coconut", "coconuthairy", "hairy coconut", "coconut", "毛椰子", "椰子")),
        ("durian", ("fruitfactorydurian", "durian", "榴莲")),
        ("pineapple", ("fruitfactorypineapple", "pineapple", "菠萝", "凤梨")),
        ("apple", ("fruitfactoryapple", "apple", "苹果", "青苹果", "绿苹果")),
        ("starfruit", ("fruitfactorystarfruit", "starfruit", "star fruit", "杨桃")),
        ("strawberry", ("fruitfactorystrawberry", "strawberry", "草莓")),
        ("compositional_fruit", ("fruitfactorycompositional", "compositional_fruit", "mixed fruit", "组合水果", "复合水果")),
        ("table", ("table", "桌")),
    )
    for category, aliases in priority:
        if any(_alias_in_text(alias, lowered) for alias in aliases):
            return category
    return _category_from_text(lowered)


def _category_for_group(root: bpy.types.Object, objects: list[bpy.types.Object]) -> str:
    explicit = root.get("agent_category")
    if explicit:
        return str(explicit)
    factory = root.get("agent_factory", "")
    names = " ".join([root.name, str(factory), *[obj.name for obj in objects[:8]]])
    return _category_from_text(names, root.type)


def _material_names(objects: list[bpy.types.Object]) -> list[str]:
    names: set[str] = set()
    for obj in objects:
        if obj.type == "MESH" and obj.data and hasattr(obj.data, "materials"):
            for mat in obj.data.materials:
                if mat:
                    names.add(mat.name)
    return sorted(names)


def _asset_root_for_existing(obj: bpy.types.Object) -> bpy.types.Object:
    if obj.get("agent_asset_id"):
        current = obj
        while current.parent and current.parent.get("agent_asset_id") == obj.get("agent_asset_id"):
            current = current.parent
        return current
    return obj


def _visible_scene_objects() -> list[bpy.types.Object]:
    return [
        obj
        for obj in bpy.context.scene.objects
        if obj.type in {"MESH", "EMPTY", "LIGHT", "CAMERA", "CURVE", "SURFACE", "FONT"}
        and not obj.hide_get()
    ]


def _build_groups() -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for obj in _visible_scene_objects():
        if obj.name.startswith("__"):
            continue
        _ensure_id(obj)
        asset_id = obj.get("agent_asset_id")
        if asset_id:
            group_id = str(asset_id)
            root = _asset_root_for_existing(obj)
        else:
            root = obj
            group_id = _ensure_asset_id(root)
        groups.setdefault(group_id, {"root": root, "objects": []})
        groups[group_id]["objects"].append(obj)
    return groups


def _xy_overlap(a: dict[str, Any], b: dict[str, Any]) -> float:
    ax0, ay0, _ = a["bbox_min"]
    ax1, ay1, _ = a["bbox_max"]
    bx0, by0, _ = b["bbox_min"]
    bx1, by1, _ = b["bbox_max"]
    x = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    y = max(0.0, min(ay1, by1) - max(ay0, by0))
    area = x * y
    denom = max(1e-6, min((ax1 - ax0) * (ay1 - ay0), (bx1 - bx0) * (by1 - by0)))
    return area / denom


def _distance_xy(a: dict[str, Any], b: dict[str, Any]) -> float:
    ac = a["center"]
    bc = b["center"]
    return math.sqrt((ac[0] - bc[0]) ** 2 + (ac[1] - bc[1]) ** 2)


def _build_scene_index(save_path: str | None = None) -> dict[str, Any]:
    groups = _build_groups()
    assets: list[dict[str, Any]] = []
    for group_id, group in groups.items():
        root = group["root"]
        objects = group["objects"]
        bbox_min_v, bbox_max_v = _bounds_for_objects(objects)
        bbox_min = [float(v) for v in bbox_min_v]
        bbox_max = [float(v) for v in bbox_max_v]
        category = _category_for_group(root, objects)
        materials = _material_names(objects)
        asset = {
            "object_id": group_id,
            "root_name": root.name,
            "name": root.name,
            "category": category,
            "factory": root.get("agent_factory"),
            "object_names": [obj.name for obj in objects],
            "type": root.type,
            "location": [float(v) for v in root.location],
            "rotation_euler": [float(v) for v in root.rotation_euler],
            "scale": [float(v) for v in root.scale],
            "bbox_min": bbox_min,
            "bbox_max": bbox_max,
            "center": _center_from_bbox(bbox_min, bbox_max),
            "dimensions": _dimensions_from_bbox(bbox_min, bbox_max),
            "materials": materials,
            "generation": {
                "script_path": root.get("agent_generation_script"),
                "seed": root.get("agent_seed"),
                "source_prompt": root.get("agent_source_prompt"),
                "edit_prompt": root.get("agent_edit_prompt"),
            },
            "description": "",
            "relations": {"near": [], "on_top_of": None, "supports": [], "nearest": None, "nearest_wall": None},
        }
        asset["description"] = (
            f"{asset['object_id']} is a {category} named {root.name}; "
            f"center={asset['center']}; size={asset['dimensions']}; materials={materials}."
        )
        assets.append(asset)

    by_id = {asset["object_id"]: asset for asset in assets}
    for asset in assets:
        distances = [
            (_distance_xy(asset, other), other)
            for other in assets
            if other["object_id"] != asset["object_id"]
        ]
        distances.sort(key=lambda item: item[0])
        asset["relations"]["near"] = [
            other["object_id"]
            for distance, other in distances
            if distance < max(1.5, sum(asset["dimensions"][:2]) * 0.75)
        ][:8]
        asset["relations"]["nearest"] = distances[0][1]["object_id"] if distances else None
        wall_distances = [(distance, other) for distance, other in distances if other["category"] == "wall"]
        asset["relations"]["nearest_wall"] = wall_distances[0][1]["object_id"] if wall_distances else None

    for asset in assets:
        for other in assets:
            if asset["object_id"] == other["object_id"]:
                continue
            z_gap = abs(asset["bbox_min"][2] - other["bbox_max"][2])
            if z_gap <= 0.12 and _xy_overlap(asset, other) > 0.12:
                asset["relations"]["on_top_of"] = other["object_id"]
                by_id[other["object_id"]]["relations"]["supports"].append(asset["object_id"])
                break

    index = {
        "schema_version": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "blend_path": bpy.data.filepath,
        "asset_count": len(assets),
        "assets": assets,
    }

    if save_path is None:
        base = Path(bpy.data.filepath).parent if bpy.data.filepath else Path.cwd()
        save_path = str(base / "scene_index.json")
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    Path(save_path).write_text(json.dumps(index, ensure_ascii=False, indent=2, default=_json_default))
    index["save_path"] = save_path
    return index


def _score_asset(asset: dict[str, Any], text: str) -> int:
    lowered = text.lower().strip()
    if not lowered:
        return 1
    fields = [
        asset.get("object_id", ""),
        asset.get("name", ""),
        asset.get("root_name", ""),
        asset.get("category", ""),
        asset.get("factory", "") or "",
        " ".join(asset.get("object_names", [])),
        " ".join(asset.get("materials", [])),
        asset.get("description", ""),
    ]
    haystack = " ".join(str(field).lower() for field in fields)
    score = 0
    if lowered == str(asset.get("object_id", "")).lower():
        score += 100
    if lowered == str(asset.get("name", "")).lower():
        score += 80
    if lowered == str(asset.get("category", "")).lower():
        score += 50
    if lowered in haystack:
        score += 20
    for category, aliases in CATEGORY_ALIASES.items():
        if any(alias.lower() in lowered for alias in aliases) and asset.get("category") == category:
            score += 30
    return score


def _query_assets(text: str = "", category: str | None = None) -> list[dict[str, Any]]:
    index = _build_scene_index()
    scored: list[tuple[int, dict[str, Any]]] = []
    for asset in index["assets"]:
        if category and asset["category"] != category:
            continue
        score = _score_asset(asset, text)
        if score > 0:
            scored.append((score, asset))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [asset for _, asset in scored]


def _resolve_asset(ref: str | None) -> dict[str, Any]:
    if not ref:
        raise ValueError("Missing object reference")
    matches = _query_assets(ref)
    if not matches:
        raise ValueError(f"Could not find object matching '{ref}'")
    return matches[0]


def _objects_for_asset(asset: dict[str, Any]) -> list[bpy.types.Object]:
    wanted = set(asset.get("object_names", []))
    return [obj for obj in bpy.context.scene.objects if obj.name in wanted]


def _root_objects_for_asset(asset: dict[str, Any]) -> list[bpy.types.Object]:
    objects = _objects_for_asset(asset)
    names = {obj.name for obj in objects}
    roots = [obj for obj in objects if obj.parent is None or obj.parent.name not in names]
    return roots or objects[:1]


def _move_asset(asset: dict[str, Any], delta: Vector) -> None:
    for obj in _root_objects_for_asset(asset):
        obj.location += delta
    bpy.context.view_layer.update()


def _set_asset_location_by_bbox_min(asset: dict[str, Any], new_bbox_min: Vector) -> None:
    current_min = Vector(asset["bbox_min"])
    _move_asset(asset, new_bbox_min - current_min)


def _fit_asset_to_max_dimension(
    asset: dict[str, Any],
    max_dimension: float | None,
    *,
    preserve_bbox_min: Vector | None = None,
) -> dict[str, Any]:
    if not max_dimension or max_dimension <= 0:
        return asset
    dimensions = Vector(asset["dimensions"])
    current_max = max(float(dimensions.x), float(dimensions.y), float(dimensions.z))
    if current_max <= max_dimension or current_max <= 1e-6:
        return asset
    factor = max_dimension / current_max
    for obj in _root_objects_for_asset(asset):
        obj.scale = obj.scale * factor
    bpy.context.view_layer.update()
    resized = _resolve_asset(asset["object_id"])
    if preserve_bbox_min is not None:
        _set_asset_location_by_bbox_min(resized, preserve_bbox_min)
        resized = _resolve_asset(asset["object_id"])
    return resized


def _polygon_world_area(points: list[Vector]) -> float:
    if len(points) < 3:
        return 0.0
    origin = points[0]
    area = 0.0
    for i in range(1, len(points) - 1):
        area += ((points[i] - origin).cross(points[i + 1] - origin)).length / 2
    return area


def _support_surface_candidates(asset: dict[str, Any]) -> list[dict[str, Any]]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bins: dict[int, dict[str, Any]] = {}

    for obj in _objects_for_asset(asset):
        if obj.type != "MESH" or not obj.data:
            continue
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = None
        try:
            mesh = eval_obj.to_mesh()
            normal_matrix = eval_obj.matrix_world.to_3x3()
            for poly in mesh.polygons:
                normal = (normal_matrix @ poly.normal).normalized()
                if normal.z < 0.55:
                    continue

                points = [eval_obj.matrix_world @ mesh.vertices[index].co for index in poly.vertices]
                area = _polygon_world_area(points)
                if area <= 1e-6:
                    continue

                center = sum(points, Vector((0, 0, 0))) / len(points)
                key = round(center.z / SUPPORT_SURFACE_Z_BIN)
                xs = [point.x for point in points]
                ys = [point.y for point in points]
                zs = [point.z for point in points]
                bucket = bins.setdefault(
                    key,
                    {
                        "area": 0.0,
                        "weighted_center": Vector((0, 0, 0)),
                        "min_x": min(xs),
                        "max_x": max(xs),
                        "min_y": min(ys),
                        "max_y": max(ys),
                        "z": max(zs),
                    },
                )
                bucket["area"] += area
                bucket["weighted_center"] += center * area
                bucket["min_x"] = min(bucket["min_x"], min(xs))
                bucket["max_x"] = max(bucket["max_x"], max(xs))
                bucket["min_y"] = min(bucket["min_y"], min(ys))
                bucket["max_y"] = max(bucket["max_y"], max(ys))
                bucket["z"] = max(bucket["z"], max(zs))
        except Exception as exc:
            print(f"[InfinigenAgent] Support surface scan skipped {obj.name}: {exc}")
        finally:
            if mesh is not None:
                eval_obj.to_mesh_clear()

    candidates: list[dict[str, Any]] = []
    for bucket in bins.values():
        area = float(bucket["area"])
        if area < SUPPORT_SURFACE_MIN_AREA:
            continue
        center = bucket["weighted_center"] / area
        candidates.append(
            {
                "area": area,
                "center": [float(center.x), float(center.y), float(bucket["z"])],
                "bbox_min": [float(bucket["min_x"]), float(bucket["min_y"]), float(bucket["z"])],
                "bbox_max": [float(bucket["max_x"]), float(bucket["max_y"]), float(bucket["z"])],
                "z": float(bucket["z"]),
            }
        )
    return candidates


def _support_surface_for_place_on(target: dict[str, Any]) -> dict[str, Any]:
    candidates = _support_surface_candidates(target)
    bbox_min = Vector(target["bbox_min"])
    bbox_max = Vector(target["bbox_max"])
    dimensions = Vector(target["dimensions"])
    category = target.get("category")

    if candidates:
        if category in {"chair", "sofa"} and dimensions.z > 1e-6:
            max_seat_z = bbox_min.z + dimensions.z * SEATING_SURFACE_MAX_RELATIVE_Z
            seating_candidates = [candidate for candidate in candidates if candidate["z"] <= max_seat_z]
            if seating_candidates:
                return max(seating_candidates, key=lambda item: (item["area"], item["z"]))
        return max(candidates, key=lambda item: (item["z"], item["area"]))

    return {
        "area": max(0.0, dimensions.x * dimensions.y),
        "center": [float((bbox_min.x + bbox_max.x) / 2), float((bbox_min.y + bbox_max.y) / 2), float(bbox_max.z)],
        "bbox_min": [float(bbox_min.x), float(bbox_min.y), float(bbox_max.z)],
        "bbox_max": [float(bbox_max.x), float(bbox_max.y), float(bbox_max.z)],
        "z": float(bbox_max.z),
    }


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _find_supporting_asset(
    asset: dict[str, Any],
    assets: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for other in assets:
        if other["object_id"] == asset["object_id"]:
            continue
        if other.get("category") in {"wall", "ceiling", "window", "door"}:
            continue
        support_surface = _support_surface_for_place_on(other)
        z_gap = abs(float(asset["bbox_min"][2]) - float(support_surface["z"]))
        if z_gap <= PHYSICS_SUPPORT_EPS and _xy_overlap(asset, other) > 0.12:
            return other
    return None


def _bbox_overlap_3d(a: dict[str, Any], b: dict[str, Any]) -> bool:
    overlaps = []
    for axis in range(3):
        amin = float(a["bbox_min"][axis])
        amax = float(a["bbox_max"][axis])
        bmin = float(b["bbox_min"][axis])
        bmax = float(b["bbox_max"][axis])
        overlaps.append(min(amax, bmax) - max(amin, bmin))
    return all(overlap > PHYSICS_COLLISION_EPS for overlap in overlaps)


def _apply_physics_rules(target: str | None = None) -> dict[str, Any]:
    index = _build_scene_index()
    assets = index["assets"]
    if target:
        target_asset = _resolve_asset(target)
        target_ids = {target_asset["object_id"]}
    else:
        target_ids = {
            asset["object_id"]
            for asset in assets
            if asset.get("category") not in STRUCTURAL_CATEGORIES
        }

    corrections: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for object_id in sorted(target_ids):
        asset = _resolve_asset(object_id)
        category = asset.get("category")
        if category in STRUCTURAL_CATEGORIES:
            continue

        support = _find_supporting_asset(asset, _build_scene_index()["assets"])
        bbox_min = Vector(asset["bbox_min"])
        max_dimension = MAX_ASSET_DIMENSIONS.get(str(category))
        if max_dimension:
            resized = _fit_asset_to_max_dimension(
                asset,
                max_dimension,
                preserve_bbox_min=bbox_min,
            )
            if resized is not asset:
                new_dimensions = Vector(resized["dimensions"])
                corrections.append(
                    {
                        "object_id": object_id,
                        "rule": "limit_asset_size",
                        "category": category,
                        "max_dimension": max_dimension,
                        "new_dimensions": [float(v) for v in new_dimensions],
                    }
                )
                asset = resized
                bbox_min = Vector(asset["bbox_min"])

        if bbox_min.z < PHYSICS_FLOOR_Z - PHYSICS_GROUND_EPS:
            _set_asset_location_by_bbox_min(
                asset,
                Vector((bbox_min.x, bbox_min.y, PHYSICS_FLOOR_Z)),
            )
            corrections.append(
                {
                    "object_id": object_id,
                    "rule": "snap_above_floor",
                    "from_z": float(bbox_min.z),
                    "to_z": PHYSICS_FLOOR_Z,
                }
            )
        elif bbox_min.z > PHYSICS_FLOOR_Z + PHYSICS_GROUND_EPS and support is None:
            _set_asset_location_by_bbox_min(
                asset,
                Vector((bbox_min.x, bbox_min.y, PHYSICS_FLOOR_Z)),
            )
            corrections.append(
                {
                    "object_id": object_id,
                    "rule": "prevent_floating",
                    "from_z": float(bbox_min.z),
                    "to_z": PHYSICS_FLOOR_Z,
                }
            )

    index = _build_scene_index()
    by_id = {asset["object_id"]: asset for asset in index["assets"]}
    for object_id in sorted(target_ids):
        asset = by_id.get(object_id)
        if not asset or asset.get("category") in STRUCTURAL_CATEGORIES:
            continue
        for other in index["assets"]:
            if other["object_id"] == object_id or other.get("category") in STRUCTURAL_CATEGORIES:
                continue
            if _bbox_overlap_3d(asset, other):
                pair = sorted([object_id, other["object_id"]])
                warning_id = f"{pair[0]}:{pair[1]}"
                if not any(item.get("id") == warning_id for item in warnings):
                    warnings.append(
                        {
                            "id": warning_id,
                            "rule": "possible_collision",
                            "object_id": object_id,
                            "other_id": other["object_id"],
                        }
                    )

    return {
        "message": f"Applied physical rules: {len(corrections)} corrections, {len(warnings)} warnings",
        "target": target,
        "corrections": corrections,
        "warnings": warnings,
    }


def _direction_vector(direction: str) -> Vector:
    mapping = {
        "left": Vector((-1, 0, 0)),
        "right": Vector((1, 0, 0)),
        "front": Vector((0, -1, 0)),
        "back": Vector((0, 1, 0)),
        "up": Vector((0, 0, 1)),
        "down": Vector((0, 0, -1)),
        "x": Vector((1, 0, 0)),
        "y": Vector((0, 1, 0)),
        "z": Vector((0, 0, 1)),
    }
    return mapping.get(direction, mapping["right"])


def _make_material(color: str | None, material_name: str | None) -> bpy.types.Material:
    prompt_mat = _generate_prompt_material(color, material_name)
    if prompt_mat is not None:
        return prompt_mat
    if isinstance(color, (list, tuple)):
        rgba = tuple(float(v) for v in color[:4])
        if len(rgba) == 3:
            rgba = rgba + (1.0,)
    else:
        color_text = str(color or "")
        rgba = COLOR_MAP.get(color_text.lower(), COLOR_MAP.get(color_text, (0.8, 0.8, 0.8, 1.0)))
        if color_text.startswith("#") and len(color_text) in {7, 9}:
            rgba = tuple(int(color_text[i : i + 2], 16) / 255 for i in (1, 3, 5)) + (1.0,)
    name = material_name or f"Agent_{color or 'material'}"
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    node = mat.node_tree.nodes.get("Principled BSDF")
    if node:
        node.inputs["Base Color"].default_value = rgba
        node.inputs["Roughness"].default_value = 0.55
    return mat


def _resolve_material_path(material: str | None) -> str | None:
    if not material:
        return None
    material_text = str(material).lower().strip()
    return MATERIAL_ALIASES.get(material_text)


def _import_infinigen_item(path: str) -> Any:
    _configure_infinigen_once()
    try:
        from infinigen.core.util.test_utils import import_item

        return import_item(path)
    except Exception:
        module_name, item_name = path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        return getattr(module, item_name)


def _generate_prompt_material(material: str | None, material_name: str | None = None) -> bpy.types.Material | None:
    material_path = _resolve_material_path(material)
    if not material_path or material_path.endswith(".apply"):
        return None
    material_item = _import_infinigen_item(material_path)
    material_obj = material_item() if isinstance(material_item, type) else material_item
    generated = None
    if hasattr(material_obj, "generate"):
        generated = material_obj.generate()
    elif callable(material_obj):
        generated = material_obj()
    if isinstance(generated, bpy.types.Material):
        generated.name = material_name or f"Agent_{str(material or 'material')}"
        return generated
    return None


def _apply_prompt_material(obj: bpy.types.Object, material: str | None, material_name: str | None = None) -> bool:
    material_path = _resolve_material_path(material)
    if not material_path:
        return False
    material_item = _import_infinigen_item(material_path)
    if material_path.endswith(".apply"):
        material_item(obj)
        return True

    material_obj = material_item() if isinstance(material_item, type) else material_item
    if hasattr(material_obj, "apply"):
        material_obj.apply(obj)
        return True

    generated = _generate_prompt_material(material, material_name)
    if generated is None:
        return False
    obj.data.materials.clear()
    obj.data.materials.append(generated)
    return True


def _color_from_prompt(prompt: str, explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    lowered = prompt.lower()
    hex_match = re.search(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?", prompt)
    if hex_match:
        return hex_match.group(0)
    for key, color in sorted(COLOR_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if key.lower() in lowered:
            return color
    return None


def _ensure_infinigen_on_path() -> Path:
    candidates = [
        os.getenv("INFINIGEN_AGENT_INFINIGEN_ROOT"),
        os.getenv("INFINIGEN_ROOT"),
        str(Path(__file__).resolve().parents[1] / "third_party" / "infinigen"),
        str(Path(__file__).resolve().parents[2] / "third_party" / "infinigen"),
    ]
    for candidate in candidates:
        if candidate and (Path(candidate) / "infinigen").exists():
            root = Path(candidate)
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            return root
    raise RuntimeError("Could not locate Infinigen root. Set INFINIGEN_AGENT_INFINIGEN_ROOT.")


def _candidate_python_dependency_paths() -> list[Path]:
    candidates: list[Path] = []

    for env_name in ("INFINIGEN_AGENT_PYTHON_SITE_PACKAGES", "PYTHONPATH"):
        for raw_path in os.getenv(env_name, "").split(os.pathsep):
            if raw_path:
                candidates.append(Path(raw_path).expanduser())

    for env_name in ("CONDA_PREFIX", "VIRTUAL_ENV"):
        prefix = os.getenv(env_name)
        if not prefix:
            continue
        for version in {
            f"python{sys.version_info.major}.{sys.version_info.minor}",
            "python3.11",
        }:
            candidates.append(Path(prefix) / "lib" / version / "site-packages")

    try:
        import site

        candidates.extend(Path(path).expanduser() for path in site.getsitepackages())
        candidates.append(Path(site.getusersitepackages()).expanduser())
    except Exception:
        pass

    candidates.append(
        Path.home()
        / ".local"
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    candidates.append(Path("/opt/miniconda3/envs/infinigen/lib/python3.11/site-packages"))

    seen: set[str] = set()
    existing: list[Path] = []
    for path in candidates:
        normalized = str(path)
        if normalized in seen or not path.exists():
            continue
        seen.add(normalized)
        existing.append(path)
    return existing


def _ensure_python_module(module_name: str, package_name: str | None = None) -> None:
    try:
        importlib.import_module(module_name)
        return
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise

    for path in _candidate_python_dependency_paths():
        module_path = path / module_name
        module_file = path / f"{module_name}.py"
        if not module_path.exists() and not module_file.exists():
            continue
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
        try:
            importlib.import_module(module_name)
            print(f"[InfinigenAgent] Loaded Python dependency '{module_name}' from {path}")
            return
        except ModuleNotFoundError as exc:
            if exc.name != module_name:
                raise

    package = package_name or module_name
    raise ModuleNotFoundError(
        f"Missing Python module '{module_name}'. Install '{package}' into the Python "
        "environment used by scripts/start_blender_agent.sh, or set "
        "INFINIGEN_AGENT_PYTHON_SITE_PACKAGES to a site-packages directory visible to Blender."
    )


def _configure_infinigen_once() -> None:
    global INFINIGEN_CONFIGURED
    if INFINIGEN_CONFIGURED:
        return
    _ensure_infinigen_on_path()
    _ensure_python_module("gin", "gin-config")
    try:
        from infinigen.core import init

        init.apply_gin_configs(
            ["infinigen_examples/configs_indoor", "infinigen_examples/configs_nature"],
            configs=[],
            overrides=[],
            skip_unknown=True,
        )
    except Exception as exc:
        print(f"[InfinigenAgent] Infinigen gin configuration warning: {exc}")
    INFINIGEN_CONFIGURED = True


def _resolve_factory(category_or_factory: str) -> tuple[str, Any]:
    _configure_infinigen_once()
    factory_path = ASSET_FACTORY_ALIASES.get(category_or_factory, category_or_factory)
    try:
        from infinigen.core.util.test_utils import import_item

        return factory_path, import_item(factory_path)
    except Exception:
        from infinigen_examples.generate_individual_assets import unified_asset_import

        cls, _asset_type = unified_asset_import(factory_path.split(".")[-1])
        return factory_path, cls


def _normalize_spawned_objects(asset: Any) -> list[bpy.types.Object]:
    if isinstance(asset, bpy.types.Object):
        return [asset]
    if isinstance(asset, (list, tuple)):
        return [item for item in asset if isinstance(item, bpy.types.Object)]
    return [bpy.context.active_object] if bpy.context.active_object else []


def _tag_asset_objects(root_objects: list[bpy.types.Object], category: str, factory_path: str) -> str:
    asset_id = f"asset_{uuid.uuid4().hex[:12]}"
    for root in root_objects:
        for obj in [root, *list(root.children_recursive)]:
            if not isinstance(obj, bpy.types.Object):
                continue
            obj["agent_asset_id"] = asset_id
            obj["agent_object_id"] = obj.get("agent_object_id") or f"obj_{uuid.uuid4().hex[:12]}"
            obj["agent_category"] = category
            obj["agent_factory"] = factory_path
    return asset_id


def _set_asset_metadata(
    asset: dict[str, Any],
    *,
    seed: int,
    source_prompt: str | None,
    edit_prompt: str | None,
    generation_script: str,
) -> None:
    for obj in _objects_for_asset(asset):
        obj["agent_seed"] = seed
        if source_prompt:
            obj["agent_source_prompt"] = source_prompt
        if edit_prompt:
            obj["agent_edit_prompt"] = edit_prompt
        obj["agent_generation_script"] = generation_script


def _spawn_infinigen_asset(
    category_or_factory: str,
    *,
    seed: int,
    location: Vector,
    scale: float,
    source_prompt: str | None = None,
    material_color: str | None = None,
) -> dict[str, Any]:
    factory_path, cls = _resolve_factory(category_or_factory)
    category = _category_from_asset_request(str(category_or_factory), factory_path)
    requested_scale = scale
    scale = _clamp(float(scale), MIN_SPAWN_SCALE, MAX_SPAWN_SCALE)

    factory = cls(seed)
    if hasattr(factory, "spawn_asset"):
        asset = factory.spawn_asset(seed)
    elif hasattr(factory, "create_asset"):
        asset = factory.create_asset()
    else:
        raise RuntimeError(f"{factory_path} has no spawn_asset/create_asset method")

    if hasattr(factory, "finalize_assets"):
        factory.finalize_assets(asset)

    root_objects = _normalize_spawned_objects(asset)
    if not root_objects:
        raise RuntimeError(f"{factory_path} did not return Blender objects")

    asset_id = _tag_asset_objects(root_objects, category, factory_path)
    bpy.context.view_layer.update()
    temp_asset = _resolve_asset(asset_id)
    bottom = Vector(temp_asset["bbox_min"])
    _move_asset(temp_asset, location - bottom)
    for root in root_objects:
        root.scale = root.scale * scale
    bpy.context.view_layer.update()
    temp_asset = _resolve_asset(asset_id)
    _set_asset_location_by_bbox_min(temp_asset, location)
    temp_asset = _resolve_asset(asset_id)
    max_dimension = MAX_ASSET_DIMENSIONS.get(category)
    final_asset = _fit_asset_to_max_dimension(
        temp_asset,
        max_dimension,
        preserve_bbox_min=location,
    )

    if material_color:
        for obj in _objects_for_asset(final_asset):
            if obj.type == "MESH" and obj.data:
                if not _apply_prompt_material(obj, material_color):
                    mat = _make_material(material_color, None)
                    obj.data.materials.clear()
                    obj.data.materials.append(mat)
        bpy.context.view_layer.update()
        final_asset = _resolve_asset(asset_id)

    physics = _apply_physics_rules(asset_id)
    final_asset = _resolve_asset(asset_id)

    script_path = _write_generation_script(
        asset_id=asset_id,
        category=category,
        factory_path=factory_path,
        seed=seed,
        scale=scale,
        location=[float(v) for v in location],
        material_color=material_color,
        source_prompt=source_prompt,
    )
    _set_asset_metadata(
        final_asset,
        seed=seed,
        source_prompt=source_prompt,
        edit_prompt=None,
        generation_script=script_path,
    )

    return {
        "object_id": asset_id,
        "category": category,
        "factory": factory_path,
        "root_names": [obj.name for obj in root_objects],
        "bbox_min": final_asset["bbox_min"],
        "bbox_max": final_asset["bbox_max"],
        "generation_script": script_path,
        "requested_scale": requested_scale,
        "scale": scale,
        "max_dimension": max_dimension,
        "physics": physics,
    }


def cmd_ping(_payload: dict[str, Any]) -> dict[str, Any]:
    return {"message": "pong", "host": HOST, "port": PORT, "blend_path": bpy.data.filepath}


def cmd_set_agent_status(payload: dict[str, Any]) -> dict[str, Any]:
    return _set_agent_status(
        str(payload.get("state", "idle")),
        str(payload.get("message", "")),
        run_id=payload.get("run_id") or None,
        operation=payload.get("operation") or None,
    )


def cmd_get_agent_status(_payload: dict[str, Any]) -> dict[str, Any]:
    _sync_scene_agent_status()
    return dict(AGENT_STATUS)


def cmd_cancel_agent_run(_payload: dict[str, Any]) -> dict[str, Any]:
    AGENT_STATUS["cancel_requested"] = True
    AGENT_STATUS["state"] = "cancelling"
    AGENT_STATUS["message"] = "已请求停止 Agent 运行"
    AGENT_STATUS["updated_at"] = time.time()
    _sync_scene_agent_status()
    return dict(AGENT_STATUS)


def cmd_get_scene_info(_payload: dict[str, Any]) -> dict[str, Any]:
    objects = []
    for obj in bpy.context.scene.objects:
        objects.append(
            {
                "name": obj.name,
                "type": obj.type,
                "location": [float(v) for v in obj.location],
                "rotation": [float(v) for v in obj.rotation_euler],
                "scale": [float(v) for v in obj.scale],
                "category": obj.get("agent_category"),
                "object_id": obj.get("agent_object_id"),
                "asset_id": obj.get("agent_asset_id"),
            }
        )
    return {
        "name": bpy.context.scene.name,
        "blend_path": bpy.data.filepath,
        "object_count": len(bpy.context.scene.objects),
        "mesh_count": sum(1 for obj in bpy.context.scene.objects if obj.type == "MESH"),
        "camera": bpy.context.scene.camera.name if bpy.context.scene.camera else None,
        "objects": objects,
    }


def cmd_rebuild_scene_index(payload: dict[str, Any]) -> dict[str, Any]:
    return _build_scene_index(payload.get("save_path"))


def cmd_query_objects(payload: dict[str, Any]) -> dict[str, Any]:
    matches = _query_assets(payload.get("text", ""), payload.get("category"))
    return {"matches": matches, "count": len(matches)}


def cmd_open_blend(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"]).expanduser()
    if not path.exists():
        raise FileNotFoundError(path)
    bpy.ops.wm.open_mainfile(filepath=str(path))
    return {"path": str(path), "message": "Opened blend file"}


def cmd_save_blend(payload: dict[str, Any]) -> dict[str, Any]:
    path = payload.get("path") or bpy.data.filepath
    if not path:
        path = str(Path.cwd() / "scene.blend")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    return {"path": str(path), "message": "Saved blend file"}


def cmd_add_infinigen_asset(payload: dict[str, Any]) -> dict[str, Any]:
    category_or_factory = payload.get("category_or_factory") or payload.get("category") or "desk"
    seed = int(payload.get("seed", 0))
    location = Vector(payload.get("location", [0.0, 0.0, 0.0]))
    factory_path = ASSET_FACTORY_ALIASES.get(str(category_or_factory).lower(), str(category_or_factory))
    category = _category_from_asset_request(str(category_or_factory), factory_path)
    scale = (
        float(payload["scale"])
        if "scale" in payload
        else DEFAULT_ASSET_SCALES.get(category, 1.0)
    )
    source_prompt = payload.get("source_prompt") or payload.get("prompt")
    material_color = _color_from_prompt(str(source_prompt or ""), payload.get("color"))
    return _spawn_infinigen_asset(
        str(category_or_factory),
        seed=seed,
        location=location,
        scale=scale,
        source_prompt=source_prompt,
        material_color=material_color,
    )


def cmd_edit_generated_asset(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = str(payload.get("prompt") or payload.get("edit_prompt") or "")
    target_ref = payload.get("target")
    if not target_ref and prompt:
        target_ref = prompt

    old_asset = _resolve_asset(target_ref)
    factory_path = old_asset.get("factory") or _category_from_text(old_asset.get("category", "object"))
    seed = int(payload.get("seed", old_asset.get("generation", {}).get("seed") or 0))
    material_color = _color_from_prompt(prompt, payload.get("color"))
    old_bbox_min = Vector(old_asset["bbox_min"])
    old_dims = Vector(old_asset["dimensions"])

    new_asset = _spawn_infinigen_asset(
        str(factory_path),
        seed=seed,
        location=old_bbox_min,
        scale=1.0,
        source_prompt=old_asset.get("generation", {}).get("source_prompt"),
        material_color=material_color,
    )

    current_new = _resolve_asset(new_asset["object_id"])
    new_dims = Vector(current_new["dimensions"])
    ratios = [
        old_dims[i] / new_dims[i]
        for i in range(3)
        if new_dims[i] > 1e-6 and old_dims[i] > 1e-6
    ]
    fit_scale = min(ratios) if ratios else 1.0
    if payload.get("preserve_size", True):
        for obj in _root_objects_for_asset(current_new):
            obj.scale = obj.scale * fit_scale
        bpy.context.view_layer.update()
        current_new = _resolve_asset(new_asset["object_id"])

    _set_asset_location_by_bbox_min(current_new, old_bbox_min)
    current_new = _resolve_asset(new_asset["object_id"])

    script_path = _write_generation_script(
        asset_id=new_asset["object_id"],
        category=current_new["category"],
        factory_path=str(factory_path),
        seed=seed,
        scale=fit_scale,
        location=[float(v) for v in old_bbox_min],
        material_color=material_color,
        source_prompt=prompt,
    )
    _set_asset_metadata(
        current_new,
        seed=seed,
        source_prompt=old_asset.get("generation", {}).get("source_prompt"),
        edit_prompt=prompt,
        generation_script=script_path,
    )

    old_objects = _objects_for_asset(old_asset)
    for obj in old_objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.view_layer.update()
    physics = _apply_physics_rules(new_asset["object_id"])
    final_asset = _resolve_asset(new_asset["object_id"])

    return {
        "message": f"Edited {old_asset['name']} via generation script and replaced it with {final_asset['name']}",
        "old_object_id": old_asset["object_id"],
        "object_id": final_asset["object_id"],
        "category": final_asset["category"],
        "factory": factory_path,
        "edit_prompt": prompt,
        "material_color": material_color,
        "generation_script": script_path,
        "bbox_min": final_asset["bbox_min"],
        "bbox_max": final_asset["bbox_max"],
        "physics": physics,
        "deleted_count": len(old_objects),
    }


def cmd_move_object(payload: dict[str, Any]) -> dict[str, Any]:
    asset = _resolve_asset(payload.get("target"))
    direction = payload.get("direction", "right")
    distance = float(payload.get("distance", 0.3))
    delta = _direction_vector(direction) * distance
    _move_asset(asset, delta)
    physics = _apply_physics_rules(asset["object_id"])
    return {
        "message": f"Moved {asset['name']} {direction} by {distance}m",
        "object_id": asset["object_id"],
        "physics": physics,
    }


def cmd_scale_object(payload: dict[str, Any]) -> dict[str, Any]:
    asset = _resolve_asset(payload.get("target"))
    requested_factor = float(payload.get("factor", 1.2))
    factor = _clamp(requested_factor, MIN_SCALE_FACTOR, MAX_SCALE_FACTOR)
    for obj in _root_objects_for_asset(asset):
        obj.scale = obj.scale * factor
    bpy.context.view_layer.update()
    physics = _apply_physics_rules(asset["object_id"])
    return {
        "message": f"Scaled {asset['name']} by {factor}",
        "object_id": asset["object_id"],
        "requested_factor": requested_factor,
        "factor": factor,
        "physics": physics,
    }


def cmd_rotate_object(payload: dict[str, Any]) -> dict[str, Any]:
    asset = _resolve_asset(payload.get("target"))
    axis = payload.get("axis", "z").lower()
    angle = math.radians(float(payload.get("angle_degrees", 90)))
    axis_index = {"x": 0, "y": 1, "z": 2}.get(axis, 2)
    for obj in _root_objects_for_asset(asset):
        obj.rotation_euler[axis_index] += angle
    bpy.context.view_layer.update()
    physics = _apply_physics_rules(asset["object_id"])
    return {
        "message": f"Rotated {asset['name']} around {axis} by {math.degrees(angle):.1f} degrees",
        "object_id": asset["object_id"],
        "physics": physics,
    }


def cmd_delete_object(payload: dict[str, Any]) -> dict[str, Any]:
    asset = _resolve_asset(payload.get("target"))
    objects = _objects_for_asset(asset)
    for obj in objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    return {"message": f"Deleted {asset['name']}", "object_id": asset["object_id"], "deleted_count": len(objects)}


def cmd_set_material(payload: dict[str, Any]) -> dict[str, Any]:
    asset = _resolve_asset(payload.get("target"))
    material = payload.get("color")
    material_name = payload.get("material_name")
    mat = None
    changed = 0
    for obj in _objects_for_asset(asset):
        if obj.type != "MESH" or not obj.data:
            continue
        if _apply_prompt_material(obj, material, material_name):
            changed += 1
            continue
        if mat is None:
            mat = _make_material(material, material_name)
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        changed += 1
    assigned = material_name or material or (mat.name if mat else "material")
    return {"message": f"Assigned material {assigned} to {asset['name']}", "object_id": asset["object_id"], "mesh_count": changed}


def cmd_place_on(payload: dict[str, Any]) -> dict[str, Any]:
    source = _resolve_asset(payload.get("source"))
    target = _resolve_asset(payload.get("target"))
    source_dims = Vector(source["dimensions"])
    support_surface = _support_surface_for_place_on(target)
    surface_center = Vector(support_surface["center"])
    new_min = Vector(
        (
            surface_center.x - source_dims.x / 2,
            surface_center.y - source_dims.y / 2,
            support_surface["z"],
        )
    )
    _set_asset_location_by_bbox_min(source, new_min)
    physics = _apply_physics_rules(source["object_id"])
    return {
        "message": f"Placed {source['name']} on {target['name']}",
        "source_id": source["object_id"],
        "target_id": target["object_id"],
        "support_surface": support_surface,
        "physics": physics,
    }


def cmd_place_near(payload: dict[str, Any]) -> dict[str, Any]:
    source = _resolve_asset(payload.get("source"))
    target = _resolve_asset(payload.get("target"))
    side = payload.get("side", "right")
    gap = float(payload.get("gap", 0.2))
    source_dims = Vector(source["dimensions"])
    target_min = Vector(target["bbox_min"])
    target_max = Vector(target["bbox_max"])
    target_center = Vector(target["center"])
    placement_z = target_min.z
    target_support = _find_supporting_asset(target, _build_scene_index()["assets"])
    if target_support is not None:
        placement_z = target["bbox_min"][2]

    if side == "left":
        new_min = Vector((target_min.x - source_dims.x - gap, target_center.y - source_dims.y / 2, placement_z))
    elif side == "front":
        new_min = Vector((target_center.x - source_dims.x / 2, target_min.y - source_dims.y - gap, placement_z))
    elif side == "back":
        new_min = Vector((target_center.x - source_dims.x / 2, target_max.y + gap, placement_z))
    else:
        new_min = Vector((target_max.x + gap, target_center.y - source_dims.y / 2, placement_z))

    _set_asset_location_by_bbox_min(source, new_min)
    physics = _apply_physics_rules(source["object_id"])
    return {
        "message": f"Placed {source['name']} near {target['name']} on {side}",
        "source_id": source["object_id"],
        "target_id": target["object_id"],
        "placement_z": float(placement_z),
        "target_support_id": target_support["object_id"] if target_support else None,
        "physics": physics,
    }


def cmd_place_against_wall(payload: dict[str, Any]) -> dict[str, Any]:
    source = _resolve_asset(payload.get("target"))
    wall_ref = payload.get("wall") or source["relations"].get("nearest_wall") or "wall"
    wall = _resolve_asset(wall_ref)
    gap = float(payload.get("gap", 0.05))
    source_dims = Vector(source["dimensions"])
    wall_min = Vector(wall["bbox_min"])
    wall_max = Vector(wall["bbox_max"])
    wall_center = Vector(wall["center"])

    wall_x_thin = (wall_max.x - wall_min.x) < (wall_max.y - wall_min.y)
    if wall_x_thin:
        x = wall_max.x + gap
        new_min = Vector((x, wall_center.y - source_dims.y / 2, wall_min.z))
    else:
        y = wall_max.y + gap
        new_min = Vector((wall_center.x - source_dims.x / 2, y, wall_min.z))
    _set_asset_location_by_bbox_min(source, new_min)
    physics = _apply_physics_rules(source["object_id"])
    return {
        "message": f"Placed {source['name']} against {wall['name']}",
        "source_id": source["object_id"],
        "wall_id": wall["object_id"],
        "physics": physics,
    }


def cmd_apply_physics_rules(payload: dict[str, Any]) -> dict[str, Any]:
    return _apply_physics_rules(payload.get("target"))


def cmd_adjust_existing_light(payload: dict[str, Any]) -> dict[str, Any]:
    target = payload.get("target")
    light_ref = payload.get("light") or payload.get("light_name")
    light = _resolve_light(str(light_ref) if light_ref else None)
    subjects = _camera_agent_subject_objects(str(target) if target else None)
    bbox_min, bbox_max, center = _subject_bounds(subjects)
    dimensions = bbox_max - bbox_min
    span = max(1.0, float(max(dimensions.x, dimensions.y, dimensions.z)))

    camera = _ensure_camera()
    horizontal = camera.location - center
    horizontal.z = 0.0
    if horizontal.length <= 1e-6:
        horizontal = Vector((0.0, -1.0, 0.0))
    horizontal.normalize()

    height = float(payload.get("height", max(2.0, span * 1.4)))
    distance = float(payload.get("distance", max(1.2, span * 0.8)))
    new_location = center + horizontal * distance + Vector((0.0, 0.0, height))
    light.location = new_location

    if light.data:
        min_energy = float(payload.get("min_energy", 900.0))
        if hasattr(light.data, "energy"):
            light.data.energy = max(float(getattr(light.data, "energy", 0.0)), min_energy)
        if getattr(light.data, "type", "") == "AREA" and hasattr(light.data, "size"):
            light.data.size = max(float(getattr(light.data, "size", 1.0)), span * 0.9)

    _look_at(light, center)
    bpy.context.view_layer.update()
    return {
        "message": f"Adjusted existing Light {light.name} for scene visibility",
        "light": light.name,
        "target": target,
        "location": [float(v) for v in light.location],
        "rotation_euler": [float(v) for v in light.rotation_euler],
        "energy": float(getattr(light.data, "energy", 0.0)) if light.data and hasattr(light.data, "energy") else None,
        "created_new_light": False,
    }


def _ensure_camera() -> bpy.types.Object:
    if bpy.context.scene.camera:
        return bpy.context.scene.camera
    bpy.ops.object.camera_add(location=(4, -6, 4), rotation=(math.radians(60), 0, math.radians(35)))
    camera = bpy.context.active_object
    bpy.context.scene.camera = camera
    return camera


def _camera_agent_subject_objects(target: str | None) -> list[bpy.types.Object]:
    if target:
        return _objects_for_asset(_resolve_asset(target))

    index = _build_scene_index()
    names: set[str] = set()
    for asset in index["assets"]:
        if asset.get("category") not in STRUCTURAL_CATEGORIES:
            names.update(asset.get("object_names", []))

    subjects = [obj for obj in bpy.context.scene.objects if obj.name in names]
    if subjects:
        return subjects

    return [
        obj
        for obj in bpy.context.scene.objects
        if obj.type not in {"CAMERA", "LIGHT"} and not obj.hide_render
    ]


def _subject_center(subjects: list[bpy.types.Object]) -> Vector:
    bbox_min, bbox_max = _bounds_for_objects(subjects)
    return (bbox_min + bbox_max) * 0.5


def _subject_bounds(subjects: list[bpy.types.Object]) -> tuple[Vector, Vector, Vector]:
    bbox_min, bbox_max = _bounds_for_objects(subjects)
    center = (bbox_min + bbox_max) * 0.5
    return bbox_min, bbox_max, center


def _existing_lights() -> list[bpy.types.Object]:
    return [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "LIGHT" and not obj.hide_get() and not obj.hide_render
    ]


def _resolve_light(ref: str | None = None) -> bpy.types.Object:
    lights = _existing_lights()
    if not lights:
        raise RuntimeError("No existing Light found in the scene")
    if ref:
        lowered = str(ref).lower()
        for light in lights:
            if lowered in light.name.lower() or lowered == str(light.get("agent_object_id", "")).lower():
                return light
    active = bpy.context.view_layer.objects.active
    if active and active.type == "LIGHT" and active in lights:
        return active
    return lights[0]


def _look_at(camera: bpy.types.Object, target: Vector) -> None:
    direction = target - camera.location
    if direction.length <= 1e-6:
        return
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _fit_camera_to_subjects(camera: bpy.types.Object, subjects: list[bpy.types.Object], target_fill: float) -> dict[str, Any]:
    bbox_min, bbox_max = _bounds_for_objects(subjects)
    center = (bbox_min + bbox_max) * 0.5
    radius = max(0.25, max((corner - center).length for corner in [bbox_min, bbox_max]))
    direction = center - camera.location
    if direction.length <= 1e-6:
        direction = Vector((0.6, -0.7, 0.45))
    direction.normalize()

    cam_data = camera.data
    angle_x = getattr(cam_data, "angle_x", cam_data.angle)
    angle_y = getattr(cam_data, "angle_y", cam_data.angle)
    fit_angle = max(0.1, min(angle_x, angle_y) * 0.5)
    distance = radius / (max(0.2, min(0.95, target_fill)) * math.tan(fit_angle))
    camera.location = center - direction * distance
    _look_at(camera, center)
    return {
        "center": [float(v) for v in center],
        "radius": float(radius),
        "distance": float(distance),
    }


def _camera_view_quality(subjects: list[bpy.types.Object], margin: float = 0.035) -> dict[str, Any]:
    from bpy_extras.object_utils import world_to_camera_view

    scene = bpy.context.scene
    camera = _ensure_camera()
    projected: list[tuple[float, float]] = []
    invisible: list[str] = []
    for obj in subjects:
        corners = _world_corners(obj)
        if not corners:
            continue
        obj_points = [world_to_camera_view(scene, camera, corner) for corner in corners]
        in_front = all(point.z > 0 for point in obj_points)
        in_frame = all(margin <= point.x <= 1.0 - margin and margin <= point.y <= 1.0 - margin for point in obj_points)
        if not in_front or not in_frame:
            invisible.append(obj.name)
        projected.extend((float(point.x), float(point.y)) for point in obj_points if point.z > 0)

    if not projected:
        return {
            "good": False,
            "reason": "no_subject_points_in_camera_view",
            "all_visible": False,
            "close_enough": False,
            "fill": [0.0, 0.0],
            "invisible_objects": [obj.name for obj in subjects],
        }

    xs = [point[0] for point in projected]
    ys = [point[1] for point in projected]
    fill_x = max(xs) - min(xs)
    fill_y = max(ys) - min(ys)
    fill = max(fill_x, fill_y)
    all_visible = not invisible and min(xs) >= margin and max(xs) <= 1.0 - margin and min(ys) >= margin and max(ys) <= 1.0 - margin
    close_enough = 0.48 <= fill <= 0.92
    good = all_visible and close_enough
    if not all_visible:
        reason = "not_all_objects_visible"
    elif not close_enough:
        reason = "camera_too_far" if fill < 0.48 else "camera_too_close"
    else:
        reason = "good"
    return {
        "good": good,
        "reason": reason,
        "all_visible": all_visible,
        "close_enough": close_enough,
        "fill": [float(fill_x), float(fill_y)],
        "projected_bbox": [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))],
        "invisible_objects": invisible[:20],
    }


def _render_camera_mask(path: Path, resolution: tuple[int, int], subjects: list[bpy.types.Object]) -> None:
    scene = bpy.context.scene
    hidden_states = [(obj, obj.hide_render) for obj in scene.objects]
    film_transparent = scene.render.film_transparent
    filepath = scene.render.filepath
    file_format = scene.render.image_settings.file_format
    color_mode = scene.render.image_settings.color_mode
    resolution_x = scene.render.resolution_x
    resolution_y = scene.render.resolution_y
    subject_names = {obj.name for obj in subjects}
    try:
        for obj in scene.objects:
            obj.hide_render = obj.name not in subject_names
        scene.render.film_transparent = True
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.resolution_x = int(resolution[0])
        scene.render.resolution_y = int(resolution[1])
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
    finally:
        for obj, hide_render in hidden_states:
            obj.hide_render = hide_render
        scene.render.film_transparent = film_transparent
        scene.render.image_settings.file_format = file_format
        scene.render.image_settings.color_mode = color_mode
        scene.render.resolution_x = resolution_x
        scene.render.resolution_y = resolution_y
        scene.render.filepath = filepath


def _alpha_bbox_from_image(path: Path, alpha_threshold: float = 0.02) -> dict[str, Any]:
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        width, height = image.size
        pixels = list(image.pixels)
        min_x, min_y = width, height
        max_x, max_y = -1, -1
        count = 0
        for y in range(height):
            row = y * width * 4
            for x in range(width):
                alpha = pixels[row + x * 4 + 3]
                if alpha > alpha_threshold:
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
                    count += 1
        if count == 0:
            raise RuntimeError("Camera agent could not find visible subject pixels in the render")
        return {
            "image_size": [int(width), int(height)],
            "bbox": [int(min_x), int(min_y), int(max_x), int(max_y)],
            "center": [((min_x + max_x) / 2) / width, ((min_y + max_y) / 2) / height],
            "fill": [((max_x - min_x + 1) / width), ((max_y - min_y + 1) / height)],
            "pixel_count": count,
        }
    finally:
        bpy.data.images.remove(image)


def _try_alpha_bbox_from_image(path: Path, alpha_threshold: float = 0.02) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return _alpha_bbox_from_image(path, alpha_threshold), None
    except Exception as exc:
        return None, str(exc)


def _move_camera_from_bbox(
    camera: bpy.types.Object,
    bbox: dict[str, Any],
    subject_center: Vector,
    target_fill: float,
    recenter_strength: float,
    zoom_strength: float,
) -> dict[str, Any]:
    quat = camera.matrix_world.to_quaternion()
    right = quat @ Vector((1, 0, 0))
    up = quat @ Vector((0, 1, 0))
    forward = quat @ Vector((0, 0, -1))
    to_subject = subject_center - camera.location
    distance = max(0.25, float(to_subject.dot(forward)))

    cam_data = camera.data
    image_w, image_h = bbox["image_size"]
    aspect = image_w / max(1, image_h)
    angle_y = getattr(cam_data, "angle_y", cam_data.angle)
    view_h = 2.0 * distance * math.tan(angle_y * 0.5)
    view_w = view_h * aspect

    center_x, center_y = bbox["center"]
    fill_x, fill_y = bbox["fill"]
    fill = max(fill_x, fill_y)
    offset_x = center_x - 0.5
    offset_y = center_y - 0.5

    lateral = right * (offset_x * view_w * recenter_strength)
    vertical = up * (offset_y * view_h * recenter_strength)
    if fill < target_fill:
        dolly_amount = distance * min(0.65, (target_fill - fill) / max(target_fill, 1e-6)) * zoom_strength
    else:
        dolly_amount = -distance * min(0.65, (fill - target_fill) / max(fill, 1e-6)) * zoom_strength
    dolly = forward * dolly_amount
    camera.location += lateral + vertical + dolly
    return {
        "distance": distance,
        "fill": fill,
        "offset": [offset_x, offset_y],
        "movement": [float(v) for v in (lateral + vertical + dolly)],
        "dolly": float(dolly_amount),
    }


def cmd_adjust_camera_from_render(payload: dict[str, Any]) -> dict[str, Any]:
    target = payload.get("target")
    output_path = payload.get("output_path")
    if not output_path:
        base = Path(bpy.data.filepath).parent if bpy.data.filepath else Path.cwd()
        output_path = str(base / "renders" / "camera_agent_preview.png")
    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)

    resolution = [
        int(payload.get("resolution_x", 768)),
        int(payload.get("resolution_y", 432)),
    ]
    target_fill = max(0.2, min(0.95, float(payload.get("target_fill", 0.72))))
    max_iterations = max(1, min(6, int(payload.get("max_iterations", 3))))
    tolerance = max(0.01, float(payload.get("tolerance", 0.06)))
    recenter_strength = max(0.0, min(1.0, float(payload.get("recenter_strength", 0.75))))
    zoom_strength = max(0.0, min(1.0, float(payload.get("zoom_strength", 0.65))))

    scene = bpy.context.scene
    camera = _ensure_camera()
    scene.camera = camera
    subjects = _camera_agent_subject_objects(str(target) if target else None)
    if not subjects:
        raise RuntimeError("Camera agent found no renderable subject objects")

    initial_quality = _camera_view_quality(subjects)
    fit_result = None
    if not initial_quality.get("good"):
        fit_result = _fit_camera_to_subjects(camera, subjects, target_fill)

    mask_path = output_path_obj.with_name(f"{output_path_obj.stem}_mask.png")
    steps: list[dict[str, Any]] = []
    subject_center = _subject_center(subjects)
    mask_error = None
    for _ in range(max_iterations):
        _render_camera_mask(mask_path, (resolution[0], resolution[1]), subjects)
        bbox, mask_error = _try_alpha_bbox_from_image(mask_path)
        if bbox is None:
            break
        movement = _move_camera_from_bbox(
            camera,
            bbox,
            subject_center,
            target_fill,
            recenter_strength,
            zoom_strength,
        )
        steps.append({"bbox": bbox, "camera_movement": movement})
        centered = abs(movement["offset"][0]) <= tolerance and abs(movement["offset"][1]) <= tolerance
        framed = abs(movement["fill"] - target_fill) <= tolerance
        if centered and framed:
            break

    if mask_error and not steps:
        print(f"[InfinigenAgent] Camera agent warning: {mask_error}; rendering without mask-based refinement")

    render_result = cmd_render_scene(
        {
            "output_path": str(output_path_obj),
            "resolution_x": int(payload.get("final_resolution_x", 1280)),
            "resolution_y": int(payload.get("final_resolution_y", 720)),
            "auto_adjust_camera": False,
        }
    )
    return {
        "message": "Camera adjusted from rendered image analysis",
        "target": target or "non_structural_scene_assets",
        "camera": camera.name,
        "camera_location": [float(v) for v in camera.location],
        "camera_rotation_euler": [float(v) for v in camera.rotation_euler],
        "initial_quality": initial_quality,
        "fit": fit_result,
        "final_quality": _camera_view_quality(subjects),
        "mask_path": str(mask_path),
        "mask_error": mask_error,
        "render": render_result,
        "steps": steps,
    }


def cmd_render_scene(payload: dict[str, Any]) -> dict[str, Any]:
    path = payload.get("path") or payload.get("output_path")
    if not path:
        base = Path(bpy.data.filepath).parent if bpy.data.filepath else Path.cwd()
        path = str(base / "renders" / "preview.png")
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    resolution = payload.get("resolution")
    if resolution is None:
        resolution = [
            int(payload.get("resolution_x", 1280)),
            int(payload.get("resolution_y", 720)),
        ]
    scene = bpy.context.scene
    camera = _ensure_camera()
    scene.camera = camera
    camera_adjustment = None
    if payload.get("auto_adjust_camera", True):
        subjects = _camera_agent_subject_objects(payload.get("camera_target"))
        if subjects:
            quality = _camera_view_quality(subjects)
            if not quality.get("good"):
                target_fill = max(0.2, min(0.95, float(payload.get("camera_target_fill", 0.72))))
                fit_result = _fit_camera_to_subjects(camera, subjects, target_fill)
                mask_path = path_obj.with_name(f"{path_obj.stem}_camera_check_mask.png")
                steps: list[dict[str, Any]] = []
                subject_center = _subject_center(subjects)
                mask_error = None
                for _ in range(max(1, min(4, int(payload.get("camera_max_iterations", 3))))):
                    _render_camera_mask(mask_path, (768, 432), subjects)
                    bbox, mask_error = _try_alpha_bbox_from_image(mask_path)
                    if bbox is None:
                        break
                    movement = _move_camera_from_bbox(camera, bbox, subject_center, target_fill, 0.75, 0.65)
                    steps.append({"bbox": bbox, "camera_movement": movement})
                    quality_after_step = _camera_view_quality(subjects)
                    if quality_after_step.get("good"):
                        break
                if mask_error:
                    print(f"[InfinigenAgent] Camera auto-adjust warning: {mask_error}; continuing render")
                camera_adjustment = {
                    "adjusted": True,
                    "before": quality,
                    "fit": fit_result,
                    "after": _camera_view_quality(subjects),
                    "mask_path": str(mask_path),
                    "mask_error": mask_error,
                    "steps": steps,
                }
            else:
                camera_adjustment = {"adjusted": False, "before": quality, "after": quality}
    scene.render.resolution_x = int(resolution[0])
    scene.render.resolution_y = int(resolution[1])
    scene.render.filepath = str(path_obj)
    bpy.ops.render.render(write_still=True)
    return {
        "path": str(path_obj),
        "saved_to": str(path_obj),
        "message": "Rendered preview",
        "camera_auto_adjust": camera_adjustment,
    }


COMMANDS = {
    "ping": cmd_ping,
    "set_agent_status": cmd_set_agent_status,
    "get_agent_status": cmd_get_agent_status,
    "cancel_agent_run": cmd_cancel_agent_run,
    "get_scene_info": cmd_get_scene_info,
    "rebuild_scene_index": cmd_rebuild_scene_index,
    "query_objects": cmd_query_objects,
    "open_blend": cmd_open_blend,
    "save_blend": cmd_save_blend,
    "add_infinigen_asset": cmd_add_infinigen_asset,
    "edit_generated_asset": cmd_edit_generated_asset,
    "move_object": cmd_move_object,
    "scale_object": cmd_scale_object,
    "rotate_object": cmd_rotate_object,
    "delete_object": cmd_delete_object,
    "set_material": cmd_set_material,
    "place_on": cmd_place_on,
    "place_near": cmd_place_near,
    "place_against_wall": cmd_place_against_wall,
    "apply_physics_rules": cmd_apply_physics_rules,
    "adjust_existing_light": cmd_adjust_existing_light,
    "adjust_camera_from_render": cmd_adjust_camera_from_render,
    "render_scene": cmd_render_scene,
}


class INFINIGEN_AGENT_OT_start_server(bpy.types.Operator):
    bl_idname = "infinigen_agent.start_server"
    bl_label = "Start Infinigen Agent Server"

    def execute(self, _context: bpy.types.Context) -> set[str]:
        start_server()
        return {"FINISHED"}


class INFINIGEN_AGENT_OT_stop_server(bpy.types.Operator):
    bl_idname = "infinigen_agent.stop_server"
    bl_label = "Stop Infinigen Agent Server"

    def execute(self, _context: bpy.types.Context) -> set[str]:
        stop_server()
        return {"FINISHED"}


class INFINIGEN_AGENT_OT_rebuild_index(bpy.types.Operator):
    bl_idname = "infinigen_agent.rebuild_index"
    bl_label = "Rebuild Scene Index"

    def execute(self, _context: bpy.types.Context) -> set[str]:
        result = _build_scene_index()
        self.report({"INFO"}, f"Indexed {result['asset_count']} assets")
        return {"FINISHED"}


class INFINIGEN_AGENT_OT_cancel_agent_run(bpy.types.Operator):
    bl_idname = "infinigen_agent.cancel_agent_run"
    bl_label = "Stop Agent Run"
    bl_description = "Request the UI/agent loop to stop at the next cancellation check"

    def execute(self, _context: bpy.types.Context) -> set[str]:
        cmd_cancel_agent_run({})
        self.report({"WARNING"}, "Requested Agent stop")
        return {"FINISHED"}


class INFINIGEN_AGENT_PT_panel(bpy.types.Panel):
    bl_label = "Infinigen Agent"
    bl_idname = "INFINIGEN_AGENT_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Infinigen"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.label(text=f"Socket: {HOST}:{PORT}")
        layout.label(text=f"Server: {'running' if SERVER else 'stopped'}")
        layout.operator("infinigen_agent.start_server")
        layout.operator("infinigen_agent.stop_server")

        layout.separator()
        _sync_scene_agent_status()
        state = getattr(context.scene, "agent_state", AGENT_STATUS.get("state", "idle"))
        message = getattr(context.scene, "agent_message", AGENT_STATUS.get("message", ""))
        operation = getattr(context.scene, "agent_operation", AGENT_STATUS.get("operation", ""))
        cancel_requested = getattr(
            context.scene,
            "agent_cancel_requested",
            AGENT_STATUS.get("cancel_requested", False),
        )
        layout.label(text=f"Agent: {state}")
        if operation:
            layout.label(text=f"Operation: {operation}")
        if message:
            layout.label(text=message)
        cancel_row = layout.row()
        cancel_row.enabled = state in {"running", "cancelling"} and not cancel_requested
        cancel_row.operator("infinigen_agent.cancel_agent_run", icon="CANCEL")

        layout.separator()
        layout.operator("infinigen_agent.rebuild_index")


CLASSES = (
    INFINIGEN_AGENT_OT_start_server,
    INFINIGEN_AGENT_OT_stop_server,
    INFINIGEN_AGENT_OT_rebuild_index,
    INFINIGEN_AGENT_OT_cancel_agent_run,
    INFINIGEN_AGENT_PT_panel,
)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.agent_state = bpy.props.StringProperty(default="idle")
    bpy.types.Scene.agent_message = bpy.props.StringProperty(default="Agent 空闲")
    bpy.types.Scene.agent_operation = bpy.props.StringProperty(default="")
    bpy.types.Scene.agent_cancel_requested = bpy.props.BoolProperty(default=False)
    _sync_scene_agent_status()
    if os.getenv("INFINIGEN_AGENT_NO_AUTOSTART") != "1":
        start_server()


def unregister() -> None:
    stop_server()
    for attr in (
        "agent_state",
        "agent_message",
        "agent_operation",
        "agent_cancel_requested",
    ):
        if hasattr(bpy.types.Scene, attr):
            delattr(bpy.types.Scene, attr)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
