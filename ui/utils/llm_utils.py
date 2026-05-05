#!/usr/bin/env python
"""
LLM交互工具函数
"""
import os
import json
import logging

# 默认配置文件路径
DEFAULT_CONFIG_PATH = "config.json"

# 配置日志
logger = logging.getLogger(__name__)

def load_config(config_path=DEFAULT_CONFIG_PATH):
    """
    加载配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        配置信息
    """
    try:
        if not os.path.exists(config_path):
            logger.error(f"配置文件不存在: {config_path}")
            return None

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        return config

    except Exception as e:
        logger.error(f"加载配置文件失败: {str(e)}")
        return None

def get_available_models(config):
    """
    获取可用的模型列表

    Args:
        config: 配置信息

    Returns:
        可用模型列表
    """
    if not config or "llm" not in config:
        return ["aimlapi"]

    llm_config = config.get("llm", {})
    models = []

    for model_type, model_config in llm_config.items():
        if model_type != "default_model" and isinstance(model_config, dict):
            models.append(model_type)

    return models or ["aimlapi"]

def get_configured_agent_model(config, agent_name, fallback=None):
    """
    从配置中读取指定 agent 使用的 LLM 类型。

    支持新格式：
    {
      "agents": {
        "code_generator": {"model_type": "r9s"},
        "visual_verifier": {"model_type": "aimlapi"}
      }
    }
    """
    if not config:
        return fallback or "aimlapi"

    llm_config = config.get("llm", {})
    agent_config = (config.get("agents", {}) or {}).get(agent_name, {})
    model_type = agent_config.get("model_type") or agent_config.get("llm")
    if model_type:
        return model_type
    return fallback or llm_config.get("default_model", "aimlapi")

def initialize_agent(session_id, model_type, temperature, verifier_model_type=None):
    """
    初始化Agent

    Args:
        session_id: 会话ID
        model_type: 模型类型
        temperature: 温度参数

    Returns:
        初始化状态信息
    """
    try:
        # 导入全局变量
        import ui.globals as globals

        # 清除之前的实例（如果有）
        if session_id in globals.agents:
            try:
                # 尝试清理旧实例
                del globals.agents[session_id]
            except Exception as e:
                logger.warning(f"清理旧Agent实例时出错: {str(e)}")

        # 加载配置
        config = load_config()
        if not config:
            return "加载配置失败，请检查配置文件"

        # 创建LLM实例
        try:
            from src.llm import LLMFactory
            code_generator_llm = LLMFactory.create_from_config_file(DEFAULT_CONFIG_PATH, model_type)
            # 验证LLM实例
            if not code_generator_llm or not hasattr(code_generator_llm, "chat"):
                return f"模型 {model_type} 初始化失败: 无效的LLM实例"

            verifier_model_type = verifier_model_type or get_configured_agent_model(
                config,
                "visual_verifier",
                fallback=model_type,
            )
            verifier_llm = LLMFactory.create_from_config_file(DEFAULT_CONFIG_PATH, verifier_model_type)
            if not verifier_llm or not hasattr(verifier_llm, "chat"):
                return f"Verifier 模型 {verifier_model_type} 初始化失败: 无效的LLM实例"
        except Exception as e:
            logger.error(f"创建LLM实例时出错: {str(e)}")
            return f"初始化模型失败: {str(e)}"

        # 创建Agent，如果已连接Blender，则使用Blender客户端，否则使用None
        try:
            from src.agent import BlenderAgent, VisualVerifierAgent

            # 检查Blender连接
            blender_client = None
            if session_id in globals.blender_clients and globals.blender_clients[session_id] is not None:
                if hasattr(globals.blender_clients[session_id], 'is_connected') and globals.blender_clients[session_id].is_connected:
                    blender_client = globals.blender_clients[session_id]
                else:
                    blender_client = None
                    logger.warning("Blender客户端存在但未连接")

            # 创建Agent实例。code generator 和 visual verifier 使用两套独立 LLM client。
            verifier_agent = VisualVerifierAgent(verifier_llm)
            agent = BlenderAgent(code_generator_llm, blender_client, visual_verifier=verifier_agent)

            # 验证Agent
            if not agent or not hasattr(agent, "functions") or len(agent.functions) == 0:
                return "Agent创建失败: 无效的Agent实例或没有可用函数"

            # 存储Agent实例到全局字典
            globals.agents[session_id] = agent

            # 返回状态信息
            blender_status = "已连接" if blender_client is not None else "未连接"
            return (
                "初始化成功，"
                f"Code Generator模型: {model_type}, "
                f"Visual Verifier模型: {verifier_model_type}, "
                f"Blender状态: {blender_status}, 可用函数: {len(agent.functions)}个"
            )

        except Exception as e:
            logger.error(f"创建Agent实例时出错: {str(e)}")
            return f"创建Agent时出错: {str(e)}"

    except Exception as e:
        logger.error(f"初始化Agent时出错: {str(e)}")
        return f"初始化出错: {str(e)}"

def get_available_functions(session_id, agents=None):
    """
    获取可用的函数列表，包含函数名和描述

    Args:
        session_id: 会话ID
        agents: 已废弃，保留参数仅用于兼容性，实际使用全局变量

    Returns:
        函数信息列表 [(name, description), ...]
    """
    # 导入全局变量
    import ui.globals as globals

    if session_id not in globals.agents:
        return []

    agent = globals.agents[session_id]
    return [(func["name"], func.get("description", "无描述")) for func in agent.functions]

def get_function_names(session_id, agents=None):
    """
    仅获取函数名列表

    Args:
        session_id: 会话ID
        agents: 已废弃，保留参数仅用于兼容性，实际使用全局变量

    Returns:
        函数名列表
    """
    # 导入全局变量
    import ui.globals as globals

    if session_id not in globals.agents:
        return []

    agent = globals.agents[session_id]
    return [func["name"] for func in agent.functions]

def format_functions_for_display(session_id, agents=None):
    """
    格式化函数列表，用于显示

    Args:
        session_id: 会话ID
        agents: 已废弃，保留参数仅用于兼容性，实际使用全局变量

    Returns:
        格式化后的函数列表，每个元素包含函数名和说明
    """
    functions = get_available_functions(session_id)
    return [f"{name} - {desc}" for name, desc in functions]
