"""Reproducible generation record for a GOSIM/Infinigen asset.
Run inside Blender with the GOSIM addon loaded if you want to replay it.
"""

import json

GENERATION = {
  "asset_id": "asset_a2ee5dd401b5",
  "category": "apple",
  "factory_path": "infinigen.assets.objects.fruits.FruitFactoryApple",
  "seed": 0,
  "scale": 1.0,
  "location": [
    0.2800000011920929,
    0.2800000011920929,
    0.699999988079071
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
