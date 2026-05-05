#!/usr/bin/env python
"""
GOSIM Infinigen Blender Agent UI主入口

UI组件说明：
1. 连接步骤区域 - 分为两行的布局设计
   - 第一行: 步骤1和步骤2并排显示，贯穿整个界面宽度
     * 步骤1: 连接到Blender - 输入主机、端口并连接
     * 步骤2: 初始化LLM模型 - 选择模型并初始化
   - 第二行: 步骤3占据左侧区域
     * 步骤3: 开始对话 - 与LLM交互的主要界面
2. 聊天界面 - 与LLM交互
   - 对话框 - 显示用户与LLM的对话历史
   - 输入框和发送按钮 - 用于发送消息
3. 高级设置 - 配置可用函数、场景信息和渲染选项
4. 场景信息和渲染结果 - 在右侧区域显示Blender状态

数据流和交互逻辑：
1. 用户按照界面引导完成步骤1和步骤2
   a. 连接到Blender服务器
   b. 选择LLM模型并初始化Agent
2. 完成初始设置后，用户开始步骤3
   a. 用户发送消息，系统调用LLM处理消息
   b. LLM通过函数调用与Blender交互，执行操作
   c. 操作结果和对话内容更新到UI上
"""
import time
import gradio as gr

from ui.components.chat_tab import create_chat_tab
import ui.globals as globals

CUSTOM_CSS = """
:root {
    --gosim-bg: #101112;
    --gosim-surface: #181a1b;
    --gosim-surface-2: #222524;
    --gosim-border: #363a37;
    --gosim-border-soft: rgba(255, 255, 255, 0.08);
    --gosim-text: #f4f7fb;
    --gosim-muted: #9aa4b2;
    --gosim-accent: #62d6a6;
}

.gradio-container {
    max-width: none !important;
    min-height: 100vh;
    padding: 24px 32px 28px !important;
    background: var(--gosim-bg) !important;
    color: var(--gosim-text);
}

#gosim-shell {
    max-width: 1680px;
    margin: 0 auto;
}

.app-title h1,
.app-title h2,
.app-title p {
    margin: 0;
}

.app-title h2 {
    font-size: 28px;
    line-height: 1.15;
    letter-spacing: 0;
}

.app-subtitle {
    margin-top: 8px !important;
    color: var(--gosim-muted);
    font-size: 14px;
}

.setup-grid,
.workspace-grid,
.action-row {
    gap: 18px !important;
}

.setup-card,
.side-panel,
.chat-panel {
    border: 1px solid var(--gosim-border-soft);
    border-radius: 8px;
    background: rgba(23, 26, 32, 0.92);
    box-shadow: 0 18px 42px rgba(0, 0, 0, 0.22);
}

.setup-card {
    padding: 18px 18px 16px;
}

.setup-card h2,
.section-title h2 {
    margin: 0 0 14px;
    font-size: 17px;
    line-height: 1.3;
}

.side-panel {
    padding: 16px;
}

.chat-panel {
    padding: 0;
    overflow: hidden;
}

.workspace-grid {
    align-items: stretch;
}

.workspace-grid > .gradio-column:first-child {
    min-width: 0;
}

.workspace-grid > .gradio-column:last-child {
    min-width: 360px;
}

.scene-info textarea {
    min-height: 210px !important;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    line-height: 1.55 !important;
}

.render-preview {
    margin-top: 14px;
}

.render-preview .image-container,
.render-preview img {
    border-radius: 6px !important;
}

.primary-actions button {
    min-height: 44px;
    font-weight: 650;
}

.secondary-actions button {
    min-height: 38px;
}

.gradio-container label,
.gradio-container .block .label-wrap span {
    color: #dce3ec !important;
}

.gradio-container input,
.gradio-container textarea,
.gradio-container select {
    border-color: var(--gosim-border) !important;
    background: #121414 !important;
    color: var(--gosim-text) !important;
}

.gradio-container button.primary,
.gradio-container button[variant="primary"] {
    border: 0 !important;
    background: linear-gradient(180deg, #7ee1b6, #43bd88) !important;
    color: #07130e !important;
}

.gradio-container button.secondary,
.gradio-container button[variant="secondary"] {
    border-color: var(--gosim-border) !important;
    background: #242724 !important;
    color: #edf2f8 !important;
}

footer {
    border-top: 1px solid var(--gosim-border-soft) !important;
    background: rgba(15, 17, 21, 0.86) !important;
}

@media (max-width: 980px) {
    .gradio-container {
        padding: 18px !important;
    }

    .workspace-grid > .gradio-column:last-child {
        min-width: 0;
    }
}
"""

def create_ui():
    """
    创建Gradio UI界面
    
    主要组件和功能：
    1. 聊天界面 - 由create_chat_tab函数创建，包含所有交互元素
    2. 聊天处理器 - 由setup_chat_handlers设置，处理各种事件和消息
    
    数据管理：
    - blender_clients: 存储Blender客户端连接
    - agents: 存储LLM Agent实例
    - session_id: 唯一会话标识符，用于关联客户端和Agent
    
    Returns:
        Gradio应用实例
    """
    # 初始化全局变量
    globals.blender_clients = {}  # 用于存储不同连接的Blender客户端
    globals.agents = {}  # 用于存储不同会话的Agent
    
    # 生成唯一会话ID，用于标识当前会话
    session_id = f"session_{int(time.time())}"
    globals.session_id = session_id
    
    with gr.Blocks(
        title="GOSIM Infinigen Blender Agent",
        css=CUSTOM_CSS,
        elem_id="gosim-shell",
    ) as app:
        gr.Markdown("## GOSIM Infinigen Blender Agent", elem_classes=["app-title"])
        gr.Markdown(
            "使用 LLM Function Call 操作 Blender / Infinigen 场景",
            elem_classes=["app-subtitle"],
        )

        create_chat_tab(session_id)
      
    
    return app 
