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
ChatbotDataMessage(role="user", content="Hi, I am the Blender AI assistant"),
{
    "role": "assistant",
    "content": "Hi. I can help control Blender. Tell me what you want to do.",
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
            backgroundColor="transparent",
            borderRadius="0",
            padding="0",
            border="0",
        ),
        vertical=True,
    ):
        chatbot = pro.Chatbot(
            height=590,
            auto_scroll=True,
            elem_classes=["agent-chatbot"],
            elem_style=dict(
                # flex=1,
                # overflow="auto",  # 添加滚动条
                # scrollBehavior="smooth",  # 平滑滚动效果
                padding="8px 10px 4px",
                
            ),
            value=[
                # 文本消息
                # ChatbotDataMessage(role="user", content="Hi, I am the Blender AI assistant"),
                {
                    "role": "assistant",
                    "content": "Hi. I can help edit your Blender scene. Tell me what you want to add or adjust.",
                },
            ],
        )

        with pro.MultimodalInput(
            upload_config=dict(upload_button_tooltip="Attach image"),
            placeholder="Enter an instruction for Blender/Infinigen",
            elem_style=dict(
                marginTop="12px",
            )
        ) as input:
            with ms.Slot("prefix"):
                with antd.Tooltip("Clear chat history"):
                    with antd.Button(
                        value=None, variant="text", color="default"
                    ) as clear_btn:
                        with ms.Slot("icon"):
                            antd.Icon("ClearOutlined")

    return chatbot, input, clear_btn
