#!/usr/bin/env python
"""
聊天处理工具函数
"""
import json
import logging
import html
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
            logger.debug("Failed to sync Blender Agent status: %s", exc)


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
    notice = "All done."
    if isinstance(content, str):
        if "all done" not in content.lower():
            message["content"] = f"{content.rstrip()}\n\n{notice}" if content.strip() else notice
    elif content is None:
        message["content"] = notice
    else:
        message["content"] = [content, {"type": "text", "content": notice}]


def _append_assistant_text(chatbot_value, text: str) -> None:
    message = chatbot_value[-1]
    content = message.get("content")
    if isinstance(content, str):
        message["content"] = f"{content}{text}"
    elif content is None:
        message["content"] = text.lstrip("\n")
    elif isinstance(content, list):
        content.append({"type": "text", "content": text})
    else:
        message["content"] = [content, {"type": "text", "content": text}]


def _format_tool_result_details(function_result: Dict[str, Any]) -> str:
    json_text = json.dumps(function_result, ensure_ascii=False, indent=2)
    return (
        '\n\n<details class="tool-result-details">'
        "<summary>View details</summary>"
        f"<pre><code>{html.escape(json_text)}</code></pre>"
        "</details>"
    )


def submit(input_value, chatbot_value):
    """处理聊天提交事件"""
    # 获取当前Agent
    agent = get_agent()
    if agent is None:
        logger.error("No available Agent instance found")
        chatbot_value.append(
            {
                "role": "user",
                "content": _format_user_chat_content(input_value),
            }
        )
        chatbot_value.append({
            "role": "assistant", 
            "content": "System error: no available Agent instance was found. Please check that Blender and the LLM are configured correctly.",
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
        original_user_text = (input_value or {}).get("text", "")
        
        # 循环生成，直到收到"完成"开头的回复或达到最大轮数
        while current_rounds < max_auto_rounds:
            current_rounds += 1
            
            # 调用Agent进行流式聊天
            response_stream = agent.chat_stream(user_message=user_message, temperature=0.7)
            
            # 处理流式响应
            first_output = True
            current_function = None  # 记录当前正在执行的函数
            response_content = ""  # 存储完整的响应内容
            blocked_by_guard = False
            
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
                    function_name = function_call.get("name", "Unknown tool")
                    # 检查是否是新的函数调用
                    if function_name != current_function:
                        current_function = function_name
                        if "content" not in chatbot_value[-1] or chatbot_value[-1]["content"] is None:
                            chatbot_value[-1]["content"] = f"Running: {function_name}..."
                        else:
                            chatbot_value[-1]["content"] += f"\nRunning: {function_name}..."
                
                # 如果有函数调用结果，添加函数调用结果到当前消息
                if function_result:
                    if function_result.get("status") == "blocked":
                        blocked_by_guard = True
                    _append_assistant_text(chatbot_value, _format_tool_result_details(function_result))
                
                # 第一次有内容输出时就取消loading状态
                if first_output and (content_chunk or function_call or function_result):
                    chatbot_value[-1]["loading"] = False
                    first_output = False
                
                # 更新UI
                if content_chunk or function_call or function_result:
                    yield gr.update(loading=False), gr.update(value=chatbot_value)
                else:
                    print("The LLM produced no output in this round")
            
            # 完成一轮对话，更新最后一条消息的状态
            chatbot_value[-1]["loading"] = False
            chatbot_value[-1]["status"] = "done"
            
            # 检查是否需要结束自动生成循环
            response_text = response_content.strip()
            should_stop = (
                response_text.lower().startswith("all done") or 
                response_text.lower().endswith("all done.") or
                "waiting for user instruction" in response_text.lower() or
                blocked_by_guard or
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
                    user_message = (
                        f"Continue completing the original user instruction: {original_user_text}\n"
                        "Strict limits: only perform actions explicitly requested in the original instruction. "
                        "Do not add, delete, move, or modify anything not requested by the original instruction. "
                        "If the original instruction is already complete, reply only: All done."
                    )
                else:
                    user_message = (
                        f"Continue completing the original user instruction: {original_user_text}\n"
                        "Strict limits: do not expand the scene and do not add unrequested objects. "
                        "If the original instruction is already complete, reply only: All done."
                    )

        _append_completion_notice(chatbot_value)
        
    except Exception as e:
        logger.error(f"Error during chat: {str(e)}")
        chatbot_value[-1]["loading"] = False
        chatbot_value[-1]["content"] = f"Error while processing the message: {str(e)}"
        chatbot_value[-1]["status"] = "done"
    
    _set_blender_agent_status(agent, "idle", "Agent run finished")
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
            scene_update = f"{scene_update}\n\nRender status: {render_error}"

    return scene_update, image_update


def submit_with_view(
    input_value,
    chatbot_value,
    auto_update_info=True,
    auto_render=True,
    enable_visual_verifier=False,
    visual_verifier_iterations=2,
):
    """处理聊天提交，并在右侧刷新场景信息与渲染预览。"""
    last_input_update = gr.update()
    last_chat_update = gr.update(value=chatbot_value)
    user_goal = (input_value or {}).get("text", "")

    for input_update, chat_update in submit(input_value, chatbot_value):
        last_input_update = input_update
        last_chat_update = chat_update
        yield input_update, chat_update, gr.update(), gr.update()

    scene_update, image_update = _refresh_right_view(auto_update_info, auto_render)
    yield last_input_update, last_chat_update, scene_update, image_update

    if not enable_visual_verifier or not auto_render or not isinstance(image_update, str):
        return

    agent = get_agent()
    if agent is None:
        return

    try:
        max_iterations = max(1, min(5, int(visual_verifier_iterations or 1)))
    except (TypeError, ValueError):
        max_iterations = 2

    current_scene_text = scene_update if isinstance(scene_update, str) else ""
    current_image_path = image_update

    for iteration in range(1, max_iterations + 1):
        chatbot_value.append({
            "role": "assistant",
            "content": f"Visual Verifier is checking render {iteration}/{max_iterations}...",
            "loading": True,
            "status": "pending",
        })
        yield gr.update(loading=True), gr.update(value=chatbot_value), gr.update(), gr.update()

        visual_verifier = getattr(agent, "visual_verifier", None)
        if visual_verifier is None:
            chatbot_value[-1]["content"] = "Visual Verifier is not initialized. Please initialize the Agent again."
            chatbot_value[-1]["loading"] = False
            chatbot_value[-1]["status"] = "done"
            yield gr.update(loading=False), gr.update(value=chatbot_value), gr.update(), gr.update()
            break

        verdict = visual_verifier.verify(user_goal, current_image_path, current_scene_text)
        reason = verdict.reason or "No reason provided."
        instruction = verdict.instruction or ""
        if verdict.done:
            chatbot_value[-1]["content"] = f"Visual Verifier: the result is acceptable. Reason: {reason}"
            chatbot_value[-1]["loading"] = False
            chatbot_value[-1]["status"] = "done"
            yield gr.update(loading=False), gr.update(value=chatbot_value), gr.update(), gr.update()
            break

        chatbot_value[-1]["content"] = (
            f"Visual Verifier: more adjustment is needed. Reason: {reason}\n\n"
            f"Instruction for the code generator: {instruction}"
        )
        chatbot_value[-1]["loading"] = False
        chatbot_value[-1]["status"] = "done"
        yield gr.update(loading=False), gr.update(value=chatbot_value), gr.update(), gr.update()

        generator_instruction = (
            "The visual verifier proposed the following adjustment based on the latest render. "
            "Use only Blender tool calls to fix prompt consistency, basic physics, or practical plausibility. "
            "If the render is too dark or the camera is too far to verify, you may move/adjust existing Light or Camera objects, but do not add new lights or unrequested objects. "
            "Do not optimize lighting, camera, composition, materials, or render style for subjective aesthetics. "
            "Keep following the user's original goal, and do not add objects unless explicitly required by the original goal or verifier instruction. "
            "When finished, reply: All done.\n"
            f"Original user goal: {user_goal}\n"
            f"{instruction}"
        )
        for input_update, chat_update in submit({"text": generator_instruction, "files": []}, chatbot_value):
            last_input_update = input_update
            last_chat_update = chat_update
            yield input_update, chat_update, gr.update(), gr.update()

        scene_update, image_update = _refresh_right_view(auto_update_info, auto_render)
        yield last_input_update, last_chat_update, scene_update, image_update

        if not isinstance(image_update, str):
            break
        current_scene_text = scene_update if isinstance(scene_update, str) else current_scene_text
        current_image_path = image_update


def cancel(chatbot_value):
    """处理取消事件"""
    agent = get_agent()
    if agent and getattr(agent, "blender_client", None) is not None:
        try:
            agent.blender_client.cancel_agent_run()
        except Exception as exc:
            logger.debug("Failed to notify Blender to stop the Agent run: %s", exc)
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
                function_name = function_call.get("name", "Unknown tool")
                # 检查是否是新的函数调用
                if function_name != current_function:
                    current_function = function_name
                    if "content" not in chatbot_value[-1] or chatbot_value[-1]["content"] is None:
                        chatbot_value[-1]["content"] = f"Running: {function_name}..."
                    else:
                        chatbot_value[-1]["content"] += f"\nRunning: {function_name}..."
                    message_changed = True
            
            # 如果有函数调用结果，添加函数调用结果到当前消息
            if function_result:
                _append_assistant_text(chatbot_value, _format_tool_result_details(function_result))
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
        logger.error(f"Error during retry: {str(e)}")
        chatbot_value[-1]["loading"] = False
        chatbot_value[-1]["content"] = f"Error while retrying: {str(e)}"
        chatbot_value[-1]["status"] = "done"
    
    _set_blender_agent_status(agent, "idle", "Agent run finished")
    # 更新UI，结束loading状态
    yield gr.update(loading=False), gr.update(value=chatbot_value)
