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
from ui.avatar_config import GENERATION_AGENT_AVATAR, USER_AVATAR, generation_message

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
        elem_classes=["gosim-chat-frame"],
        elem_style=dict(
            height="100%",
            minHeight="100%",
            backgroundColor="transparent",
            borderRadius="0",
            padding="0",
            border="0",
            display="flex",
            flexDirection="column",
        ),
        vertical=True,
    ):
        chatbot = pro.Chatbot(
            height="100%",
            min_height=0,
            auto_scroll=True,
            user_config={
                "header": "user",
                "avatar": USER_AVATAR,
                "placement": "end",
                "shape": "round",
                "variant": "borderless",
            },
            bot_config={
                "header": "3D Generation Agent",
                "avatar": GENERATION_AGENT_AVATAR,
                "placement": "start",
                "shape": "round",
                "variant": "borderless",
            },
            elem_classes=["gosim-chatbot"],
            elem_style=dict(
                padding="0",
                minWidth="0",
                minHeight="0",
                overflow="hidden",
            ),
            value=[
                generation_message("Hi. I can help edit your Blender scene. Tell me what you want to add or adjust."),
            ],
        )

        with pro.MultimodalInput(
            upload_config=dict(upload_button_tooltip="Attach image"),
            placeholder="Enter an instruction for Blender/Infinigen",
            elem_classes=["gosim-chat-input"],
            elem_style=dict(
                marginTop="auto",
                flexShrink=0,
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
