#!/usr/bin/env python
"""
聊天处理工具函数
"""
import json
import logging
from typing import Dict, List, Any, Optional, Generator
import gradio as gr
from ui.utils.blender_utils import get_scene_info, render_scene_and_return_image
import time
from src.agent.agent import BlenderAgent
from ui.globals import agents

# 配置日志
logger = logging.getLogger(__name__)

"""
消息类型说明：

1. 普通文本消息
   - 用户或助手发送的纯文本消息
   - 结构: {'role': 'user'/'assistant', 'content': '文本内容', ...}

2. 图文消息
   - 用户上传的文件，如图片等
   - 结构: {'role': 'user', 'content': {'type': 'file', 'content': [文件路径列表], ...}, ...}

3. 工具消息
   - 助手使用工具返回的结果
   - 结构: {'role': 'assistant', 'content': {'type': 'tool', 'content': '工具内容', ...}, ...}

4. 组合消息
   - 包含多种内容类型的消息
   - 结构: {'role': 'user'/'assistant', 'content': [{消息1}, {消息2}, ...], ...}

5. 加载状态消息
   - 表示助手正在处理的消息
   - 结构: {'role': 'assistant', 'loading': True, 'status': 'pending', ...}

6. 思考类型消息
   - 显示助手正在思考或推理的过程
   - 结构: {'role': 'assistant', 'content': {'type': 'thinking', 'content': '思考内容'}, ...}
   - 可以包含状态如 'typing': True 表示正在输入思考内容

消息通用属性:
- role: 消息发送者角色 ('user' 或 'assistant')
- content: 消息内容，可以是字符串、字典或列表
- status: 消息状态 ('pending', 'done' 等)
- loading: 是否正在加载
- typing: 是否正在输入(思考)
- footer: 底部信息，如 'canceled' 表示已取消
- 以及其他UI相关属性(avatar, variant, shape等)
"""


def get_agent() -> Optional[BlenderAgent]:
    """获取当前使用的Agent实例"""
    import ui.globals as globals
    for session_id in globals.agents:
        return globals.agents[session_id]


def _set_blender_agent_status(agent, state: str, message: str):
    if agent and getattr(agent, "blender_client", None) is not None:
        try:
            agent.blender_client.set_agent_status(state=state, message=message)
        except Exception as exc:
            logger.debug("同步 Blender Agent 状态失败: %s", exc)


def _format_user_chat_content(input_value):
    """Use plain text for text-only messages so the chatbot renders them reliably."""
    input_value = input_value or {}
    text = input_value.get("text", "")
    files = input_value.get("files") or []
    if not files:
        return text
    return [
        {"type": "text", "content": text},
        {"type": "file", "content": files},
    ]


def _append_completion_notice(chatbot_value):
    if not chatbot_value:
        return
    message = chatbot_value[-1]
    content = message.get("content")
    notice = "已全部完成"
    if isinstance(content, str):
        if notice not in content:
            message["content"] = f"{content.rstrip()}\n\n{notice}" if content.strip() else notice
    elif content is None:
        message["content"] = notice
    else:
        message["content"] = [content, {"type": "text", "content": notice}]


