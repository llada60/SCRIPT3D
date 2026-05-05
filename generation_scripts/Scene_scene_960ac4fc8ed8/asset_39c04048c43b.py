"""Reproducible generation record for a GOSIM/Infinigen asset.
Run inside Blender with the GOSIM addon loaded if you want to replay it.
"""

import json

GENERATION = {
  "object_id": "asset_39c04048c43b",
  "asset_id": "asset_39c04048c43b",
  "category": "object",
  "factory_path": "infinigen.assets.objects.tables.TableDiningFactory",
  "seed": 0,
  "scale": 1.0,
  "location": [
    0.0,
    0.0,
    0.0
  ],
  "material_color": null,
  "source_prompt": "change the table style",
  "scene": "Scene_scene_960ac4fc8ed8"
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
