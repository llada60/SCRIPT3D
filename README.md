# SCRIPT3D: Script-Backed, Controllable, and Reproducible 3D Asset Generation in Blender

<img src="pic_readme/icon.jpg" width="200" align="right" alt="SCRIPT3D Icon">

**SCRIPT3D** is a code-based multi-agent system for **controllable 3D asset generation and editing in Blender**.

Instead of producing a one-time black-box mesh, SCRIPT3D turns natural-language requests into **explicit Python generation scripts**, executable Blender operations, and persistent asset metadata. Every generated object can be inspected, traced, regenerated, edited, and reinserted into the scene with spatial consistency.

> **Core idea:** Treat every generated 3D asset not as a static mesh, but as a reproducible, script-backed object with metadata.


## Demo

<video controls src="pic_readme/SCRIPT3D.mp4" title="Title"></video>

Youtube link: https://youtu.be/YtQ2YAHLNBc

---

## Table of Contents

- [Key Innovation](#key-innovation)
- [Highlights](#highlights)
- [System Architecture](#system-architecture)
- [Agent System](#agent-system)
- [Technical Depth](#technical-depth)
- [Supported Workflows](#supported-workflows)
- [Supported Object Categories](#supported-object-categories)
- [Example End-to-End Scenario](#example-end-to-end-scenario)
- [Quick Start](#quick-start)
- [Run with UI](#run-with-ui)
- [Run with CLI](#run-with-cli)
- [Project Layout](#project-layout)
- [Summary](#summary)

---

## Key Innovation

<p align="center">
  <img src="pic_readme/motivation.png" alt="SCRIPT3D Motivation">
</p>

Most text-to-3D systems follow this pattern:

```text
prompt -> generated mesh
```

This is useful for visual generation, but weak for real 3D workflows.

If a user later asks:

```text
make the desk marble
replace the apple with a green one
put the lamp on the side table
```

a black-box mesh output gives the system very little reliable information about:

- how the asset was created,
- which factory or seed produced it,
- where it is located in the scene,
- what category it belongs to,
- how to regenerate a compatible replacement,
- how to preserve its size, pose, and scene relation.

SCRIPT3D solves this by making every asset **script-backed and metadata-backed**.

```text
prompt
  -> agent plan
  -> structured tool calls
  -> Python generation script
  -> Blender asset
  -> scene index
  -> render
  -> visual verification
  -> iterative correction
```

This makes 3D generation **inspectable, repeatable, editable, and scene-aware**.

---

## Highlights

<p align="center">
  <img src="pic_readme/highlight.png" alt="SCRIPT3D Highlights">
</p>

SCRIPT3D supports:

- natural-language 3D asset generation,
- script-backed asset records,
- reproducible regeneration through factory, seed, and script metadata,
- scene-aware editing and replacement,
- automatic scene indexing,
- object placement and spatial relation handling,
- visual verification with feedback,
- automatic camera adjustment,
- both UI and CLI workflows,
- deterministic fallback control without relying fully on an LLM.

---
## System Architecture

<p align="center">
  <img src="pic_readme/teaser.png" alt="SCRIPT3D System Architecture">
</p>

### Agent System

SCRIPT3D currently exposes two planning paths that share the same Blender command
surface:

- an LLM function-calling path used by the Gradio UI,
- a deterministic rule-planner path used by the CLI and useful for offline demos.

Both paths send structured JSON commands to the Blender addon. Neither path sends
arbitrary `bpy` code to Blender.

#### 1. Code Generator Agent / UI Agent

**Location:** `src/agent/agent.py`

The Code Generator Agent adapts the original LLM-Blender-Agent workflow to
Infinigen scene generation and editing. It gives the selected LLM a fixed list of
Blender/Infinigen tools and dispatches returned function calls through the
Blender client.

It is responsible for:

- converting natural-language requests into whitelisted function calls,
- enforcing the physical-rules prompt used for placement and scale sanity,
- routing generation, editing, placement, camera, render, and save operations,
- streaming tool progress and results into the UI,
- optionally using rendered-image feedback from the Visual Verifier Agent.

Example tool choices include:

```text
add_infinigen_asset
edit_generated_asset
place_on
place_near
apply_physics_rules
adjust_camera_from_render
render_scene
```

This keeps interaction flexible while preserving a narrow, auditable execution
surface.

---

#### 2. Rule Planner / CLI Agent

**Locations:**

```text
infinigen_blender_agent/planner.py
infinigen_blender_agent/agent.py
infinigen_blender_agent/cli.py
```

The Rule Planner provides a deterministic fallback path for demos, tests, and
environments without an LLM. It recognizes a practical set of English and Chinese
commands and converts them into the same `Action` schema used by the client.

It supports:

- scene inspection and indexing,
- opening and saving `.blend` files,
- asset generation,
- `\editing`-prefixed generated-asset edits,
- movement, scale, rotation, deletion, and material changes,
- `place_on`, `place_near`, and `place_against_wall`,
- automatic `apply_physics_rules` after spatial edits,
- render and camera-framing requests.

The CLI entry point uses this path through:

```text
python3 -m infinigen_blender_agent.cli chat "add a desk lamp on the desk"
```

---

#### 3. Optional JSON LLM Planner

**Location:** `infinigen_blender_agent/llm_planner.py`

This planner is an OpenAI-compatible JSON planner for the same CLI-side action
schema. It is configured through environment variables:

```text
INFINIGEN_AGENT_LLM_BASE_URL
INFINIGEN_AGENT_LLM_API_KEY
INFINIGEN_AGENT_LLM_MODEL
```

If the remote planner fails or returns unusable output, it falls back to the
deterministic `RulePlanner`.

---

#### 4. Blender Addon Agent

**Location:** `blender_addon/infinigen_agent_addon.py`

The Blender Addon Agent performs all Blender-side execution.

It is responsible for:

- starting the Blender socket server,
- receiving structured commands,
- executing operations on the Blender main thread,
- invoking Infinigen procedural asset factories,
- generating Blender objects,
- applying materials, scaling, rotation, placement, deletion, and physics cleanup,
- writing generation scripts,
- maintaining `scene_index.json`,
- rendering the scene,
- auto-adjusting cameras from transparent-mask renders,
- exposing live run status and cancellation hooks to the UI.

This agent is the bridge between high-level agent planning and real Blender execution.

---

#### 5. Visual Verifier Agent

**Location:** `src/agent/visual_verifier.py`

The Visual Verifier Agent evaluates rendered outputs and sends targeted correction feedback.

It checks:

- whether the prompt was satisfied,
- whether requested objects are visible,
- whether spatial relations are correct,
- whether objects overlap incorrectly,
- whether the scene is physically plausible,
- whether the render is useful for evaluation.

Example verifier output:

```json
{
  "done": false,
  "reason": "The apple overlaps the strawberry on the tabletop.",
  "instruction": "Move the apple slightly to the right of the strawberry and keep both objects on the tabletop."
}
```

This enables iterative improvement instead of one-shot generation.

---

#### 6. Camera Agent

**Location:** `blender_addon/infinigen_agent_addon.py`

The Camera Agent improves presentation quality by automatically adjusting scene framing.

Role:

- checks whether prompt-relevant objects are visible,
- renders a transparent mask,
- computes the alpha-pixel bounding box,
- recenters the camera,
- adjusts zoom based on object fill ratio,
- returns render metadata for debugging.

This helps ensure that generated assets are not only correct, but also clearly visible in the final demo.

---

## Technical Depth

SCRIPT3D combines several technical components into a unified pipeline:

```text
natural-language request
  -> LLM tool-call planner or deterministic rule planner
  -> typed Action / JSON command
  -> BlenderClient socket request
  -> Blender addon command handler
  -> Infinigen factory or bpy scene operation
  -> asset metadata + generation script
  -> scene_index.json
  -> render / camera adjustment / optional visual verification
```

### Script-Backed Generation

Every generated Infinigen asset is backed by a Python script written by the
Blender addon.

Instead of only saving a mesh, SCRIPT3D saves the process that created the mesh.

```text
generation_scripts/
  Scene_scene_081397bb4e26/
    asset_5dc67a6e18be.py
    asset_babe3c928956.py
```

Each script records the factory path, category, seed, location, scale, edit
prompt, and source prompt needed to respawn a compatible asset.

---

### Scene Indexing

SCRIPT3D maintains a structured scene index next to the current `.blend` file by
default:

```json
{
  "object_id": "asset_5dc67a6e18be",
  "root_name": "agent_asset_desk_5dc67a6e18be",
  "category": "desk",
  "factory": "infinigen.assets.objects.tables.desk.SimpleDeskFactory",
  "object_names": ["agent_asset_desk_5dc67a6e18be"],
  "location": [0.0, 0.0, 0.75],
  "dimensions": [1.4, 0.7, 0.75],
  "materials": ["wood"],
  "relations": [],
  "generation": {
    "seed": 0,
    "source_prompt": "add a desk",
    "edit_prompt": "",
    "script_path": "generation_scripts/Scene_scene_081397bb4e26/asset_5dc67a6e18be.py"
  }
}
```

The index gives planners a stable handle for semantic lookup, spatial placement,
replacement editing, and render targeting.

---

### Record-Backed Editing

Generated-asset editing is performed through stored generation records.

```text
\editing prompt
  -> target resolution
  -> retrieve asset record
  -> respawn from original factory
  -> apply supported edit parameters
  -> align replacement to old bounding box
  -> remove old object group
  -> update scene index
  -> render and verify
```

This is more reliable than editing arbitrary mesh geometry without knowing its
origin. Current edits focus on reproducible replacement, material/color changes,
and preserving size and position.

---

### Physics and Placement Rules

The planning and execution layers include explicit spatial rules:

- furniture and rugs are kept on the floor unless explicitly placed elsewhere,
- fruit and lamps stay at realistic small-object scale,
- `place_on` aligns an object with a support surface such as a tabletop or chair seat,
- `place_near` places objects beside a target with a gap,
- `place_against_wall` uses room/wall information when available,
- `apply_physics_rules` corrects common floating/support errors after spatial edits.

---

### Visual Feedback Loop

SCRIPT3D can inspect the rendered scene and correct mistakes.

```text
render -> verifier -> correction instruction -> agent action -> render again
```

This improves completeness and demo reliability.

---

## Supported Workflows

### 1. Inspect and Index a Scene

SCRIPT3D can connect to a running Blender session, inspect objects, and rebuild
the semantic scene index.

Example:

```text
what objects are in the scene?
```

CLI:

```bash
python3 -m infinigen_blender_agent.cli index
```

### 2. Open, Save, and Render `.blend` Files

The agent can open existing Blender files, save the current scene, and render
preview images.

Example:

```text
open /absolute/path/to/scene.blend
render preview
save scene
```

### 3. Generate Infinigen Assets

Generation prompts create new assets.

Example:

```text
add a marble side table
add a desk lamp on the desk
add a strawberry next to the apple
```

Generated assets are inserted through Infinigen factories and tagged with asset
metadata, generation scripts, and scene-index entries.

### 4. Edit Generated Assets

Editing prompts must start with:

```text
\editing
```

Example:

```text
\editing make the desk marble
\editing make the apple green and put it on the table
\editing replace the side table with a coffee table
```

The edit path resolves the target from `scene_index.json`, respawns a compatible
asset from the recorded factory, applies supported edits, and preserves the old
asset's placement and size when requested.

### 5. Move, Scale, Rotate, Delete, and Change Materials

Example:

```text
move the bed right 0.3 meters
rotate the chair 90 degrees
make the cabinet black
delete the apple
```

### 6. Spatial Placement

Example:

```text
put the lamp on the desk
place the strawberry near the apple
put the sofa against the wall
```

These map to dedicated placement tools instead of raw coordinates when possible.

### 7. Camera Framing and Visual Verification

Example:

```text
center the camera on the desk
adjust the view so the apple is visible
```

The addon can render a transparent mask, compute the subject bounding box, adjust
the camera, and produce a final preview render. The UI-side agent can also invoke
the Visual Verifier Agent to check rendered outputs and request corrections.

---

## Supported Object Categories

### Furniture and Interior Objects

```text
bed, bed_frame, mattress, pillow,
desk, table, side_table, coffee_table,
desk_lamp, floor_lamp,
chair, bar_chair, office_chair, sofa, armchair,
cabinet, bookcase, rug, plant
```

### Appliances

```text
beverage_fridge, dishwasher, microwave, oven, tv, monitor
```

### Fruits

```text
apple, blackberry, green_coconut, hairy_coconut, durian,
pineapple, starfruit, strawberry, compositional_fruit
```

---

## Example End-to-End Scenario

User prompt:

```text
add a desk and put a desk lamp on it
```

SCRIPT3D performs:

```text
1. The planner resolves "desk" and "desk lamp" to supported asset categories.
2. It emits add_infinigen_asset for the desk factory.
3. It emits add_infinigen_asset for the desk_lamp factory.
4. It emits place_on to align the lamp to the desk support surface.
5. The Blender client sends each command over the JSON socket.
6. The addon spawns each asset on Blender's main thread.
7. The addon tags root objects with object_id, category, factory, seed, and prompt metadata.
8. The addon writes generation scripts under generation_scripts/.
9. apply_physics_rules corrects common support/floating issues.
10. rebuild_scene_index writes scene_index.json with dimensions, materials, relations, and generation metadata.
11. render_scene optionally runs camera auto-adjustment and writes a preview image.
```

Later, the user asks:

```text
\editing make the desk marble
```

SCRIPT3D then:

```text
1. The planner detects the \editing prefix.
2. It emits edit_generated_asset with target="desk", prompt="make the desk marble", and color="marble".
3. The addon resolves the desk through scene_index.json.
4. It reads the stored factory, seed, source prompt, and generation script path.
5. It respawns a compatible replacement asset from the original factory.
6. It applies the marble material edit.
7. It aligns the replacement to the old asset's bounding box.
8. It removes the old generated object group.
9. It writes a new generation script and refreshes scene_index.json.
10. The scene can be rendered and visually verified again.
```

---

## Quick Start

### 1. Install

Python 3.11 is recommended.

```bash
cd /path/to/infinigen-blender-agent
python3 -m pip install -r requirements.txt
```

Editable install:

```bash
python3 -m pip install -e ".[ui,llm]"
```

---

### 2. Configure LLMs

Edit `config.json` and add API keys for the providers you want to use.

The Code Generator Agent and Visual Verifier Agent can use different models.

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
      "api_key": "...",
      "model": "deepseek-v4-pro",
      "api_base": "https://api.r9s.ai/v1"
    },
    "r9s_visual_verifier": {
      "api_key": "...",
      "model": "claude-opus-4-6",
      "api_base": "https://api.r9s.ai/v1"
    }
  }
}
```

---

## Run with UI

### 1. Start the Blender Addon Agent

```bash
cd /path/to/infinigen-blender-agent
bash scripts/start_blender_agent.sh
```

Default Blender binary:

```text
third_party/infinigen/Blender.app/Contents/MacOS/Blender
```

Default socket:

```text
127.0.0.1:9876
```

### 2. Start the UI

In another terminal:

```bash
cd /path/to/infinigen-blender-agent
bash scripts/start_ui.sh
```

Open:

```text
http://127.0.0.1:7860
```

---

## Run with CLI

Check connection:

```bash
python3 -m infinigen_blender_agent.cli ping
```

Generate an asset:

```bash
python3 -m infinigen_blender_agent.cli chat "add a marble side table"
```

Edit an existing asset:

```bash
python3 -m infinigen_blender_agent.cli chat "\\editing make the desk marble"
```

Render the current scene:

```bash
python3 -m infinigen_blender_agent.cli render --path renders/preview.png
```

Generate a single-room Infinigen bedroom:

```bash
python3 -m infinigen_blender_agent.cli generate-bedroom \
  --output outputs/bedroom/coarse \
  --seed 0
```

---

## Project Layout

```text
SCRIPT3D/
├── README.md
├── pyproject.toml
├── requirements.txt
├── config.json
├── scene.blend
│
├── blender_addon/
│   └── infinigen_agent_addon.py          # Blender socket server and command executor
│
├── infinigen_blender_agent/
│   ├── agent.py                          # CLI/offline agent orchestration
│   ├── planner.py                        # Deterministic English/Chinese rule planner
│   ├── llm_planner.py                    # Optional OpenAI-compatible JSON planner
│   ├── client.py                         # JSON socket client
│   ├── protocol.py                       # Request/response encoding
│   ├── asset_registry.py                 # Category, factory, alias, and material registry
│   ├── infinigen_runner.py               # Out-of-process Infinigen scene generation
│   ├── cli.py                            # Command-line entry point
│   └── app.py                            # Lightweight app helpers
│
├── src/
│   ├── agent/
│   │   ├── agent.py                      # LLM function-calling UI agent
│   │   └── visual_verifier.py            # Render-based visual verifier
│   ├── blender/
│   │   └── client.py                     # UI-side Blender client
│   └── llm/                              # Provider adapters
│
├── ui/
│   ├── main.py                           # Gradio UI entry point
│   ├── components/                       # Chat and layout components
│   ├── utils/                            # Chat, LLM, and Blender helpers
│   └── assets/                           # UI avatars and images
│
├── generation_scripts/
│   ├── asset_*.py
│   └── Scene_*/asset_*.py                # Reproducible generated-asset scripts
│
├── data/
│   ├── aimlapi_samples/                  # Streaming/function-call samples
│   ├── stream_samples/
│   └── stream_parser.py
│
├── docs/
│   └── ARCHITECTURE.md
│
├── doc/
│   └── API.md
│
├── scripts/
│   ├── start_blender_agent.sh
│   └── start_ui.sh
│
├── tests/
│   └── test_visual_verifier.py
│
├── third_party/
│   └── infinigen/                        # Vendored Infinigen dependency
│
├── pic_readme/                           # README images and videos
├── asserts/                              # UI screenshots/icons
└── addon.py                              # Addon convenience entry point
```

---

## Summary

SCRIPT3D turns text-to-3D into a controllable asset workflow.

By combining procedural generation, Python scripts, persistent metadata, scene indexing, multi-agent planning, render verification, and camera correction, SCRIPT3D makes generated 3D assets:

```text
reproducible
editable
inspectable
scene-aware
demo-ready
```

This makes SCRIPT3D more than a text-to-3D generator. It is a foundation for controllable, script-backed 3D creation.