def submit(input_value, chatbot_value):
    """处理聊天提交事件"""
    # 获取当前Agent
    agent = get_agent()
    if agent is None:
        logger.error("未找到可用的Agent实例")
        chatbot_value.append(
            {
                "role": "user",
                "content": _format_user_chat_content(input_value),
            }
        )
        chatbot_value.append({
            "role": "assistant", 
            "content": "系统错误：未找到可用的Agent实例，请确认已正确配置Blender和LLM。",
            "status": "done"
        })
        yield gr.update(value=None), gr.update(value=chatbot_value)
        return

    # 添加用户消息到聊天界面
    chatbot_value.append(
        {
            "role": "user",
            "content": _format_user_chat_content(input_value),
        }
    )
    chatbot_value.append({"role": "assistant", "loading": True, "status": "pending"})
    
    # 更新UI，清空输入框并显示loading状态
    yield gr.update(value=None, loading=True), gr.update(value=chatbot_value)
    
    try:
        # 构建用户消息格式
        user_message = (input_value or {}).get("text", "")
        
        # 如果有文件，添加到用户消息
        input_files = (input_value or {}).get("files") or []
        if input_files:
            user_message = [
                {"type": "text", "text": user_message},
                *[{"type": "image_url", "image_url": {"url": file}} for file in input_files]
            ]
        
        # 自动生成的最大轮数
        max_auto_rounds = 10
        current_rounds = 0
        
        # 循环生成，直到收到"完成"开头的回复或达到最大轮数
        while current_rounds < max_auto_rounds:
            current_rounds += 1
            
            # 调用Agent进行流式聊天
            response_stream = agent.chat_stream(user_message=user_message, temperature=0.7)
            
            # 处理流式响应
            first_output = True
            current_function = None  # 记录当前正在执行的函数
            response_content = ""  # 存储完整的响应内容
            
            for chunk in response_stream:
                content_chunk = chunk.get("content")
                function_call = chunk.get("function_call")
                function_result = chunk.get("function_result")
                
                # 更新聊天内容和收集完整响应
                if content_chunk:
                    response_content += content_chunk
                    if "content" not in chatbot_value[-1] or chatbot_value[-1]["content"] is None:
                        chatbot_value[-1]["content"] = content_chunk
                    else:
                        chatbot_value[-1]["content"] += content_chunk
                
                # 如果有函数调用，添加函数调用信息（仅当是新函数时）
                if function_call:
                    function_name = function_call.get("name", "未知函数")
                    # 检查是否是新的函数调用
                    if function_name != current_function:
                        current_function = function_name
                        if "content" not in chatbot_value[-1] or chatbot_value[-1]["content"] is None:
                            chatbot_value[-1]["content"] = f"正在执行：{function_name}..."
                        else:
                            chatbot_value[-1]["content"] += f"\n正在执行：{function_name}..."
                
                # 如果有函数调用结果，添加函数调用结果到当前消息
                if function_result:
                    # 在当前消息中添加函数调用结果
                    if "content" not in chatbot_value[-1] or chatbot_value[-1]["content"] is None:
                        chatbot_value[-1]["content"] = json.dumps(function_result, ensure_ascii=False, indent=2)
                    else:
                        chatbot_value[-1]["content"] += f"\n\n```json\n{json.dumps(function_result, ensure_ascii=False, indent=2)}\n```"
                
                # 第一次有内容输出时就取消loading状态
                if first_output and (content_chunk or function_call or function_result):
                    chatbot_value[-1]["loading"] = False
                    first_output = False
                
                # 更新UI
                if content_chunk or function_call or function_result:
                    yield gr.update(loading=False), gr.update(value=chatbot_value)
                else:
                    print("该轮中LLM没有内容输出")
            
            # 完成一轮对话，更新最后一条消息的状态
            chatbot_value[-1]["loading"] = False
            chatbot_value[-1]["status"] = "done"
            
            # 检查是否需要结束自动生成循环
            response_text = response_content.strip()
            should_stop = (
                response_text.startswith("全部完成") or 
                response_text.endswith("全部完成") or
                "等待用户指令" in response_text or
                current_rounds >= max_auto_rounds
            )
            
            if should_stop:
                # 如果满足停止条件，结束循环
                break
            else:
                # 继续下一轮生成，但不添加新的用户消息到UI中
                # 为下一轮生成创建新的助手消息
                chatbot_value.append({"role": "assistant", "loading": True, "status": "pending"})
                yield gr.update(loading=True), gr.update(value=chatbot_value)
                
                # 下一轮传入空字符串作为用户消息
                if not response_content:
                    user_message = ""
                else:
                    user_message = "继续"

        _append_completion_notice(chatbot_value)
        
    except Exception as e:
        logger.error(f"聊天过程中发生错误: {str(e)}")
        chatbot_value[-1]["loading"] = False
        chatbot_value[-1]["content"] = f"处理消息时发生错误: {str(e)}"
        chatbot_value[-1]["status"] = "done"
    
    _set_blender_agent_status(agent, "idle", "Agent 运行已结束")
    # 更新UI，结束loading状态
    yield gr.update(loading=False), gr.update(value=chatbot_value)


def _refresh_right_view(auto_update_info=True, auto_render=True):
    import ui.globals as globals

    scene_update = gr.update()
    image_update = gr.update()

    if auto_update_info:
        scene_text, _scene_data = get_scene_info(globals.session_id, globals.blender_clients)
        scene_update = scene_text

    if auto_render:
        image_path, render_error = render_scene_and_return_image(
            globals.session_id,
            globals.blender_clients,
        )
        image_update = image_path if image_path else gr.update()
        if render_error and auto_update_info:
            scene_update = f"{scene_update}\n\n渲染状态: {render_error}"

    return scene_update, image_update


def submit_with_view(input_value, chatbot_value, auto_update_info=True, auto_render=True):
    """处理聊天提交，并在右侧刷新场景信息与渲染预览。"""
    last_input_update = gr.update()
    last_chat_update = gr.update(value=chatbot_value)

    for input_update, chat_update in submit(input_value, chatbot_value):
        last_input_update = input_update
        last_chat_update = chat_update
        yield input_update, chat_update, gr.update(), gr.update()

    scene_update, image_update = _refresh_right_view(auto_update_info, auto_render)
    yield last_input_update, last_chat_update, scene_update, image_update


def cancel(chatbot_value):
    """处理取消事件"""
    agent = get_agent()
    if agent and getattr(agent, "blender_client", None) is not None:
        try:
            agent.blender_client.cancel_agent_run()
        except Exception as exc:
            logger.debug("通知 Blender 停止 Agent 运行失败: %s", exc)
    chatbot_value[-1]["loading"] = False
    chatbot_value[-1]["footer"] = "canceled"
    chatbot_value[-1]["status"] = "done"
    yield gr.update(loading=False), gr.update(value=chatbot_value)


