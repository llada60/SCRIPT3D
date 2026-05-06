"""Reproducible generation record for a Infinigen asset.
Run inside Blender with the Infinigen addon loaded if you want to replay it.
"""

import json

GENERATION = {
  "object_id": "asset_c7b55fe53d0d",
  "asset_id": "asset_c7b55fe53d0d",
  "category": "chair",
  "factory_path": "infinigen.assets.objects.seating.chairs.ChairFactory",
  "seed": 0,
  "scale": 1.0,
  "location": [
    0.0,
    0.0,
    0.0
  ],
  "material_color": null,
  "source_prompt": null,
  "scene": "Scene_scene_6cec2f08a982"
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
