"""Semantic aliases for Infinigen asset factories.

The registry intentionally maps natural-language categories to Infinigen factory
classes instead of external text-to-3D services. The Blender addon resolves these
strings with Infinigen's own import helpers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AssetSpec:
    category: str
    factory: str
    aliases: tuple[str, ...]
    default_scale: float = 1.0


@dataclass(frozen=True)
class MaterialSpec:
    category: str
    material: str
    aliases: tuple[str, ...]


ASSET_SPECS: tuple[AssetSpec, ...] = (
    AssetSpec(
        "bed",
        "infinigen.assets.objects.seating.BedFactory",
        ("bed", "床", "卧床", "双人床"),
    ),
    AssetSpec(
        "bed_frame",
        "infinigen.assets.objects.seating.BedFrameFactory",
        ("bed frame", "bedframe"),
    ),
    AssetSpec(
        "mattress",
        "infinigen.assets.objects.seating.MattressFactory",
        ("mattress",),
    ),
    AssetSpec(
        "pillow",
        "infinigen.assets.objects.seating.PillowFactory",
        ("pillow", "cushion"),
        default_scale=0.35,
    ),
    AssetSpec(
        "desk",
        "infinigen.assets.objects.shelves.SimpleDeskFactory",
        ("desk", "书桌", "桌子", "工作桌", "办公桌"),
    ),
    AssetSpec(
        "table",
        "infinigen.assets.objects.tables.TableDiningFactory",
        ("table", "餐桌", "大桌子"),
    ),
    AssetSpec(
        "side_table",
        "infinigen.assets.objects.tables.SideTableFactory",
        ("side table", "nightstand", "床头柜", "边几", "小桌子"),
    ),
    AssetSpec(
        "coffee_table",
        "infinigen.assets.objects.tables.CoffeeTableFactory",
        ("coffee table", "茶几"),
    ),
    AssetSpec(
        "desk_lamp",
        "infinigen.assets.objects.lamp.DeskLampFactory",
        ("desk lamp", "lamp", "台灯", "灯"),
    ),
    AssetSpec(
        "floor_lamp",
        "infinigen.assets.objects.lamp.FloorLampFactory",
        ("floor lamp", "落地灯"),
    ),
    AssetSpec(
        "chair",
        "infinigen.assets.objects.seating.chairs.ChairFactory",
        ("chair", "椅子", "座椅"),
    ),
    AssetSpec(
        "bar_chair",
        "infinigen.assets.objects.seating.chairs.BarChairFactory",
        ("bar chair", "bar stool", "stool"),
    ),
    AssetSpec(
        "office_chair",
        "infinigen.assets.objects.seating.chairs.OfficeChairFactory",
        ("office chair", "办公椅"),
    ),
    AssetSpec(
        "sofa",
        "infinigen.assets.objects.seating.SofaFactory",
        ("sofa", "沙发"),
    ),
    AssetSpec(
        "armchair",
        "infinigen.assets.objects.seating.ArmChairFactory",
        ("armchair", "arm chair", "lounge chair"),
    ),
    AssetSpec(
        "beverage_fridge",
        "infinigen.assets.objects.appliances.BeverageFridgeFactory",
        ("beverage fridge", "drink fridge", "mini fridge", "fridge"),
    ),
    AssetSpec(
        "dishwasher",
        "infinigen.assets.objects.appliances.DishwasherFactory",
        ("dishwasher",),
    ),
    AssetSpec(
        "microwave",
        "infinigen.assets.objects.appliances.MicrowaveFactory",
        ("microwave", "microwave oven"),
    ),
    AssetSpec(
        "oven",
        "infinigen.assets.objects.appliances.OvenFactory",
        ("oven",),
    ),
    AssetSpec(
        "tv",
        "infinigen.assets.objects.appliances.TVFactory",
        ("tv", "television"),
    ),
    AssetSpec(
        "monitor",
        "infinigen.assets.objects.appliances.MonitorFactory",
        ("monitor", "computer monitor", "display"),
    ),
    AssetSpec(
        "cabinet",
        "infinigen.assets.objects.shelves.SingleCabinetFactory",
        ("cabinet", "柜子", "储物柜"),
    ),
    AssetSpec(
        "bookcase",
        "infinigen.assets.objects.shelves.SimpleBookcaseFactory",
        ("bookcase", "bookshelf", "书架"),
    ),
    AssetSpec(
        "rug",
        "infinigen.assets.objects.elements.RugFactory",
        ("rug", "地毯"),
    ),
    AssetSpec(
        "plant",
        "infinigen.assets.objects.tableware.PlantContainerFactory",
        ("plant", "盆栽", "植物"),
    ),
    AssetSpec(
        "apple",
        "infinigen.assets.objects.fruits.FruitFactoryApple",
        ("apple", "苹果", "青苹果", "绿苹果"),
        default_scale=0.12,
    ),
    AssetSpec(
        "blackberry",
        "infinigen.assets.objects.fruits.FruitFactoryBlackberry",
        ("blackberry", "黑莓"),
        default_scale=0.06,
    ),
    AssetSpec(
        "green_coconut",
        "infinigen.assets.objects.fruits.FruitFactoryCoconutgreen",
        ("green coconut", "coconutgreen", "青椰子", "椰青"),
        default_scale=0.14,
    ),
    AssetSpec(
        "hairy_coconut",
        "infinigen.assets.objects.fruits.FruitFactoryCoconuthairy",
        ("hairy coconut", "coconuthairy", "coconut", "毛椰子", "椰子"),
        default_scale=0.14,
    ),
    AssetSpec(
        "durian",
        "infinigen.assets.objects.fruits.FruitFactoryDurian",
        ("durian", "榴莲"),
        default_scale=0.12,
    ),
    AssetSpec(
        "pineapple",
        "infinigen.assets.objects.fruits.FruitFactoryPineapple",
        ("pineapple", "菠萝", "凤梨"),
        default_scale=0.12,
    ),
    AssetSpec(
        "starfruit",
        "infinigen.assets.objects.fruits.FruitFactoryStarfruit",
        ("starfruit", "star fruit", "杨桃"),
        default_scale=0.10,
    ),
    AssetSpec(
        "strawberry",
        "infinigen.assets.objects.fruits.FruitFactoryStrawberry",
        ("strawberry", "草莓"),
        default_scale=0.15,
    ),
    AssetSpec(
        "compositional_fruit",
        "infinigen.assets.objects.fruits.FruitFactoryCompositional",
        ("compositional fruit", "mixed fruit", "组合水果", "复合水果"),
        default_scale=0.12,
    ),
)


MATERIAL_SPECS: tuple[MaterialSpec, ...] = (
    MaterialSpec(
        "wood",
        "infinigen.assets.materials.wood.Wood",
        ("wood", "wooden", "natural wood"),
    ),
    MaterialSpec(
        "hardwood_floor",
        "infinigen.assets.materials.wood.HardwoodFloor",
        ("hardwood floor", "hardwood flooring"),
    ),
    MaterialSpec(
        "table_wood",
        "infinigen.assets.materials.wood.TableWood",
        ("table wood",),
    ),
    MaterialSpec(
        "plywood",
        "infinigen.assets.materials.wood.BlondePlywood",
        ("plywood", "blonde plywood"),
    ),
    MaterialSpec(
        "white_plywood",
        "infinigen.assets.materials.wood.WhitePlywood",
        ("white plywood",),
    ),
    MaterialSpec(
        "black_plywood",
        "infinigen.assets.materials.wood.BlackPlywood",
        ("black plywood",),
    ),
    MaterialSpec(
        "wood_tile",
        "infinigen.assets.materials.wood.WoodTiles",
        ("wood tile", "wood tiles"),
    ),
    MaterialSpec(
        "ceramic",
        "infinigen.assets.materials.ceramic.Ceramic",
        ("ceramic", "glazed ceramic"),
    ),
    MaterialSpec(
        "brick",
        "infinigen.assets.materials.ceramic.Brick",
        ("brick", "ceramic brick"),
    ),
    MaterialSpec(
        "concrete",
        "infinigen.assets.materials.ceramic.Concrete",
        ("concrete",),
    ),
    MaterialSpec(
        "glass",
        "infinigen.assets.materials.ceramic.Glass",
        ("glass",),
    ),
    MaterialSpec(
        "marble",
        "infinigen.assets.materials.ceramic.Marble",
        ("marble",),
    ),
    MaterialSpec(
        "plaster",
        "infinigen.assets.materials.ceramic.Plaster",
        ("plaster",),
    ),
    MaterialSpec(
        "tile",
        "infinigen.assets.materials.ceramic.Tile",
        ("tile", "ceramic tile"),
    ),
    MaterialSpec(
        "advanced_tiles",
        "infinigen.assets.materials.tiles.advanced_tiles.apply",
        ("tiles", "advanced tiles", "patterned tiles"),
    ),
    MaterialSpec(
        "metal",
        "infinigen.assets.materials.metal.MetalBasic",
        ("metal", "metallic"),
    ),
    MaterialSpec(
        "aluminum",
        "infinigen.assets.materials.metal.Aluminum",
        ("aluminum", "aluminium"),
    ),
    MaterialSpec(
        "brushed_metal",
        "infinigen.assets.materials.metal.BrushedMetal",
        ("brushed metal",),
    ),
    MaterialSpec(
        "galvanized_metal",
        "infinigen.assets.materials.metal.GalvanizedMetal",
        ("galvanized metal",),
    ),
    MaterialSpec(
        "grained_metal",
        "infinigen.assets.materials.metal.GrainedMetal",
        ("grained metal", "polished metal"),
    ),
    MaterialSpec(
        "hammered_metal",
        "infinigen.assets.materials.metal.HammeredMetal",
        ("hammered metal",),
    ),
    MaterialSpec(
        "mirror",
        "infinigen.assets.materials.metal.Mirror",
        ("mirror", "mirrored metal"),
    ),
    MaterialSpec(
        "black_glass",
        "infinigen.assets.materials.metal.BlackGlass",
        ("black glass",),
    ),
    MaterialSpec(
        "black_metal",
        "infinigen.assets.materials.metal.BrushedBlackMetal",
        ("black metal", "brushed black metal"),
    ),
    MaterialSpec(
        "white_metal",
        "infinigen.assets.materials.metal.WhiteMetal",
        ("white metal",),
    ),
    MaterialSpec(
        "plastic",
        "infinigen.assets.materials.plastic.Plastic",
        ("plastic",),
    ),
    MaterialSpec(
        "black_plastic",
        "infinigen.assets.materials.plastic.BlackPlastic",
        ("black plastic",),
    ),
    MaterialSpec(
        "rough_plastic",
        "infinigen.assets.materials.plastic.PlasticRough",
        ("rough plastic",),
    ),
    MaterialSpec(
        "translucent_plastic",
        "infinigen.assets.materials.plastic.PlasticTranslucent",
        ("translucent plastic", "clear plastic"),
    ),
    MaterialSpec(
        "rubber",
        "infinigen.assets.materials.plastic.BumpyRubberFloor",
        ("rubber", "bumpy rubber"),
    ),
)


def _alias_matches(normalized: str, alias: str) -> bool:
    alias_lower = alias.lower()
    if re.search(r"[a-z0-9]", alias_lower):
        pattern = rf"(?<![a-z0-9]){re.escape(alias_lower)}(?![a-z0-9])"
        return re.search(pattern, normalized) is not None
    return alias_lower in normalized


def resolve_asset(text: str) -> AssetSpec | None:
    normalized = text.lower().strip()
    for spec in ASSET_SPECS:
        if normalized == spec.category or normalized == spec.factory.lower():
            return spec
        if any(_alias_matches(normalized, alias) for alias in spec.aliases):
            return spec
    return None


def resolve_material(text: str) -> MaterialSpec | None:
    normalized = text.lower().strip()
    best: tuple[int, MaterialSpec] | None = None
    for spec in MATERIAL_SPECS:
        if normalized == spec.category or normalized == spec.material.lower():
            return spec
        for alias in spec.aliases:
            if _alias_matches(normalized, alias):
                score = len(alias)
                if best is None or score > best[0]:
                    best = (score, spec)
    return best[1] if best else None


def registry_payload() -> list[dict[str, object]]:
    return [
        {
            "category": spec.category,
            "factory": spec.factory,
            "aliases": list(spec.aliases),
            "default_scale": spec.default_scale,
        }
        for spec in ASSET_SPECS
    ]
