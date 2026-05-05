#!/usr/bin/env python
"""
GOSIM Infinigen Blender Agent 应用程序入口
"""
import os
import sys
import traceback
import logging
import socket

import gradio as gr

from ui.main import create_ui

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_free_port(start_port: int, max_tries: int = 20) -> int:
    """Find an available localhost port starting from `start_port`."""
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except PermissionError:
                return start_port
            except OSError:
                continue
            return port
    raise OSError(f"Cannot find empty port in range: {start_port}-{start_port + max_tries - 1}")

def main():
    """主函数"""
    try:
        app = create_ui()
        port = find_free_port(int(os.getenv("GRADIO_SERVER_PORT", "7860")))
        logger.info("Starting UI on http://127.0.0.1:%s", port)
        app.launch(
            server_name="127.0.0.1", 
            server_port=port,
            inbrowser=os.getenv("GOSIM_UI_INBROWSER", "1") != "0"
        )
    except Exception as e:
        logger.error(f"Error starting the Gradio UI: {str(e)}")
        print("\n\n===== Error Details =====")
        traceback.print_exc()
        print("\nIf you see an 'update_status_after_message' undefined error, make sure all code has been updated correctly.")

def fail_safe_main():
    """提供后备的UI，防止主UI无法启动"""
    try:
        # 尝试主启动流程
        main()
    except Exception as e:
        # 如果主UI无法启动，则显示一个简单的错误信息界面
        logger.error(f"Failed to start the app; showing fallback UI: {str(e)}")
        with gr.Blocks(title="GOSIM Infinigen Blender Agent (Error Mode)") as app:
            gr.Markdown("## GOSIM Infinigen Blender Agent Startup Error")
            gr.Markdown(f"""
            An error occurred while starting the application:
            
            ```
            {traceback.format_exc()}
            ```
            
            Check the logs and console output for more information.
            """)
            
            with gr.Row():
                restart_btn = gr.Button("Restart App")
                
            def restart():
                # 重启应用程序
                os.execv(sys.executable, ['python'] + sys.argv)
                
        restart_btn.click(fn=restart)
            
        port = find_free_port(int(os.getenv("GRADIO_SERVER_PORT", "7860")))
        app.launch(
            server_name="127.0.0.1", 
            server_port=port,
            inbrowser=os.getenv("GOSIM_UI_INBROWSER", "1") != "0"
        )

if __name__ == "__main__":
    fail_safe_main() 
