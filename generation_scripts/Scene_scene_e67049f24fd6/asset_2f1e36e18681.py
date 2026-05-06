"""Reproducible generation record for a Infinigen asset.
Run inside Blender with the Infinigen addon loaded if you want to replay it.
"""

import json

GENERATION = {
  "object_id": "asset_2f1e36e18681",
  "asset_id": "asset_2f1e36e18681",
  "category": "table",
  "factory_path": "infinigen.assets.objects.tables.TableDiningFactory",
  "seed": 0,
  "scale": 1.0,
  "location": [
    0.0,
    0.0,
    0.0
  ],
  "material_color": null,
  "source_prompt": null,
  "scene": "Scene_scene_e67049f24fd6"
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
