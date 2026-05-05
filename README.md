# Gosim2026-Paris

Standalone natural-language Blender agent for editing Infinigen scenes.

This project is now fully self-contained. It no longer depends on the external
`/Users/rason/Developer/GOSIM_HACKATHON/infinigen` directory or the empty
`Gosim2026-Paris-main/LLM-Blender-Agent` directory.

It contains three main parts:

- `src/`, `ui/`, and `app.py`: the agent, LLM providers, and Gradio UI adapted from `LLM-Blender-Agent`.
- `blender_addon/` and `addon.py`: the Blender addon entry point, replacing the original Rodin/Hunyuan3D flow with an Infinigen-aware socket server.
- `third_party/infinigen/`: vendored Infinigen source code and the Blender 4.2 app.

## Directory Layout

```text
Gosim2026-Paris/
  addon.py                         # Blender addon entry point; loads the Infinigen-aware addon
  app.py                           # Original LLM-Blender-Agent UI entry point
  src/                             # LLM-Blender-Agent agent / Blender client / LLM providers
  ui/                              # LLM-Blender-Agent Gradio UI
  blender_addon/
    gosim_infinigen_agent_addon.py # Blender socket server + scene index + Infinigen tools
  gosim_blender_agent/             # Extra CLI / offline planner / runner
  third_party/infinigen/           # Infinigen source + Blender.app
  scripts/
    start_blender_agent.sh
    start_ui.sh
  docs/
    ARCHITECTURE.md
```

## Installation

```bash
cd /Users/rason/Developer/GOSIM_HACKATHON/Gosim2026-Paris
conda activate infinigen
pip install -r requirements.txt
```

For editable installation:

```bash
pip install -e ".[ui,llm]"
```

## Start the Blender Addon Service

```bash
cd /Users/rason/Developer/GOSIM_HACKATHON/Gosim2026-Paris
conda activate infinigen
bash scripts/start_blender_agent.sh
```

By default, this script uses the bundled Blender binary:

```text
third_party/infinigen/Blender.app/Contents/MacOS/Blender
```

The addon listens on:

```text
127.0.0.1:9876
```

## Start the Agent UI

In another terminal:

```bash
cd /Users/rason/Developer/GOSIM_HACKATHON/Gosim2026-Paris
conda activate infinigen
bash scripts/start_ui.sh
```

Open:

```text
http://127.0.0.1:7860
```

The UI keeps the original LLM-Blender-Agent workflow for connection setup, model selection, chat, and render previews, but the tool functions now edit Infinigen scenes. The layout keeps the conversation on the left and scene information plus render output on the right. After each tool execution, the right-side views refresh automatically.

### UI Notes

The current web UI has been cleaned up for the Gradio/ModelScope Studio chat experience:

- The page uses a cleaner dark theme with consistent panel spacing and borders across the connection area, model initialization area, chat area, scene information area, and render preview area.
- Chat messages use stable left/right bubble alignment: user messages appear on the right, agent output appears on the left, each with explicit background and text colors.
- Plain-text user input is rendered as a normal text message. Multimodal message structures are used only when files are uploaded, avoiding invisible user messages caused by empty file payloads.
- Agent text replies, function-call notices, and tool results all trigger UI refreshes, reducing cases where streamed output or tool output is not displayed.
- Long text, JSON, and code blocks wrap or scroll horizontally to avoid breaking narrow layouts.
- The responsive layout supports different browser widths: desktop keeps the scene/render panel on the right, while smaller screens widen message bubbles for readability.
- The initialization area separates the two agent model choices: Code Generator edits the Blender scene through tools, while Visual Verifier reads render images and produces the next adjustment instruction.
- Advanced settings include an optional Visual Verifier loop. When enabled, each completed user instruction is rendered automatically, then the render image, user goal, and current scene information are sent to an independent verifier agent.
- `Visual Verifier max iterations` controls the maximum number of verifier plus Blender editing cycles. If the verifier decides the result is good enough, the loop exits early.
- When the verifier requests another adjustment, it produces a text instruction for the code generator to continue adjusting objects, camera, lighting, scale, rotation, material, or framing parameters. The agent then uses the existing Blender tools, renders again, and sends the new result back to the Visual Verifier.

## Current Agent Tools

The LLM can call:

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
- `adjust_camera_from_render`
- `render_scene`

The original Rodin, Hyper3D, and Hunyuan3D-2 model generation entry points are no longer exposed as primary features. The legacy-compatible `generate_3d_model` function now forwards to `add_infinigen_asset`.

### Camera Agent

`adjust_camera_from_render` first renders a transparent-background mask image inside Blender, reads the alpha-pixel bounding box, estimates the target center offset and image occupancy, then automatically pans or dollies the current camera and renders the final preview.

`render_scene` checks the camera view automatically before each formal render. A good view means:

