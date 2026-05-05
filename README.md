# Gosim2026-Paris

<<<<<<< HEAD
Standalone natural-language Blender agent for editing Infinigen scenes.

这个工程现在是一个完整独立工程，不再依赖外部的
`/Users/rason/Developer/GOSIM_HACKATHON/infinigen` 或空的
`Gosim2026-Paris-main/LLM-Blender-Agent` 目录。

它包含三部分：

- `src/`、`ui/`、`app.py`：基于 `LLM-Blender-Agent` 的 Agent、LLM provider 和 Gradio UI。
- `blender_addon/`、`addon.py`：替换原 Rodin/Hunyuan3D 的 Blender 插件入口，改为 Infinigen-aware socket server。
- `third_party/infinigen/`：vendored Infinigen 源码和 Blender 4.2 app。

## 目录结构

```text
Gosim2026-Paris/
  addon.py                         # Blender 插件入口，加载 Infinigen-aware addon
  app.py                           # LLM-Blender-Agent 原 UI 入口
  src/                             # LLM-Blender-Agent 的 agent / blender client / llm providers
  ui/                              # LLM-Blender-Agent 的 Gradio UI
  blender_addon/
    gosim_infinigen_agent_addon.py # Blender socket server + scene index + Infinigen tools
  gosim_blender_agent/             # 额外 CLI / 离线 planner / runner
  third_party/infinigen/           # Infinigen 源码 + Blender.app
  scripts/
    start_blender_agent.sh
    start_ui.sh
  docs/
    ARCHITECTURE.md
```

## 安装

```bash
cd /Users/rason/Developer/GOSIM_HACKATHON/Gosim2026-Paris
conda activate infinigen
pip install -r requirements.txt
```

如果要用 `pip install -e`：

```bash
pip install -e ".[ui,llm]"
```

## 启动 Blender 插件服务

```bash
cd /Users/rason/Developer/GOSIM_HACKATHON/Gosim2026-Paris
conda activate infinigen
bash scripts/start_blender_agent.sh
```

这个脚本默认使用工程内的：

```text
third_party/infinigen/Blender.app/Contents/MacOS/Blender
```

插件会监听：

```text
127.0.0.1:9876
```

## 启动 Agent UI

另开一个终端：

```bash
cd /Users/rason/Developer/GOSIM_HACKATHON/Gosim2026-Paris
conda activate infinigen
bash scripts/start_ui.sh
```

打开：

```text
http://127.0.0.1:7860
```

UI 沿用 LLM-Blender-Agent 的连接、模型选择、聊天、渲染预览流程，但工具函数已经改成 Infinigen 场景编辑工具。
交互布局保持“左侧网页对话、右侧场景信息和渲染结果”的形式；每次对话工具执行完成后会自动刷新右侧视图。

## 当前 Agent 工具

LLM 可以调用：

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

原来的 Rodin、Hyper3D、Hunyuan3D-2 模型生成入口已经不作为功能暴露。
兼容旧函数名的 `generate_3d_model` 现在会转发到 `add_infinigen_asset`。

## 示例指令

```text
添加一张书桌
添加一盏台灯
添加一个苹果
add a pineapple
把台灯放到桌子上
把床往右移动 0.3 米
把桌子放大 1.2
把椅子放到床旁边
把柜子变成黑色
\editing 场景中的桌子改成绿色
渲染预览
保存场景
```

`add_infinigen_asset` 额外支持 `third_party/infinigen/infinigen/assets/objects/fruits`
下的水果资产：`apple`, `blackberry`, `green_coconut`, `hairy_coconut`,
`durian`, `pineapple`, `starfruit`, `strawberry`, `compositional_fruit`。
对应中文 prompt 如“苹果、黑莓、青椰子、椰子、榴莲、菠萝、凤梨、杨桃、草莓、组合水果”也会被解析。

## CLI

测试连接：

```bash
python -m gosim_blender_agent.cli ping
```

打开已有 `.blend`：

```bash
python -m gosim_blender_agent.cli open /absolute/path/to/scene.blend
```

自然语言命令：

```bash
python -m gosim_blender_agent.cli chat "添加一张书桌"
python -m gosim_blender_agent.cli chat "把台灯放到桌子上"
```

生成一个单卧室 Infinigen 场景：

```bash
python -m gosim_blender_agent.cli generate-bedroom \
  --output /Users/rason/Developer/GOSIM_HACKATHON/Gosim2026-Paris/outputs/bedroom/coarse \
  --seed 0
```

## 场景索引

插件会把当前场景整理成 `gosim_scene_index.json`，字段包括：

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

后续要接 RAG/vector DB 时，可以直接对 `description` 和 `relations` 做 embedding。

生成资产会额外写入 `generation_scripts/{asset_id}.py`，用于追踪 factory、seed、prompt 和后续 editing 修改。

## 独立性说明

默认路径都指向工程内部：

- Infinigen root: `third_party/infinigen`
- Blender binary: `third_party/infinigen/Blender.app/Contents/MacOS/Blender`
- Blender addon: `addon.py`

只要这个目录完整拷走，Python 依赖装好，就不需要再依赖外部项目目录。
=======
# begin 5th May 11:10AM
>>>>>>> 537693ea31a6a776b40e80c29ef6142cf289a351
