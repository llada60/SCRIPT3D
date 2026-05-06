"""Reproducible generation record for a Infinigen asset.
Run inside Blender with the Infinigen addon loaded if you want to replay it.
"""

import json

GENERATION = {
  "object_id": "asset_5dc67a6e18be",
  "asset_id": "asset_5dc67a6e18be",
  "category": "lamp",
  "factory_path": "lamp",
  "seed": 0,
  "scale": 1.0,
  "location": [
    4.076245307922363,
    1.0054539442062378,
    5.903861999511719
  ],
  "material_color": null,
  "source_prompt": "将光源能量提高到至少1000W，使场景更明亮",
  "scene": "Scene_scene_081397bb4e26"
}

def replay(client):
    result = client.add_infinigen_asset(
        category_or_factory=GENERATION['factory_path'],
        seed=GENERATION['seed'],
        location=tuple(GENERATION['location']),
        scale=GENERATION['scale'],
    )
    if GENERATION.get('material_color'):
        client.set_material(result['object_id'], color=GENERATION['material_color'])
    return result
