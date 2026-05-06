# Architecture

This project integrates two roles:

- Infinigen provides procedural indoor scenes and furniture factories.
- The Blender agent layer provides natural-language interaction, a socket bridge,
  scene indexing, editing tools, and visual preview.

```mermaid
flowchart LR
    User["Natural language"] --> Planner["Planner / LLM adapter"]
    Planner --> Client["Python BlenderClient"]
    Client --> Socket["JSON socket 127.0.0.1:9876"]
    Socket --> Addon["Blender addon"]
    Addon --> Index["Scene graph / semantic index"]
    Addon --> Bpy["bpy transforms/materials/render"]
    Addon --> Factories["Infinigen factories"]
    Bpy --> Preview["Rendered preview"]
```

## Key Boundaries

The LLM or rule planner never receives raw `bpy` code execution rights. It emits
structured tool calls only. The Blender addon validates object references, resolves
semantic aliases through the scene index, performs geometry edits, and then writes
an updated `scene_index.json`.

## Scene Index

The index is generated inside Blender and saved next to the `.blend` file by
default. Each indexed asset contains:

- `object_id`
- `root_name`
- `category`
- `factory`
- `object_names`
- `location`
- `rotation_euler`
- `scale`
- `bbox_min`
- `bbox_max`
- `center`
- `dimensions`
- `materials`
- `relations`
- `description`

This supports both structured lookup and RAG-style semantic retrieval. The current
implementation stores JSON. A vector database can be added later by embedding each
asset's `description` plus relation text.

## Editing Tools

Implemented Blender commands:

- `get_scene_info`
- `rebuild_scene_index`
- `query_objects`
- `open_blend`
- `save_blend`
- `add_infinigen_asset`
- `edit_generated_asset`
- `move_object`
- `scale_object`
- `rotate_object`
- `delete_object`
- `set_material`
- `place_on`
- `place_near`
- `place_against_wall`
- `render_scene`

## Infinigen Generation

There are two generation paths:

1. Out-of-process scene generation through `infinigen_blender_agent.infinigen_runner`.
   This calls `python -m infinigen.launch_blender` inside the vendored
   `third_party/infinigen` copy.

2. In-Blender asset insertion through `add_infinigen_asset`.
   This imports Infinigen factory classes such as `BedFactory`,
   `SimpleDeskFactory`, `DeskLampFactory`, and fruit factories under
   `infinigen.assets.objects.fruits`, spawns the asset, tags it with agent metadata
   metadata, places it in the current scene, and refreshes the index.

## Generated Asset Editing

When an asset is generated in Blender, the addon records the factory path, seed,
source prompt, and a reproducible Python generation script path on the asset's
custom properties. The scene index exposes this as `generation`.

Messages starting with `\editing` are planned as `edit_generated_asset`. The
addon resolves the target asset through the scene index, rewrites the generation
record with the edit prompt, respawns the asset from the original factory,
applies supported edits such as material color, aligns the replacement to the
old asset's bounding box, and removes the old object group.

## Recommended Next Extensions

- Tighten the LLM prompt around the current Infinigen function schema.
- Add a persistent SQLite scene store.
- Add vector embeddings for asset descriptions and edit history.
- Add stronger collision checks before accepting placement.
- Add room/wall extraction tailored to Infinigen's indoor solver outputs.
