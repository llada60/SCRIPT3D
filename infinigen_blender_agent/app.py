"""Gradio UI compatible with the original Blender-agent interaction loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent import InfinigenAgent
from .client import BlenderClient
from .config import get_settings


def main() -> None:
    try:
        import gradio as gr
    except ImportError as exc:
        raise SystemExit("Please install UI dependencies first: pip install -e '.[ui]'") from exc

    settings = get_settings()
    client = BlenderClient(settings)
    agent = InfinigenAgent(client)

    def chat(message: str, history: list[dict[str, str]]) -> tuple[list[dict[str, str]], str | None, str]:
        try:
            result = agent.handle(message)
            assistant_content = result.text.rstrip()
            if assistant_content:
                assistant_content = f"{assistant_content}\n\nAll done."
            else:
                assistant_content = "All done."
            history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": assistant_content},
            ]
            raw = json.dumps(result.raw_results, ensure_ascii=False, indent=2)
            return history, result.preview_path, raw
        except Exception as exc:  # UI should show Blender-side errors directly.
            history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": f"Execution failed: {exc}"},
            ]
            return history, None, repr(exc)

    def rebuild_index() -> str:
        return json.dumps(client.rebuild_scene_index(), ensure_ascii=False, indent=2)

    def render_preview() -> tuple[str, str]:
        path = settings.render_dir / "preview.png"
        result = client.render_scene(Path(path))
        return result["path"], json.dumps(result, ensure_ascii=False, indent=2)

    with gr.Blocks(title="Infinigen Blender Agent") as demo:
        gr.Markdown("# Infinigen Blender Agent")
        with gr.Row():
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(type="messages", height=520)
                textbox = gr.Textbox(
                    label="Natural-language Instruction",
                    placeholder="Example: put the desk lamp on the table / add a desk / move the bed right by 0.3 m / render preview",
                )
                with gr.Row():
                    send = gr.Button("Send", variant="primary")
                    index_btn = gr.Button("Rebuild Index")
                    render_btn = gr.Button("Render Preview")
            with gr.Column(scale=1):
                image = gr.Image(label="Blender Preview", type="filepath")
                raw = gr.Code(label="Tool Call Result", language="json")

        send.click(chat, inputs=[textbox, chatbot], outputs=[chatbot, image, raw])
        textbox.submit(chat, inputs=[textbox, chatbot], outputs=[chatbot, image, raw])
        index_btn.click(rebuild_index, outputs=raw)
        render_btn.click(render_preview, outputs=[image, raw])

    demo.launch(server_name="127.0.0.1", server_port=7860)


if __name__ == "__main__":
    main()
