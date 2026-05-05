"""Reproducible generation record for a GOSIM/Infinigen asset.
Run inside Blender with the GOSIM addon loaded if you want to replay it.
"""

import json

GENERATION = {
  "asset_id": "asset_75f91ea3642c",
  "category": "strawberry",
  "factory_path": "infinigen.assets.objects.fruits.FruitFactoryStrawberry",
  "seed": 0,
  "scale": 0.15,
  "location": [
    0.0,
    0.0,
    0.5
  ],
  "material_color": null,
  "source_prompt": null
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
