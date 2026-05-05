#!/usr/bin/env python
"""
GOSIM HACKATHON BlenderCode3D UI主入口

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
"""

import logging
import os
import time

import gradio as gr

from ui.components.chat_tab import create_chat_tab
import ui.globals as globals


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


CUSTOM_CSS = """
:root {
    --gosim-bg: #0d1117;
    --gosim-surface: rgba(23, 28, 36, 0.58);
    --gosim-surface-2: rgba(35, 41, 52, 0.52);
    --gosim-border: rgba(226, 234, 244, 0.18);
    --gosim-border-soft: rgba(255, 255, 255, 0.08);
    --gosim-text: #f4f7fb;
    --gosim-muted: #9aa4b2;
    --gosim-accent: #62d6a6;
    --gosim-blue: #5aa8ff;
    --gosim-glass-shadow: 0 24px 70px rgba(0, 0, 0, 0.32);
}

*,
*::before,
*::after {
    box-sizing: border-box;
}

html,
body {
    height: 100%;
    overflow: hidden;
}

.gradio-container {
    max-width: none !important;
    height: 100dvh;
    min-height: 100dvh;
    overflow: hidden !important;
    padding: 12px 20px 36px !important;
    background:
        radial-gradient(circle at 12% 8%, rgba(82, 140, 255, 0.18), transparent 28%),
        radial-gradient(circle at 78% 12%, rgba(98, 214, 166, 0.14), transparent 30%),
        linear-gradient(135deg, #0b0f15 0%, #111820 46%, #0a0d12 100%) !important;
    color: var(--gosim-text);
}

#gosim-shell {
    max-width: 1680px;
    height: 100%;
    min-height: 0;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.app-title h1,
.app-title h2,
.app-title p {
    margin: 0;
}

.app-title {
    margin-bottom: 10px !important;
    flex: 0 0 auto;
}

.app-title h2 {
    font-size: 24px;
    line-height: 1.15;
    letter-spacing: 0;
    font-weight: 760;
}

.app-subtitle {
    margin-top: 8px !important;
    color: var(--gosim-muted);
    font-size: 14px;
}

.setup-grid,
.workspace-grid,
.action-row {
    gap: 12px !important;
}

.setup-card,
.side-panel {
    border: 1px solid var(--gosim-border-soft);
    border-radius: 14px;
    background: var(--gosim-surface);
    box-shadow: var(--gosim-glass-shadow);
    backdrop-filter: blur(22px) saturate(130%);
    -webkit-backdrop-filter: blur(22px) saturate(130%);
}

.setup-card {
    padding: 12px 14px;
    margin-bottom: 12px;
    flex: 0 0 auto;
}

.unified-setup-card {
    width: 100%;
    max-width: none;
}

.model-row,
.connect-row,
.setup-links {
    gap: 12px !important;
}

.connect-row {
    align-items: stretch !important;
    padding-top: 8px;
}

.connect-row button {
    min-height: 66px;
    height: 100%;
    border-radius: 12px !important;
    font-weight: 760 !important;
}

.connect-row .block {
    min-height: 66px !important;
}

.setup-links {
    justify-content: flex-end;
    margin-top: 0;
}

.setup-links button {
    min-height: 30px !important;
    padding: 0 14px !important;
}

.setup-card h2,
.section-title h2 {
    margin: 0 0 14px;
    font-size: 17px;
    line-height: 1.3;
}

.setup-card .block,
.setup-card .form {
    margin-bottom: 0 !important;
}

.workspace-grid {
    display: grid !important;
    grid-template-columns: minmax(0, 3fr) minmax(470px, 2fr);
    grid-template-rows: minmax(0, 1fr);
    align-items: stretch;

    /*
    关键修复：
    不能写 height:100%，因为上方还有 title 和 setup-card。
    height:100% 会让 workspace 自己等于整页高度，最终页面被消息撑长。
    这里让它吃掉剩余空间，真正高度由 JS 按视口动态兜底计算。
    */
    flex: 1 1 0 !important;
    min-height: 0 !important;
    height: auto !important;
    max-height: none !important;

    overflow: hidden !important;
    margin-bottom: 10px;
}

.workspace-grid > * {
    min-height: 0 !important;
    height: 100% !important;
    max-height: 100% !important;
    overflow: hidden !important;
}

.workspace-grid > .gradio-column:first-child {
    min-width: 0;
    height: 100%;
    min-height: 0 !important;
    max-height: 100% !important;
    overflow: hidden !important;
}

.workspace-grid > .gradio-column:last-child {
    min-width: 470px;
    height: 100%;
    min-height: 0 !important;
    max-height: 100% !important;
    overflow: hidden !important;
}

.side-panel {
    padding: 12px;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
}

.side-stack {
    gap: 12px !important;
    height: 100%;
    min-height: 0;
}

.side-panel .block {
    min-height: 0 !important;
}

.scene-info {
    flex: 1 1 auto;
    min-height: 0;
}

.scene-info textarea {
    min-height: 104px !important;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    line-height: 1.38 !important;
    font-size: 13px !important;
}

.render-preview {
    margin-bottom: 10px;
    flex: 0 0 auto;
}

.render-preview .image-container,
.render-preview img {
    border-radius: 12px !important;
}

/* =========================
   ChatGPT-like chat layout
   ========================= */

.chat-panel {
    position: relative;
    padding: 0;
    overflow: hidden;
    min-height: 0;
    height: 100%;
    max-height: 100%;
    display: flex;
    flex-direction: column;
    border: 0;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
}

.chat-panel > div,
.chat-panel > .block,
.gosim-chat-frame {
    flex: 1 1 0 !important;
    min-height: 0 !important;
    height: 100% !important;
    max-height: 100% !important;
    overflow: hidden !important;
}

.gosim-chat-frame {
    display: flex !important;
    flex-direction: column !important;
    gap: 8px;
    min-width: 0;
}

/*
重要：
这里不要写 height:100%，否则聊天列表会把输入框一起往下顶。
第一个子元素只负责占据剩余空间。
*/
.gosim-chat-frame > *:first-child {
    flex: 1 1 0 !important;
    min-height: 0 !important;
    height: auto !important;
    max-height: 100% !important;
    overflow: hidden !important;
}

.gosim-chat-frame > *:last-child {
    flex: 0 0 auto !important;
    min-height: 0 !important;
}

.gosim-chatbot {
    color: var(--gosim-text) !important;
    min-width: 0 !important;
    min-height: 0 !important;
    height: 100% !important;
    max-height: 100% !important;
    overflow: hidden !important;
    background: transparent !important;
}

.gosim-chatbot,
.gosim-chatbot * {
    box-sizing: border-box;
}

.chat-panel .block,
.chat-panel .form,
.chat-panel .wrap,
.chat-panel [class*="container"],
.chat-panel [class*="Container"] {
    background: transparent !important;
    border-color: transparent !important;
    box-shadow: none !important;
}

.ms-gr-pro-chatbot {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 1 auto !important;
    min-height: 0 !important;
    height: 100% !important;
    max-height: 100% !important;
    overflow: hidden !important;
}

.ms-gr-pro-chatbot,
.ms-gr-pro-chatbot-messages {
    min-height: 0 !important;
    max-height: 100% !important;
}

/*
唯一滚动区：消息列表。
padding-bottom 用来给底部输入框预留空间，避免最后一条消息被挡住。
*/
.ms-gr-pro-chatbot-messages {
    /*
    唯一滚动区。
    flex-basis 用 0，防止内容高度参与父级高度计算并把页面撑长。
    */
    flex: 1 1 0 !important;
    height: auto !important;
    min-height: 0 !important;
    max-height: 100% !important;

    overflow-y: auto !important;
    overflow-x: hidden !important;

    display: block !important;
    align-content: flex-start !important;
    justify-content: flex-start !important;

    padding: 12px 8px 112px 8px !important;

    scrollbar-gutter: stable;
    overscroll-behavior: contain;
    scroll-behavior: smooth;
}

/* 输入框在底部正常占位，不再把整个聊天区往下顶 */
.gosim-chat-input {
    flex: 0 0 auto !important;
    min-width: 0 !important;
    margin-bottom: 2px !important;
    padding-top: 10px !important;
    z-index: 20;
    background:
        linear-gradient(
            to top,
            rgba(11, 15, 21, 0.96),
            rgba(11, 15, 21, 0.72),
            transparent
        ) !important;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
}

/* 如果组件内部用了 form，也固定成底部占位元素 */
.gosim-chat-input form {
    margin: 0 !important;
}

.chat-panel textarea,
.chat-panel input {
    border-radius: 999px !important;
    background: rgba(7, 12, 18, 0.62) !important;
}

/* 兼容不同版本的 gradio/modelscope DOM 层级 */
.gosim-chatbot,
.gosim-chatbot > div,
.gosim-chatbot > div > div,
.gosim-chatbot [class*="chatbot"],
.gosim-chatbot [class*="Chatbot"] {
    min-height: 0 !important;
}

.gosim-chatbot [class*="list"],
.gosim-chatbot [class*="List"],
.gosim-chatbot [class*="items"],
.gosim-chatbot [class*="Items"],
.gosim-chatbot [class*="message-list"],
.gosim-chatbot [class*="Message-list"] {
    background: transparent !important;
    border: 0 !important;
}

/* =========================
   Bubble style
   ========================= */

.ms-gr-pro-chatbot-message,
.ms-gr-pro-chatbot-message-content,
.ms-gr-ant-bubble,
.ms-gr-ant-bubble-content-wrapper {
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    overflow: visible !important;
}

.ms-gr-pro-chatbot-message {
    margin-bottom: 10px !important;
    padding: 0 !important;
    overflow: visible !important;
}

.ms-gr-pro-chatbot-message-content {
    padding: 0 !important;
    width: auto !important;
    max-width: 100% !important;
    overflow: visible !important;
}

.gosim-chatbot .ms-gr-pro-chatbot-message,
.gosim-chatbot .ms-gr-pro-chatbot-message-content,
.gosim-chatbot .ms-gr-ant-bubble,
.gosim-chatbot .ms-gr-ant-bubble-content-wrapper,
.gosim-chatbot [class*="pro-chatbot-message"]:not([class*="content-filled"]),
.gosim-chatbot [class*="bubble-content-wrapper"],
.gosim-chatbot [class*="Bubble-content-wrapper"] {
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
}

.gosim-chatbot [class*="pro-chatbot-message-content"] {
    padding: 0 !important;
    overflow: visible !important;
}

.gosim-chatbot [class*="bubble"]:not([class*="content"]):not([class*="Content"]),
.gosim-chatbot [class*="Bubble"]:not([class*="content"]):not([class*="Content"]),
.gosim-chatbot [class*="message"]:not([class*="content"]):not([class*="Content"]),
.gosim-chatbot [class*="Message"]:not([class*="content"]):not([class*="Content"]),
.gosim-chatbot [class*="item"]:not([class*="content"]):not([class*="Content"]),
.gosim-chatbot [class*="Item"]:not([class*="content"]):not([class*="Content"]) {
    max-width: 100%;
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
}

.gosim-chatbot .ant-bubble-content,
.gosim-chatbot .ms-gr-ant-bubble-content,
.gosim-chatbot .ant-bubble-content-filled,
.gosim-chatbot .ms-gr-ant-bubble-content-filled,
.gosim-chatbot [class*="bubble-content-filled"],
.gosim-chatbot [class*="Bubble-content-filled"],
.gosim-chatbot [class*="bubble-content"],
.gosim-chatbot [class*="Bubble-content"],
.gosim-chatbot [class*="ant-bubble-content"] {
    position: relative;
    width: auto !important;
    max-width: min(76%, 760px) !important;
    min-width: 44px;
    padding: 14px 18px;
    border: 0;
    border-radius: 16px;
    color: var(--gosim-text) !important;
    line-height: 1.6;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    word-break: break-word;
    box-shadow: none !important;
}

.gosim-chatbot .ant-bubble-content-filled,
.gosim-chatbot .ms-gr-ant-bubble-content-filled {
    background: transparent !important;
}

.gosim-chatbot [class*="content-wrapper"],
.gosim-chatbot [class*="Content-wrapper"] {
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    padding: 0 !important;
    overflow: visible !important;
}

.gosim-chatbot .ant-bubble,
.gosim-chatbot .ms-gr-ant-bubble,
.gosim-chatbot [class*="ant-bubble"] {
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    overflow: visible !important;
}

.gosim-chatbot .ant-bubble-content-wrapper,
.gosim-chatbot .ms-gr-ant-bubble-content-wrapper,
.gosim-chatbot [class*="bubble-content-wrapper"],
.gosim-chatbot [class*="Bubble-content-wrapper"] {
    width: auto !important;
    max-width: min(76%, 760px) !important;
    height: auto !important;
    min-height: 0 !important;
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    overflow: visible !important;
}

.gosim-chatbot .ant-bubble-end .ant-bubble-content-wrapper,
.gosim-chatbot .ms-gr-ant-bubble-end .ms-gr-ant-bubble-content-wrapper,
.gosim-chatbot [class*="bubble-end"] [class*="bubble-content-wrapper"],
.gosim-chatbot [class*="Bubble-end"] [class*="Bubble-content-wrapper"] {
    margin-left: auto !important;
    max-width: min(76%, 760px) !important;
}

.gosim-chatbot .ant-bubble-content,
.gosim-chatbot .ms-gr-ant-bubble-content,
.gosim-chatbot [class*="ant-bubble-content"]:not([class*="wrapper"]):not([class*="Wrapper"]) {
    display: inline-block !important;
    width: auto !important;
    max-width: 100% !important;
    height: auto !important;
    min-height: 0 !important;
    overflow: visible !important;
    white-space: pre-wrap !important;
    overflow-wrap: anywhere !important;
    word-break: break-word !important;
}

.gosim-chatbot .ant-bubble-end .ant-bubble-content,
.gosim-chatbot .ms-gr-ant-bubble-end .ms-gr-ant-bubble-content,
.gosim-chatbot [class*="bubble-end"] [class*="content"]:not([class*="wrapper"]):not([class*="Wrapper"]),
.gosim-chatbot [class*="Bubble-end"] [class*="content"]:not([class*="wrapper"]):not([class*="Wrapper"]),
.gosim-chatbot [class*="user"] [class*="ant-bubble-content"] {
    margin-left: auto;
    background: linear-gradient(180deg, rgba(70, 221, 158, 0.96), rgba(43, 198, 130, 0.94)) !important;
    border: 0 !important;
    border-radius: 16px 6px 16px 16px !important;
    color: #07130e !important;
    display: inline-block !important;
}

.gosim-chatbot .ant-bubble-end .ant-bubble-content::after,
.gosim-chatbot .ms-gr-ant-bubble-end .ms-gr-ant-bubble-content::after,
.gosim-chatbot [class*="bubble-end"] [class*="content"]:not([class*="wrapper"]):not([class*="Wrapper"])::after,
.gosim-chatbot [class*="Bubble-end"] [class*="content"]:not([class*="wrapper"]):not([class*="Wrapper"])::after {
    content: "";
    position: absolute;
    top: 13px;
    right: -7px;
    width: 0;
    height: 0;
    border-top: 7px solid transparent;
    border-bottom: 7px solid transparent;
    border-left: 8px solid rgba(43, 198, 130, 0.94);
}

.gosim-chatbot .ant-bubble-start .ant-bubble-content,
.gosim-chatbot .ms-gr-ant-bubble-start .ms-gr-ant-bubble-content,
.gosim-chatbot [class*="bubble-start"] [class*="content"]:not([class*="wrapper"]):not([class*="Wrapper"]),
.gosim-chatbot [class*="Bubble-start"] [class*="content"]:not([class*="wrapper"]):not([class*="Wrapper"]),
.gosim-chatbot [class*="assistant"] [class*="ant-bubble-content"] {
    margin-right: auto;
    background: rgba(36, 42, 53, 0.72) !important;
    border: 0 !important;
    border-radius: 6px 16px 16px 16px !important;
    color: #edf2f8 !important;
}

.gosim-chatbot .ant-bubble-start .ant-bubble-content::before,
.gosim-chatbot .ms-gr-ant-bubble-start .ms-gr-ant-bubble-content::before,
.gosim-chatbot [class*="bubble-start"] [class*="content"]:not([class*="wrapper"]):not([class*="Wrapper"])::before,
.gosim-chatbot [class*="Bubble-start"] [class*="content"]:not([class*="wrapper"]):not([class*="Wrapper"])::before {
    content: "";
    position: absolute;
    top: 13px;
    left: -7px;
    width: 0;
    height: 0;
    border-top: 7px solid transparent;
    border-bottom: 7px solid transparent;
    border-right: 8px solid rgba(36, 42, 53, 0.72);
}

/* 回到底部按钮 */
.gosim-scroll-bottom-button {
    position: absolute;
    right: 18px;
    bottom: 88px;
    z-index: 30;
    display: none;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 999px;
    background: rgba(18, 24, 32, 0.94);
    color: #edf2f8;
    box-shadow: 0 10px 26px rgba(0, 0, 0, 0.32);
    padding: 8px 14px;
    font-size: 13px;
    line-height: 1;
    cursor: pointer;
    backdrop-filter: blur(14px) saturate(120%);
    -webkit-backdrop-filter: blur(14px) saturate(120%);
}

.gosim-scroll-bottom-button:hover {
    background: rgba(34, 42, 54, 0.98);
}

.gosim-scroll-helper {
    display: none !important;
}

/* Avatar / header */
.gosim-chatbot [class*="avatar"],
.gosim-chatbot [class*="Avatar"] {
    border-radius: 50% !important;
}

.gosim-chatbot [class*="avatar"] img,
.gosim-chatbot [class*="Avatar"] img {
    width: 34px !important;
    height: 34px !important;
    min-width: 34px !important;
    border-radius: 50% !important;
    object-fit: cover !important;
    box-shadow: 0 8px 26px rgba(0, 0, 0, 0.28);
}

.gosim-chatbot [class*="header"],
.gosim-chatbot [class*="Header"] {
    color: rgba(229, 237, 247, 0.68) !important;
    font-size: 11px !important;
    font-weight: 650 !important;
}

.gosim-chatbot [class*="tool"],
.gosim-chatbot [class*="Tool"],
.gosim-chatbot [class*="thought"],
.gosim-chatbot [class*="Thought"] {
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
}

.gosim-chatbot p,
.gosim-chatbot span,
.gosim-chatbot pre,
.gosim-chatbot code {
    color: inherit;
}

.gosim-chatbot pre,
.gosim-chatbot code {
    max-width: 100%;
    overflow-x: auto;
    white-space: pre-wrap;
    border: 0 !important;
    background: rgba(0, 0, 0, 0.18) !important;
}

.gosim-chatbot details.tool-result-details {
    margin-top: 10px;
}

.gosim-chatbot details.tool-result-details summary {
    display: inline-flex;
    align-items: center;
    min-height: 30px;
    padding: 4px 10px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.10);
    color: inherit;
    cursor: pointer;
    user-select: none;
}

/* Buttons / inputs */
.primary-actions button {
    min-height: 36px;
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

.gradio-container input[type="checkbox"] {
    width: 18px !important;
    height: 18px !important;
    min-width: 18px !important;
    appearance: none;
    -webkit-appearance: none;
    display: inline-grid;
    place-content: center;
    border: 1.5px solid #7b8794 !important;
    border-radius: 4px !important;
    background: rgba(7, 12, 10, 0.82) !important;
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.04);
    cursor: pointer;
}

.gradio-container input[type="checkbox"]::before {
    content: "";
    width: 9px;
    height: 9px;
    transform: scale(0);
    transition: transform 120ms ease;
    background: #07130e;
    clip-path: polygon(14% 44%, 0 59%, 38% 100%, 100% 18%, 84% 4%, 36% 70%);
}

.gradio-container input[type="checkbox"]:checked {
    border-color: #7ee1b6 !important;
    background: #62d6a6 !important;
    box-shadow: 0 0 0 3px rgba(98, 214, 166, 0.18);
}

.gradio-container input[type="checkbox"]:checked::before {
    transform: scale(1);
}

.gradio-container input[type="checkbox"]:focus-visible {
    outline: 2px solid rgba(126, 225, 182, 0.72);
    outline-offset: 2px;
}

.gradio-container label:has(input[type="checkbox"]) {
    gap: 10px !important;
    align-items: center !important;
    color: #e8edf3 !important;
}

.gradio-container label:has(input[type="checkbox"]:checked) {
    color: #ffffff !important;
}

.gradio-container label:has(input[type="checkbox"]:checked),
.gradio-container .checkbox-label:has(input[type="checkbox"]:checked) {
    background: rgba(98, 214, 166, 0.1) !important;
    border-color: rgba(126, 225, 182, 0.42) !important;
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
    display: none !important;
    border-top: 1px solid var(--gosim-border-soft) !important;
    background: rgba(15, 17, 21, 0.86) !important;
}


/* =========================
   Hard viewport constraints
   防止 Gradio 外层 wrapper 因子元素高度继续向下撑开页面
   ========================= */

body,
html,
.gradio-container,
#gosim-shell {
    overflow: hidden !important;
}

#gosim-shell {
    height: 100dvh !important;
    max-height: 100dvh !important;
}

.setup-card,
.app-title {
    flex: 0 0 auto !important;
}

.chat-panel,
.side-panel,
.gosim-chatbot,
.ms-gr-pro-chatbot {
    min-height: 0 !important;
    overflow: hidden !important;
}



/* =========================================================
   DOCKED INPUT FINAL LAYOUT
   .gosim-chat-scroll 是唯一滚动区
   .gosim-chat-input-dock 始终固定在聊天区域底部
   ========================================================= */

.chat-panel {
    position: relative !important;
    height: 100% !important;
    max-height: 100% !important;
    min-height: 0 !important;
    overflow: hidden !important;
}

.gosim-chat-frame {
    display: flex !important;
    flex-direction: column !important;
    height: 100% !important;
    max-height: 100% !important;
    min-height: 0 !important;
    overflow: hidden !important;
}

/* 消息滚动区 */
.gosim-chat-scroll {
    flex: 1 1 0 !important;
    min-height: 0 !important;
    height: auto !important;
    max-height: none !important;

    overflow-y: auto !important;
    overflow-x: hidden !important;

    padding: 12px 8px 24px 8px !important;
    scrollbar-gutter: stable;
    overscroll-behavior: contain;
    scroll-behavior: smooth;
}

.gosim-chat-scroll::-webkit-scrollbar {
    width: 8px;
}

.gosim-chat-scroll::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.28);
    border-radius: 999px;
}

.gosim-chat-scroll::-webkit-scrollbar-track {
    background: transparent;
}

/* 输入框独立固定底部 */
.gosim-chat-input-dock {
    flex: 0 0 auto !important;
    position: relative !important;
    z-index: 60 !important;
    min-height: 0 !important;
    overflow: visible !important;

    padding: 10px 0 2px 0 !important;
    background:
        linear-gradient(
            to top,
            rgba(11, 15, 21, 0.98),
            rgba(11, 15, 21, 0.86),
            transparent
        ) !important;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
}

.gosim-chat-input {
    position: relative !important;
    bottom: auto !important;
    top: auto !important;
    z-index: 70 !important;
    margin: 0 !important;
    flex: 0 0 auto !important;
    min-width: 0 !important;
}

/* 滚动区内部组件不要自己截断高度 */
.gosim-chat-scroll .gosim-chatbot,
.gosim-chat-scroll .ms-gr-pro-chatbot,
.gosim-chat-scroll .ms-gr-pro-chatbot-messages,
.gosim-chat-scroll .gosim-chatbot > div,
.gosim-chat-scroll .gosim-chatbot > div > div,
.gosim-chat-scroll [class*="chatbot"],
.gosim-chat-scroll [class*="Chatbot"] {
    height: auto !important;
    max-height: none !important;
    min-height: 0 !important;
    overflow: visible !important;
}

.gosim-chat-scroll .ms-gr-pro-chatbot-messages {
    overflow: visible !important;
    padding: 0 !important;
}

/* 回到底部按钮 */
.gosim-scroll-bottom-button {
    position: absolute !important;
    right: 18px !important;
    bottom: 94px !important;
    z-index: 90 !important;
}

@media (max-width: 980px) {
    .gradio-container {
        padding: 18px !important;
    }

    .workspace-grid {
        grid-template-columns: minmax(0, 1fr);
    }

    .workspace-grid > .gradio-column:last-child {
        min-width: 0;
    }

    .gosim-chatbot .ant-bubble-content,
    .gosim-chatbot [class*="bubble-content"],
    .gosim-chatbot [class*="Bubble-content"],
    .gosim-chatbot [class*="message-content"],
    .gosim-chatbot [class*="Message-content"],
    .gosim-chatbot [data-role] {
        max-width: 92%;
    }

    .gosim-chatbot .ant-bubble-content-wrapper,
    .gosim-chatbot .ms-gr-ant-bubble-content-wrapper,
    .gosim-chatbot [class*="bubble-content-wrapper"],
    .gosim-chatbot [class*="Bubble-content-wrapper"] {
        width: min(100%, 560px) !important;
        max-width: min(100%, 560px) !important;
    }
}

@media (max-width: 640px) {
    .app-title h2 {
        font-size: 22px;
    }

    .setup-card,
    .side-panel {
        padding: 14px;
    }

    .gosim-chatbot {
        min-height: 340px;
    }
}
/* =========================
   Chat Bubble Inner Spacing
   ========================= */

.gosim-chatbot .ant-bubble-content,
.gosim-chatbot .ms-gr-ant-bubble-content,
.gosim-chatbot [class*="bubble-content"],
.gosim-chatbot [class*="Bubble-content"] {

    /* 关键：增加内部留白 */
    padding: 16px 20px !important;

    line-height: 1.7 !important;

    /* 防止文字贴边 */
    box-sizing: border-box !important;

    /* 让长文本更舒服 */
    word-break: break-word !important;
    overflow-wrap: anywhere !important;
}

/* assistant 气泡 */
.gosim-chatbot .ant-bubble-start .ant-bubble-content,
.gosim-chatbot .ms-gr-ant-bubble-start .ms-gr-ant-bubble-content {
    padding: 16px 20px !important;
    border-radius: 8px 18px 18px 18px !important;
}

/* user 气泡 */
.gosim-chatbot .ant-bubble-end .ant-bubble-content,
.gosim-chatbot .ms-gr-ant-bubble-end .ms-gr-ant-bubble-content {
    padding: 16px 20px !important;
    border-radius: 18px 8px 18px 18px !important;
}

"""


