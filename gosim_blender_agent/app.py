"""Gradio UI compatible with the original Blender-agent interaction loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent import GosimAgent
from .client import BlenderClient
from .config import get_settings


def main() -> None:
    try:
        import gradio as gr
    except ImportError as exc:
        raise SystemExit("请先安装 UI 依赖：pip install -e '.[ui]'") from exc

    settings = get_settings()
    client = BlenderClient(settings)
    agent = GosimAgent(client)

    def chat(message: str, history: list[dict[str, str]]) -> tuple[list[dict[str, str]], str | None, str]:
        try:
            result = agent.handle(message)
            assistant_content = result.text.rstrip()
            if assistant_content:
                assistant_content = f"{assistant_content}\n\n已全部完成"
            else:
                assistant_content = "已全部完成"
            history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": assistant_content},
            ]
            raw = json.dumps(result.raw_results, ensure_ascii=False, indent=2)
            return history, result.preview_path, raw
        except Exception as exc:  # UI should show Blender-side errors directly.
            history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": f"执行失败：{exc}"},
            ]
            return history, None, repr(exc)

    def rebuild_index() -> str:
        return json.dumps(client.rebuild_scene_index(), ensure_ascii=False, indent=2)

    def render_preview() -> tuple[str, str]:
        path = settings.render_dir / "preview.png"
        result = client.render_scene(Path(path))
        return result["path"], json.dumps(result, ensure_ascii=False, indent=2)

    with gr.Blocks(title="GOSIM Infinigen Blender Agent") as demo:
        gr.Markdown("# GOSIM Infinigen Blender Agent")
        with gr.Row():
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(type="messages", height=520)
                textbox = gr.Textbox(
                    label="自然语言指令",
                    placeholder="例如：把台灯放到桌子上 / 添加一张书桌 / 把床往右移动 0.3 米 / 渲染预览",
                )
                with gr.Row():
                    send = gr.Button("发送", variant="primary")
                    index_btn = gr.Button("重建索引")
                    render_btn = gr.Button("渲染预览")
            with gr.Column(scale=1):
                image = gr.Image(label="Blender 预览", type="filepath")
                raw = gr.Code(label="工具调用结果", language="json")

        send.click(chat, inputs=[textbox, chatbot], outputs=[chatbot, image, raw])
        textbox.submit(chat, inputs=[textbox, chatbot], outputs=[chatbot, image, raw])
        index_btn.click(rebuild_index, outputs=raw)
        render_btn.click(render_preview, outputs=[image, raw])

    demo.launch(server_name="127.0.0.1", server_port=7860)


if __name__ == "__main__":
    main()
