bl_info = {
    "name": "GOSIM Infinigen Agent",
    "author": "GOSIM Hackathon",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > GOSIM",
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


HOST = os.getenv("GOSIM_BLENDER_HOST", "127.0.0.1")
PORT = int(os.getenv("GOSIM_BLENDER_PORT", "9876"))
REQUEST_QUEUE: queue.Queue[tuple[dict[str, Any], threading.Event, dict[str, Any]]] = queue.Queue()
SERVER: socketserver.ThreadingTCPServer | None = None
SERVER_THREAD: threading.Thread | None = None
TIMER_REGISTERED = False
INFINIGEN_CONFIGURED = False


ASSET_FACTORY_ALIASES = {
    "bed": "infinigen.assets.objects.seating.BedFactory",
    "床": "infinigen.assets.objects.seating.BedFactory",
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
    "office_chair": "infinigen.assets.objects.seating.chairs.OfficeChairFactory",
    "sofa": "infinigen.assets.objects.seating.SofaFactory",
    "沙发": "infinigen.assets.objects.seating.SofaFactory",
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


CATEGORY_ALIASES = {
    "bed": ("bed", "床"),
    "desk": ("desk", "simpledesk", "书桌", "办公桌"),
    "table": ("table", "桌", "餐桌", "sidetable", "coffeetable"),
    "side_table": ("side_table", "sidetable", "nightstand", "床头柜", "边几"),
    "lamp": ("lamp", "light", "台灯", "灯"),
    "chair": ("chair", "椅"),
    "sofa": ("sofa", "沙发"),
    "cabinet": ("cabinet", "柜"),
    "bookcase": ("bookcase", "shelf", "书架"),
    "rug": ("rug", "地毯"),
    "plant": ("plant", "植物", "盆栽"),
    "apple": ("apple", "苹果"),
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
    "strawberry": 0.15,
}

PHYSICS_FLOOR_Z = 0.0
PHYSICS_GROUND_EPS = 0.03
PHYSICS_SUPPORT_EPS = 0.12
PHYSICS_COLLISION_EPS = 0.02
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
    "white": "white",
    "白": "white",
    "白色": "white",
    "black": "black",
    "黑": "black",
    "黑色": "black",
    "wood": "wood",
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
            else:
                slot["response"] = _ok(handler(payload))
        except Exception:
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

    print(f"[GOSIM] Blender agent server listening on {HOST}:{PORT}")
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
    if not obj.get("gosim_object_id"):
        obj["gosim_object_id"] = f"{prefix}_{uuid.uuid4().hex[:12]}"
    return str(obj["gosim_object_id"])


def _ensure_asset_id(obj: bpy.types.Object) -> str:
    if obj.get("gosim_asset_id"):
        return str(obj["gosim_asset_id"])
    obj["gosim_asset_id"] = f"asset_{uuid.uuid4().hex[:12]}"
    return str(obj["gosim_asset_id"])


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


def _generation_script_dir() -> Path:
    base = Path(bpy.data.filepath).parent if bpy.data.filepath else _project_root()
    path = base / "generation_scripts"
    path.mkdir(parents=True, exist_ok=True)
    return path


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
    payload = {
        "asset_id": asset_id,
        "category": category,
        "factory_path": factory_path,
        "seed": seed,
        "scale": scale,
        "location": location,
        "material_color": material_color,
        "source_prompt": source_prompt,
    }
    return (
        '"""Reproducible generation record for a GOSIM/Infinigen asset.\n'
        "Run inside Blender with the GOSIM addon loaded if you want to replay it.\n"
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
    path = _generation_script_dir() / f"{asset_id}.py"
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
        ("side_table", ("side_table", "sidetable", "nightstand", "床头柜")),
        ("lamp", ("desk_lamp", "floor_lamp", "desklamp", "floorlamp", "lamp", "台灯", "灯")),
        ("desk", ("simpledesk", "desk", "书桌")),
        ("bookcase", ("bookcase", "bookshelf", "书架")),
        ("cabinet", ("cabinet", "柜")),
        ("chair", ("officechair", "chair", "椅")),
        ("sofa", ("sofa", "沙发")),
        ("bed", ("bed", "床")),
        ("rug", ("rug", "地毯")),
        ("plant", ("plant", "植物")),
        ("blackberry", ("fruitfactoryblackberry", "blackberry", "黑莓")),
        ("green_coconut", ("fruitfactorycoconutgreen", "green_coconut", "coconutgreen", "green coconut", "青椰子", "椰青")),
        ("hairy_coconut", ("fruitfactorycoconuthairy", "hairy_coconut", "coconuthairy", "hairy coconut", "coconut", "毛椰子", "椰子")),
        ("durian", ("fruitfactorydurian", "durian", "榴莲")),
        ("pineapple", ("fruitfactorypineapple", "pineapple", "菠萝", "凤梨")),
        ("apple", ("fruitfactoryapple", "apple", "苹果")),
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
    explicit = root.get("gosim_category")
    if explicit:
        return str(explicit)
    factory = root.get("gosim_factory", "")
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
    if obj.get("gosim_asset_id"):
        current = obj
        while current.parent and current.parent.get("gosim_asset_id") == obj.get("gosim_asset_id"):
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
        asset_id = obj.get("gosim_asset_id")
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
            "factory": root.get("gosim_factory"),
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
                "script_path": root.get("gosim_generation_script"),
                "seed": root.get("gosim_seed"),
                "source_prompt": root.get("gosim_source_prompt"),
                "edit_prompt": root.get("gosim_edit_prompt"),
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
        save_path = str(base / "gosim_scene_index.json")
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
        z_gap = abs(float(asset["bbox_min"][2]) - float(other["bbox_max"][2]))
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
    if isinstance(color, (list, tuple)):
        rgba = tuple(float(v) for v in color[:4])
        if len(rgba) == 3:
            rgba = rgba + (1.0,)
    else:
        color_text = str(color or "")
        rgba = COLOR_MAP.get(color_text.lower(), COLOR_MAP.get(color_text, (0.8, 0.8, 0.8, 1.0)))
        if color_text.startswith("#") and len(color_text) in {7, 9}:
            rgba = tuple(int(color_text[i : i + 2], 16) / 255 for i in (1, 3, 5)) + (1.0,)
    name = material_name or f"GOSIM_{color or 'material'}"
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    node = mat.node_tree.nodes.get("Principled BSDF")
    if node:
        node.inputs["Base Color"].default_value = rgba
        node.inputs["Roughness"].default_value = 0.55
    return mat


def _color_from_prompt(prompt: str, explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    lowered = prompt.lower()
    hex_match = re.search(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?", prompt)
    if hex_match:
        return hex_match.group(0)
    for key, color in COLOR_ALIASES.items():
        if key.lower() in lowered:
            return color
    return None


def _ensure_infinigen_on_path() -> Path:
    candidates = [
        os.getenv("GOSIM_INFINIGEN_ROOT"),
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
    raise RuntimeError("Could not locate Infinigen root. Set GOSIM_INFINIGEN_ROOT.")


def _candidate_python_dependency_paths() -> list[Path]:
    candidates: list[Path] = []

    for env_name in ("GOSIM_PYTHON_SITE_PACKAGES", "PYTHONPATH"):
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
            print(f"[GOSIM] Loaded Python dependency '{module_name}' from {path}")
            return
        except ModuleNotFoundError as exc:
            if exc.name != module_name:
                raise

    package = package_name or module_name
    raise ModuleNotFoundError(
        f"Missing Python module '{module_name}'. Install '{package}' into the Python "
        "environment used by scripts/start_blender_agent.sh, or set "
        "GOSIM_PYTHON_SITE_PACKAGES to a site-packages directory visible to Blender."
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
        print(f"[GOSIM] Infinigen gin configuration warning: {exc}")
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
            obj["gosim_asset_id"] = asset_id
            obj["gosim_object_id"] = obj.get("gosim_object_id") or f"obj_{uuid.uuid4().hex[:12]}"
            obj["gosim_category"] = category
            obj["gosim_factory"] = factory_path
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
        obj["gosim_seed"] = seed
        if source_prompt:
            obj["gosim_source_prompt"] = source_prompt
        if edit_prompt:
            obj["gosim_edit_prompt"] = edit_prompt
        obj["gosim_generation_script"] = generation_script


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

    final_asset = _resolve_asset(asset_id)
    if material_color:
        mat = _make_material(material_color, None)
        for obj in _objects_for_asset(final_asset):
            if obj.type == "MESH" and obj.data:
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
        "physics": physics,
    }


def cmd_ping(_payload: dict[str, Any]) -> dict[str, Any]:
    return {"message": "pong", "host": HOST, "port": PORT, "blend_path": bpy.data.filepath}


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
                "category": obj.get("gosim_category"),
                "object_id": obj.get("gosim_object_id"),
                "asset_id": obj.get("gosim_asset_id"),
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
        path = str(Path.cwd() / "gosim_scene.blend")
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
    mat = _make_material(payload.get("color"), payload.get("material_name"))
    changed = 0
    for obj in _objects_for_asset(asset):
        if obj.type != "MESH" or not obj.data:
            continue
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        changed += 1
    return {"message": f"Assigned material {mat.name} to {asset['name']}", "object_id": asset["object_id"], "mesh_count": changed}


def cmd_place_on(payload: dict[str, Any]) -> dict[str, Any]:
    source = _resolve_asset(payload.get("source"))
    target = _resolve_asset(payload.get("target"))
    source_dims = Vector(source["dimensions"])
    target_center = Vector(target["center"])
    new_min = Vector(
        (
            target_center.x - source_dims.x / 2,
            target_center.y - source_dims.y / 2,
            target["bbox_max"][2],
        )
    )
    _set_asset_location_by_bbox_min(source, new_min)
    physics = _apply_physics_rules(source["object_id"])
    return {
        "message": f"Placed {source['name']} on {target['name']}",
        "source_id": source["object_id"],
        "target_id": target["object_id"],
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

    if side == "left":
        new_min = Vector((target_min.x - source_dims.x - gap, target_center.y - source_dims.y / 2, target_min.z))
    elif side == "front":
        new_min = Vector((target_center.x - source_dims.x / 2, target_min.y - source_dims.y - gap, target_min.z))
    elif side == "back":
        new_min = Vector((target_center.x - source_dims.x / 2, target_max.y + gap, target_min.z))
    else:
        new_min = Vector((target_max.x + gap, target_center.y - source_dims.y / 2, target_min.z))

    _set_asset_location_by_bbox_min(source, new_min)
    physics = _apply_physics_rules(source["object_id"])
    return {
        "message": f"Placed {source['name']} near {target['name']} on {side}",
        "source_id": source["object_id"],
        "target_id": target["object_id"],
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


def _ensure_camera() -> bpy.types.Object:
    if bpy.context.scene.camera:
        return bpy.context.scene.camera
    bpy.ops.object.camera_add(location=(4, -6, 4), rotation=(math.radians(60), 0, math.radians(35)))
    camera = bpy.context.active_object
    bpy.context.scene.camera = camera
    return camera


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
    scene.camera = _ensure_camera()
    scene.render.resolution_x = int(resolution[0])
    scene.render.resolution_y = int(resolution[1])
    scene.render.filepath = str(path_obj)
    bpy.ops.render.render(write_still=True)
    return {"path": str(path_obj), "saved_to": str(path_obj), "message": "Rendered preview"}


COMMANDS = {
    "ping": cmd_ping,
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
    "render_scene": cmd_render_scene,
}


class GOSIM_OT_start_server(bpy.types.Operator):
    bl_idname = "gosim.start_server"
    bl_label = "Start GOSIM Agent Server"

    def execute(self, _context: bpy.types.Context) -> set[str]:
        start_server()
        return {"FINISHED"}


class GOSIM_OT_stop_server(bpy.types.Operator):
    bl_idname = "gosim.stop_server"
    bl_label = "Stop GOSIM Agent Server"

    def execute(self, _context: bpy.types.Context) -> set[str]:
        stop_server()
        return {"FINISHED"}


class GOSIM_OT_rebuild_index(bpy.types.Operator):
    bl_idname = "gosim.rebuild_index"
    bl_label = "Rebuild Scene Index"

    def execute(self, _context: bpy.types.Context) -> set[str]:
        result = _build_scene_index()
        self.report({"INFO"}, f"Indexed {result['asset_count']} assets")
        return {"FINISHED"}


class GOSIM_PT_panel(bpy.types.Panel):
    bl_label = "GOSIM Agent"
    bl_idname = "GOSIM_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GOSIM"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.label(text=f"Socket: {HOST}:{PORT}")
        layout.label(text=f"Status: {'running' if SERVER else 'stopped'}")
        layout.operator("gosim.start_server")
        layout.operator("gosim.stop_server")
        layout.operator("gosim.rebuild_index")


CLASSES = (
    GOSIM_OT_start_server,
    GOSIM_OT_stop_server,
    GOSIM_OT_rebuild_index,
    GOSIM_PT_panel,
)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    if os.getenv("GOSIM_NO_AUTOSTART") != "1":
        start_server()


def unregister() -> None:
    stop_server()
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
