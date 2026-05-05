import os
import time
import gradio as gr
import modelscope_studio.components.antd as antd
import modelscope_studio.components.antdx as antdx
import modelscope_studio.components.base as ms
import modelscope_studio.components.pro as pro
from modelscope_studio.components.pro.chatbot import (
    ChatbotDataMessage,
    ChatbotDataMessageContent,
    ChatbotDataSuggestionContentItem,
    ChatbotDataSuggestionContentOptions,
)

"""
消息类型：
# 文本消息
ChatbotDataMessage(role="user", content="你好，我是Blender AI助手"),
{
    "role": "assistant",
    "content": "你好！我可以帮你操作Blender，请告诉我你想要做什么。",
},
# 图片消息
ChatbotDataMessage(
    role="user",
    # other content type
    content=ChatbotDataMessageContent(
        type="file",
        content=[
            "https://zos.alipayobjects.com/rmsportal/jkjgkEfvpUPVyRjUImniVslZfWPnJuuZ.png",
            # 使用相对路径，避免路径嵌套问题
            os.path.join(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(__file__))
                ),
                "renders/render_20250324_161433.png",
            ),
        ],
    ),
),
# 工具消息
ChatbotDataMessage(
    role="assistant",
    content=ChatbotDataMessageContent(
        type="tool", content="Tool content", options={"title": "Tool"}
    ),
),
# 思考消息
ChatbotDataMessage(
    role="assistant",
    # multiple content type
    content=[
        ChatbotDataMessageContent(
            type="tool",
            content="Thought content",
            options={"title": "Thinking"},
        ),
        ChatbotDataMessageContent(type="text", content="Hello World"),
    ],
),
"""


def create_chat_interface():
    """创建聊天界面"""
    with antd.Flex(
        elem_style=dict(
            # minHeight=550,
            height="100%",
            maxHeight=700,
            backgroundColor="#171a20",
            borderRadius="8px",
            padding="14px",
            border="1px solid rgba(255,255,255,0.08)",
        ),
        vertical=True,
    ):
        chatbot = pro.Chatbot(
            height=590,
            auto_scroll=True,
            elem_classes=["gosim-chatbot"],
            elem_style=dict(
                # flex=1,
                # overflow="auto",  # 添加滚动条
                # scrollBehavior="smooth",  # 平滑滚动效果
                padding="10px",
                
            ),
            value=[
                # 文本消息
                # ChatbotDataMessage(role="user", content="你好，我是Blender AI助手"),
                {
                    "role": "assistant",
                    "content": "你好！我可以帮你编辑 Infinigen/Blender 场景，请告诉我想添加或调整什么。",
                },
            ],
        )

        with pro.MultimodalInput(
            upload_config=dict(upload_button_tooltip="添加图片"),
            placeholder="请输入想让 Blender/Infinigen 执行的操作指令",
            elem_style=dict(
                marginTop="12px",
            )
        ) as input:
            with ms.Slot("prefix"):
                with antd.Tooltip("清空历史记录"):
                    with antd.Button(
                        value=None, variant="text", color="default"
                    ) as clear_btn:
                        with ms.Slot("icon"):
                            antd.Icon("ClearOutlined")

    return chatbot, input, clear_btn
