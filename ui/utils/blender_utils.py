#!/usr/bin/env python
"""
Blender通信工具函数
"""
import os
import json
import base64
import logging
import tempfile

# 配置日志
logger = logging.getLogger(__name__)

def connect_to_blender(host, port, blender_clients, session_id):
    """
    连接到Blender服务器
    
    Args:
        host: 主机地址
        port: 端口号
        blender_clients: 已废弃，保留参数仅用于兼容性，实际使用全局变量
        session_id: 会话ID
        
    Returns:
        连接状态信息
    """
    try:
        # 导入全局变量
        import ui.globals as globals
        
        # 尝试导入BlenderClient
        from src.blender import BlenderClient
        
        # 清理之前的连接（如果有）
        if session_id in globals.blender_clients and globals.blender_clients[session_id] is not None:
            try:
                # 尝试关闭之前的连接
                globals.blender_clients[session_id].close()
            except Exception:
                pass
        
        # 创建新的客户端连接
        client = BlenderClient(host, int(port))
        
        # 检查连接
        if client.is_connected:
            globals.blender_clients[session_id] = client
            
            # 如果Agent已经初始化，更新其Blender客户端
            if session_id in globals.agents and globals.agents[session_id] is not None:
                try:
                    globals.agents[session_id].update_blender_client(client)
                    return f"Connected to Blender server at {host}:{port}. The Agent Blender client was updated."
                except AttributeError:
                    return f"Connected to Blender server at {host}:{port}, but the Agent could not be updated because update_blender_client is missing."
                except Exception as e:
                    return f"Connected to Blender server at {host}:{port}, but updating the Agent failed: {str(e)}"
            
            return f"Connected to Blender server at {host}:{port}"
        else:
            return "Connection failed. Check that the Blender server is running and that the host/port are correct."
    
    except Exception as e:
        logger.error(f"Error connecting to Blender: {str(e)}")
        return f"Connection error: {str(e)}"

def render_scene_and_return_image(session_id, blender_clients):
    """
    渲染当前场景并返回图像
    
    Args:
        session_id: 会话ID
        blender_clients: 已废弃，保留参数仅用于兼容性，实际使用全局变量
        
    Returns:
        渲染后的图像路径和渲染状态信息
    """
    # 导入全局变量
    import ui.globals as globals
    
    if session_id not in globals.blender_clients:
        return None, "Blender is not connected. Cannot render."
    
    try:
        client = globals.blender_clients[session_id]
        result = client.render_scene(auto_save=True, save_dir="renders")
        
        if result.get("status") == "success":
            # 获取保存的图像路径
            saved_path = result.get("result", {}).get("saved_to")
            if saved_path and os.path.exists(saved_path):
                return saved_path, None
            
            # 如果没有保存路径但有图像数据，则从图像数据创建临时文件
            image_data = result.get("result", {}).get("image_data")
            if image_data:
                temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                image_bytes = base64.b64decode(image_data)
                with open(temp_file.name, "wb") as f:
                    f.write(image_bytes)
                return temp_file.name, None
            
        return None, f"Render failed: {result.get('message', 'Unknown error')}"
    
    except Exception as e:
        logger.error(f"Error rendering scene: {str(e)}")
        return None, f"Render error: {str(e)}"

def get_scene_info(session_id, blender_clients):
    """
    获取场景信息
    
    Args:
        session_id: 会话ID
        blender_clients: 已废弃，保留参数仅用于兼容性，实际使用全局变量
        
    Returns:
        场景信息文本和原始数据对象
    """
    # 导入全局变量
    import ui.globals as globals
    
    if session_id not in globals.blender_clients:
        return "Blender is not connected. Cannot fetch scene info.", None
    
    try:
        client = globals.blender_clients[session_id]
        result = client.get_scene_info()
        
        if result.get("status") == "success":
            scene_data = result.get("result", {})
            info_text = f"Scene Name: {scene_data.get('name', 'Unknown')}\n"
            info_text += f"Object Count: {len(scene_data.get('objects', []))}\n\n"
            
            # 添加对象列表
            objects = scene_data.get("objects", [])
            if objects:
                info_text += "Objects:\n"
                for obj in objects:
                    obj_type = obj.get("type", "Unknown")
                    obj_name = obj.get("name", "Unknown")
                    info_text += f"- {obj_name} ({obj_type})\n"
            
            return info_text, scene_data
        else:
            return f"Failed to fetch scene info: {result.get('message', 'Unknown error')}", None
    
    except Exception as e:
        logger.error(f"Error fetching scene info: {str(e)}")
        return f"Scene info error: {str(e)}", None 
