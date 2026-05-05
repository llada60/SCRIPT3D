# Gosim2026-Paris

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

### UI 更新说明

当前网页 UI 已针对 Gradio/ModelScope Studio 聊天体验做了整理：

- 页面采用更干净的暗色主题，顶部连接区、模型初始化区、聊天区、场景信息区和渲染预览区使用统一的面板间距与边框。
- 聊天对话框支持稳定的左右气泡排版：用户消息在右侧，Agent 输出在左侧，并分别设置了明确的背景色和文字色。
- 纯文本用户输入会按普通文本消息渲染；只有上传文件时才使用多模态消息结构，避免空文件结构导致用户消息不可见。
- Agent 的文本回复、函数调用提示和工具执行结果都会触发 UI 刷新，减少流式输出或工具输出不显示的问题。
- 长文本、JSON、代码块会自动换行或横向滚动，避免在窄窗口中撑破布局。
- 响应式布局已适配不同浏览器宽度：桌面端保留右侧场景/渲染面板，小屏下消息气泡会自动放宽到可读宽度。
- 初始化区分成两个 agent 模型选择：Code Generator 负责调用 Blender 工具编辑场景，Visual Verifier 负责读取 render 图并生成下一轮调整指令。
- 高级设置新增可选的 Visual Verifier 闭环：勾选“启用 Visual Verifier”后，每次用户指令完成并自动渲染后，系统会把 render 图片、用户目标和当前场景信息交给独立的 verifier agent 判断。
- “Visual Verifier 最大迭代次数”控制 verifier + Blender editing 的最多循环次数；如果 verifier 判断结果已经差不多，会提前结束。
- 当 verifier 认为还需要调整时，它会生成一段给 code generator 的中文 text instruction，要求继续调整物体、camera、lighting、缩放、旋转、材质或构图参数；随后 Agent 会用现有 Blender 工具执行编辑并重新渲染。

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
- `adjust_camera_from_render`
- `render_scene`

原来的 Rodin、Hyper3D、Hunyuan3D-2 模型生成入口已经不作为功能暴露。
兼容旧函数名的 `generate_3d_model` 现在会转发到 `add_infinigen_asset`。

### Camera agent

`adjust_camera_from_render` 会在 Blender 内部先渲染一张透明背景的 mask 图，读取图片 alpha 像素包围盒，判断目标在画面中的中心偏移和占比，然后自动平移/推拉当前 camera，并渲染最终预览图。

`render_scene` 默认会在每次正式渲染前自动检查 camera 视角。视角好的标准是：

- 所有非结构资产都在 camera 画面内。
- 主体在画面中占比足够大，避免相机离物体太远。

如果检查失败，`render_scene` 会先根据场景物体整体包围盒把 camera 对准并拉近，再用透明 mask render 微调居中和距离，然后继续输出最终渲染图。返回结果中的 `camera_auto_adjust` 会记录是否调整、调整前后质量、mask 路径和每步移动信息。

可选参数：

- `target`：要构图的对象、类别或自然语言描述；不填则默认使用场景中的非结构资产。
- `target_fill`：目标主体画面占比，默认 `0.72`。
- `max_iterations`：根据 render 结果迭代调整 camera 的次数，默认 `3`。
- `output_path`：最终预览图输出路径；不填则保存到当前 blend 目录的 `renders/camera_agent_preview.png`。
- `render_scene` 额外支持 `auto_adjust_camera`、`camera_target`、`camera_target_fill`；默认 `auto_adjust_camera=true`。

### Visual Verifier agent

Visual Verifier 是独立 agent，不新增 Blender socket 命令。配置文件用 `agents.code_generator` 和 `agents.visual_verifier` 分别指定两套 API 调用使用的 LLM 类型：

```json
{
  "agents": {
    "code_generator": {
      "model_type": "r9s"
    },
    "visual_verifier": {
      "model_type": "r9s"
    }
  }
}
```

UI 初始化时也可以分别选择 Code Generator 模型和 Visual Verifier 模型。Verifier 输入包括：

- 自动渲染得到的图片路径。
- 用户原始自然语言目标。
- 最新场景信息文本。

Verifier 只负责判断 render 是否接近目标，并输出结构化结果：

```json
{
  "done": false,
  "reason": "主体偏左且灯光偏暗",
  "instruction": "把 camera 向右平移一点并增加主灯亮度，让桌子和台灯位于画面中心。"
}
```

如果 `done=true`，闭环提前结束；如果 `done=false`，`instruction` 会作为下一轮 Code Generator agent 输入，Code Generator 会继续调用现有工具编辑 Blender 场景，然后重新 render 并再次交给 Visual Verifier。循环次数由 UI 中的“Visual Verifier 最大迭代次数”控制。

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
调整相机让桌子居中
调整视角，让场景主体更大一些
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
