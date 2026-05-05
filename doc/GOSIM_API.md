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

