"""Reproducible generation record for a GOSIM/Infinigen asset.
Run inside Blender with the GOSIM addon loaded if you want to replay it.
"""

import json

GENERATION = {
  "asset_id": "asset_92809b180101",
  "category": "side_table",
  "factory_path": "infinigen.assets.objects.tables.SideTableFactory",
  "seed": 0,
  "scale": 1.0,
  "location": [
    0.0,
    0.0,
    0.0
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
