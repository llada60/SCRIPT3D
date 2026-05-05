# GOSIM Blender Agent API

The socket protocol remains compatible with LLM-Blender-Agent:

```json
{"type": "command_name", "params": {}}
```

The addon also accepts the newer internal form:

```json
{"command": "command_name", "payload": {}}
```

Responses include both shapes:

```json
{"ok": true, "status": "success", "result": {}}
```

## Commands

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
- `place_on`
- `place_near`
- `place_against_wall`
- `set_material`
- `delete_object`
- `render_scene`

`generate_3d_model` is kept only as a Python client compatibility wrapper and
forwards to `add_infinigen_asset`.

## Generated Asset Editing

Assets inserted through `add_infinigen_asset` are tagged with generation metadata
and a reproducible Python record under `generation_scripts/{asset_id}.py`.

`edit_generated_asset` accepts:

```json
{
  "target": "desk",
  "prompt": "Make the desk in the scene green.",
  "color": "green",
  "preserve_size": true
}
```

The addon resolves the target asset, updates the generation record, respawns the
asset from its original Infinigen factory, applies the requested edit, aligns the
new bounding box to the old position and size, and removes the old asset.