CHAT_SCROLL_HELPER = """
<script>
(() => {
    const THRESHOLD = 80;
    let followBottom = true;
    let scrollContainer = null;
    let observer = null;
    let button = null;
    let inputFormBound = false;

    const findScrollContainer = () => document.querySelector('.gosim-chat-scroll');
    const findChatPanel = () => document.querySelector('.chat-panel');
    const findInputForm = () => document.querySelector('.gosim-chat-input form');

    const syncWorkspaceHeight = () => {
        const grid = document.querySelector('.workspace-grid');
        if (!grid) return;

        const rect = grid.getBoundingClientRect();
        const bottomGap = 24;
        const available = Math.max(260, window.innerHeight - rect.top - bottomGap);

        grid.style.height = `${available}px`;
        grid.style.maxHeight = `${available}px`;
        grid.style.minHeight = '0px';
        grid.style.overflow = 'hidden';
    };

    const isNearBottom = (element) => {
        if (!element) return true;
        return element.scrollHeight - element.scrollTop - element.clientHeight < THRESHOLD;
    };

    const scrollToBottom = (behavior = 'smooth') => {
        if (!scrollContainer) return;
        scrollContainer.scrollTo({
            top: scrollContainer.scrollHeight,
            behavior,
        });
    };

    const syncButton = () => {
        if (!button) return;
        button.style.display = followBottom ? 'none' : 'block';
    };

    const setFollowBottom = (value, shouldScroll = false) => {
        followBottom = value;
        syncButton();
        if (shouldScroll) {
            setTimeout(() => scrollToBottom('smooth'), 0);
        }
    };

    const ensureButton = () => {
        const chatPanel = findChatPanel();
        if (!chatPanel) return null;

        let existing = document.getElementById('gosim-scroll-bottom-button');
        if (existing) return existing;

        const created = document.createElement('button');
        created.id = 'gosim-scroll-bottom-button';
        created.type = 'button';
        created.className = 'gosim-scroll-bottom-button';
        created.textContent = '回到底部';
        created.addEventListener('click', () => {
            setFollowBottom(true, true);
        });

        chatPanel.appendChild(created);
        return created;
    };

    const bindInputForm = () => {
        if (inputFormBound) return;

        const form = findInputForm();
        if (!form) return;

        inputFormBound = true;

        form.addEventListener(
            'submit',
            () => {
                followBottom = true;
                syncButton();

                setTimeout(() => {
                    syncWorkspaceHeight();
                    scrollToBottom('smooth');
                }, 50);
                setTimeout(() => scrollToBottom('smooth'), 250);
                setTimeout(() => scrollToBottom('smooth'), 600);
            },
            true
        );
    };

    const bindScrollContainer = () => {
        const element = findScrollContainer();
        if (!element) return;

        button = ensureButton() || button;
        bindInputForm();

        if (element === scrollContainer) return;

        scrollContainer = element;
        followBottom = true;
        syncButton();

        element.addEventListener(
            'scroll',
            () => {
                followBottom = isNearBottom(element);
                syncButton();
            },
            { passive: true }
        );

        observer?.disconnect();

        observer = new MutationObserver(() => {
            if (!scrollContainer) return;

            syncWorkspaceHeight();

            const nearBottom = isNearBottom(scrollContainer);

            if (followBottom || nearBottom) {
                followBottom = true;
                syncButton();
                requestAnimationFrame(() => scrollToBottom('auto'));
            }
        });

        observer.observe(element, {
            childList: true,
            subtree: true,
            characterData: true,
        });

        setTimeout(() => scrollToBottom('auto'), 0);
    };

    const bootstrap = () => {
        syncWorkspaceHeight();
        button = ensureButton() || button;
        bindInputForm();
        bindScrollContainer();

        if (followBottom) {
            setTimeout(() => scrollToBottom('auto'), 0);
        }
    };

    const watcher = new MutationObserver(() => bootstrap());
    watcher.observe(document.body, {
        childList: true,
        subtree: true,
    });

    window.addEventListener('resize', () => {
        syncWorkspaceHeight();
        if (followBottom) scrollToBottom('auto');
    });

    setInterval(bootstrap, 700);
    document.addEventListener('DOMContentLoaded', bootstrap);
    bootstrap();
})();
</script>
"""


def create_ui():
    """
    创建Gradio UI界面
    """

    globals.blender_clients = {}
    globals.agents = {}

    session_id = f"session_{int(time.time())}"
    globals.session_id = session_id

    with gr.Blocks(
        title="GOSIM HACKATHON ● BlenderCode3D",
        css=CUSTOM_CSS,
        elem_id="gosim-shell",
    ) as app:
        gr.Markdown("## GOSIM HACKATHON ● BlenderCode3D", elem_classes=["app-title"])

        create_chat_tab(session_id)

        # JS 辅助滚动：新消息自动到底部，用户上滑历史时不强制跳回。
        gr.HTML(CHAT_SCROLL_HELPER, elem_classes=["gosim-scroll-helper"])

    return app


def main():
    app = create_ui()

    configured_port = os.getenv("GRADIO_SERVER_PORT")
    port = int(configured_port) if configured_port else None

    logger.info(
        "Starting UI on %s",
        f"http://127.0.0.1:{port}" if port else "the first available localhost port",
    )

    app.launch(
        server_name="127.0.0.1",
        server_port=port,
        inbrowser=os.getenv("GOSIM_UI_INBROWSER", "1") != "0",
    )


if __name__ == "__main__":
    main()
