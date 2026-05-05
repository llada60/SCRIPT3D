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


ASSET_SPECS: tuple[AssetSpec, ...] = (
    AssetSpec(
        "bed",
        "infinigen.assets.objects.seating.BedFactory",
        ("bed", "床", "卧床", "双人床"),
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
        ("apple", "苹果"),
    ),
    AssetSpec(
        "blackberry",
        "infinigen.assets.objects.fruits.FruitFactoryBlackberry",
        ("blackberry", "黑莓"),
    ),
    AssetSpec(
        "green_coconut",
        "infinigen.assets.objects.fruits.FruitFactoryCoconutgreen",
        ("green coconut", "coconutgreen", "青椰子", "椰青"),
    ),
    AssetSpec(
        "hairy_coconut",
        "infinigen.assets.objects.fruits.FruitFactoryCoconuthairy",
        ("hairy coconut", "coconuthairy", "coconut", "毛椰子", "椰子"),
    ),
    AssetSpec(
        "durian",
        "infinigen.assets.objects.fruits.FruitFactoryDurian",
        ("durian", "榴莲"),
    ),
    AssetSpec(
        "pineapple",
        "infinigen.assets.objects.fruits.FruitFactoryPineapple",
        ("pineapple", "菠萝", "凤梨"),
    ),
    AssetSpec(
        "starfruit",
        "infinigen.assets.objects.fruits.FruitFactoryStarfruit",
        ("starfruit", "star fruit", "杨桃"),
    ),
    AssetSpec(
        "strawberry",
        "infinigen.assets.objects.fruits.FruitFactoryStrawberry",
        ("strawberry", "草莓"),
    ),
    AssetSpec(
        "compositional_fruit",
        "infinigen.assets.objects.fruits.FruitFactoryCompositional",
        ("compositional fruit", "mixed fruit", "组合水果", "复合水果"),
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
