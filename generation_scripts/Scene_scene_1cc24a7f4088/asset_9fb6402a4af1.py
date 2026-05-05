"""Reproducible generation record for a GOSIM/Infinigen asset.
Run inside Blender with the GOSIM addon loaded if you want to replay it.
"""

import json

GENERATION = {
  "object_id": "asset_9fb6402a4af1",
  "asset_id": "asset_9fb6402a4af1",
  "category": "apple",
  "factory_path": "infinigen.assets.objects.fruits.FruitFactoryApple",
  "seed": 0,
  "scale": 0.12,
  "location": [
    0.0,
    0.0,
    0.0
  ],
  "material_color": null,
  "source_prompt": null,
  "scene": "Scene_scene_1cc24a7f4088"
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