def clear():
    """清空聊天历史"""
    # 如果存在Agent，也清空Agent的消息历史
    agent = get_agent()
    if agent:
        if hasattr(agent, "reset_messages"):
            agent.reset_messages()
        else:
            agent.messages = []
    
    yield gr.update(value=None)


def retry(chatbot_value):
    """重试事件"""
    agent = get_agent()
    if agent is None or not chatbot_value:
        yield gr.update(value=chatbot_value)
    
    # 找到最后一条用户消息
    user_messages = [msg for msg in chatbot_value if msg.get("role") == "user"]
    if not user_messages:
        yield gr.update(value=chatbot_value)
    
    last_user_message = user_messages[-1]
    
    # 从chatbot_value中移除最后一个助手消息
    assistant_indices = [i for i, msg in enumerate(chatbot_value) if msg.get("role") == "assistant"]
    if assistant_indices:
        chatbot_value.pop(assistant_indices[-1])
    
    # 添加新的助手消息（处理中状态）
    chatbot_value.append({"role": "assistant", "loading": True, "status": "pending"})
    
    # 先更新UI
    yield gr.update(loading=True), gr.update(value=chatbot_value)
    
    try:
        # 从Agent的消息历史中移除最后一个助手消息
        if agent.messages and agent.messages[-1]["role"] == "assistant":
            agent.messages.pop()
        
        # 提取用户消息内容
        if isinstance(last_user_message.get("content"), list):
            # 多模态消息
            text_content = next((item.get("content") for item in last_user_message["content"] 
                                if item.get("type") == "text"), "")
            file_content = [item.get("content") for item in last_user_message["content"] 
                           if item.get("type") == "file"]
            
            # 构建用户消息格式
            if file_content and file_content[0]:
                user_message = [
                    {"type": "text", "text": text_content},
                    *[{"type": "image_url", "image_url": {"url": file}} for file in file_content[0]]
                ]
            else:
                user_message = text_content
        else:
            # 纯文本消息
            user_message = last_user_message.get("content", "")
        
        # 调用Agent进行流式聊天
        response_stream = agent.chat_stream(user_message=user_message, temperature=0.7)
        
        # 处理流式响应
        first_output = True
        current_function = None  # 记录当前正在执行的函数
        for chunk in response_stream:
            content_chunk = chunk.get("content")
            function_call = chunk.get("function_call")
            function_result = chunk.get("function_result")
            
            # 更新聊天内容
            message_changed = False

            if content_chunk:
                if "content" not in chatbot_value[-1] or chatbot_value[-1]["content"] is None:
                    chatbot_value[-1]["content"] = content_chunk
                else:
                    chatbot_value[-1]["content"] += content_chunk
                message_changed = True
                
            # 如果有函数调用，添加函数调用信息（仅当是新函数时）
            if function_call:
                function_name = function_call.get("name", "未知函数")
                # 检查是否是新的函数调用
                if function_name != current_function:
                    current_function = function_name
                    if "content" not in chatbot_value[-1] or chatbot_value[-1]["content"] is None:
                        chatbot_value[-1]["content"] = f"正在执行：{function_name}..."
                    else:
                        chatbot_value[-1]["content"] += f"\n正在执行：{function_name}..."
                    message_changed = True
            
            # 如果有函数调用结果，添加函数调用结果到当前消息
            if function_result:
                # 在当前消息中添加函数调用结果
                if "content" not in chatbot_value[-1] or chatbot_value[-1]["content"] is None:
                    chatbot_value[-1]["content"] = json.dumps(function_result, ensure_ascii=False, indent=2)
                else:
                    chatbot_value[-1]["content"] += f"\n\n```json\n{json.dumps(function_result, ensure_ascii=False, indent=2)}\n```"
                message_changed = True
            
            # 第一次有内容输出时就取消loading状态
            if first_output and (content_chunk or function_call or function_result):
                chatbot_value[-1]["loading"] = False
                first_output = False
            
            # 更新UI
            if message_changed:
                yield gr.update(loading=False), gr.update(value=chatbot_value)
        
        # 完成对话，更新最后一条消息的状态
        chatbot_value[-1]["loading"] = False
        chatbot_value[-1]["status"] = "done"
        _append_completion_notice(chatbot_value)
        
    except Exception as e:
        logger.error(f"重试过程中发生错误: {str(e)}")
        chatbot_value[-1]["loading"] = False
        chatbot_value[-1]["content"] = f"处理重试时发生错误: {str(e)}"
        chatbot_value[-1]["status"] = "done"
    
    _set_blender_agent_status(agent, "idle", "Agent 运行已结束")
    # 更新UI，结束loading状态
    yield gr.update(loading=False), gr.update(value=chatbot_value)