- All non-structural assets are inside the camera frame.
- The subject occupies enough of the image, avoiding a camera that is too far away.

If the check fails, `render_scene` first aims and moves the camera closer based on the overall object bounding box, then uses transparent mask rendering to fine-tune centering and distance before producing the final render. The returned `camera_auto_adjust` data records whether adjustment happened, quality before and after adjustment, mask paths, and each movement step.

Optional parameters:

- `target`: object, category, or natural-language description to frame. If omitted, all non-structural scene assets are used.
- `target_fill`: target image occupancy, default `0.72`.
- `max_iterations`: number of camera-adjustment iterations based on render feedback, default `3`.
- `output_path`: final preview output path. If omitted, the image is saved as `renders/camera_agent_preview.png` beside the current blend file.
- `render_scene` additionally supports `auto_adjust_camera`, `camera_target`, and `camera_target_fill`; `auto_adjust_camera` defaults to `true`.

### Visual Verifier Agent

Visual Verifier is an independent agent and does not add new Blender socket commands. Configure separate LLM types for the two API call paths with `agents.code_generator` and `agents.visual_verifier`:

```json
{
  "agents": {
    "code_generator": {
      "model_type": "r9s_code"
    },
    "visual_verifier": {
      "model_type": "r9s_visual_verifier"
    }
  },
  "llm": {
    "r9s_code": {
      "provider": "r9s",
      "model": "deepseek-v4-pro",
      "api_base": "https://api.r9s.ai/v1"
    },
    "r9s_visual_verifier": {
      "provider": "r9s",
      "model": "claude-opus-4-6",
      "api_base": "https://api.r9s.ai/v1"
    }
  }
}
```

`model_type` can be a built-in provider name such as `r9s`, or a custom configuration key under `llm`, such as `r9s_code`. Custom configurations should explicitly set `provider` to select the underlying API adapter.

During UI initialization, the Code Generator model and Visual Verifier model can also be selected separately. The verifier input includes:

- The auto-rendered image path.
- The original natural-language user goal.
- The latest scene information text.

The verifier only judges whether the render is close to the goal and returns a structured result:

```json
{
  "done": false,
  "reason": "The subject is left of center and the lighting is too dark.",
  "instruction": "Move the camera slightly to the right and increase the existing main light intensity so the desk and desk lamp are centered."
}
```

If `done=true`, the loop exits early. If `done=false`, `instruction` becomes the next Code Generator agent input. The Code Generator continues using the existing tools to edit the Blender scene, renders again, and sends the new render back to Visual Verifier. The loop count is controlled by `Visual Verifier max iterations` in the UI.

## Example Instructions

```text
add a desk
add a desk lamp
add an apple
add a pineapple
put the desk lamp on the desk
move the bed 0.3 meters to the right
scale the desk by 1.2
put the chair beside the bed
make the cabinet black
\editing make the table in the scene green
adjust the camera so the desk is centered
adjust the view so the main scene subject is larger
render preview
save the scene
```

`add_infinigen_asset` additionally supports the fruit assets under
`third_party/infinigen/infinigen/assets/objects/fruits`: `apple`, `blackberry`,
`green_coconut`, `hairy_coconut`, `durian`, `pineapple`, `starfruit`,
`strawberry`, and `compositional_fruit`. Chinese-language aliases for these fruit names are also parsed.

## CLI

Test the connection:

```bash
python -m gosim_blender_agent.cli ping
```

Open an existing `.blend` file:

```bash
python -m gosim_blender_agent.cli open /absolute/path/to/scene.blend
```

Natural-language commands:

```bash
python -m gosim_blender_agent.cli chat "add a desk"
python -m gosim_blender_agent.cli chat "put the desk lamp on the desk"
```

Generate a single-bedroom Infinigen scene:

```bash
python -m gosim_blender_agent.cli generate-bedroom \
  --output /Users/rason/Developer/GOSIM_HACKATHON/Gosim2026-Paris/outputs/bedroom/coarse \
  --seed 0
```

## Scene Index

The addon organizes the current scene into `gosim_scene_index.json` with fields including:

- `object_id`
- `category`
- `factory`
- `object_names`
- `location`
- `rotation_euler`
- `scale`
- `bbox_min`
- `bbox_max`
- `dimensions`
- `materials`
- `relations`
- `description`
- `generation`

For future RAG/vector DB integration, `description` and `relations` can be embedded directly.

Generated assets also write `generation_scripts/{asset_id}.py`, which tracks the factory, seed, prompt, and later editing changes.

## Self-Containment

Default paths point inside this project:

- Infinigen root: `third_party/infinigen`
- Blender binary: `third_party/infinigen/Blender.app/Contents/MacOS/Blender`
- Blender addon: `addon.py`

As long as this directory is copied completely and the Python dependencies are installed, no external project directories are required.
