"""
LLM模块初始化文件和工厂类
"""
import json
import os
from typing import Dict, Any, Optional

from .base import BaseLLM
from .claude import ClaudeLLM
from .zhipu import ZhipuLLM
from .deepseek import DeepSeekLLM
from .doubao import DoubaoLLM
from .moonshot import MoonshotLLM
from .aimlapi import AIMLAPI_LLM
from .r9s import R9SLLM

# 支持的LLM模型
LLM_MODELS = {
    "claude": ClaudeLLM,
    "zhipu": ZhipuLLM,
    "deepseek": DeepSeekLLM,
    "doubao": DoubaoLLM,
    "moonshot": MoonshotLLM,
    "aimlapi": AIMLAPI_LLM,
    "r9s": R9SLLM,
}

class LLMFactory:
    """LLM工厂类，用于创建LLM实例"""

    @staticmethod
    def resolve_provider_type(model_type: str, config: Dict[str, Any]) -> str:
        """Resolve a config entry name to an actual LLM provider type.

        `model_type` can be either a built-in provider name such as `r9s`, or a
        custom config alias such as `r9s_code`. Aliases can specify `provider`
        or `type`; otherwise the prefix before `_` is used when it matches a
        known provider.
        """
        provider_type = config.get("provider") or config.get("type") or model_type
        if provider_type in LLM_MODELS:
            return provider_type

        prefix = model_type.split("_", 1)[0]
        if prefix in LLM_MODELS:
            return prefix

        raise ValueError(
            f"Unsupported LLM type: {model_type}. Supported types: {', '.join(LLM_MODELS.keys())}. "
            "For custom config entries, add a provider field, for example \"provider\": \"r9s\"."
        )

    @staticmethod
    def create_llm(model_type: str, config: Dict[str, Any]) -> Optional[BaseLLM]:
        """
        根据配置创建LLM实例

        Args:
            model_type: 模型类型，如"claude"、"zhipu"、"deepseek"
            config: 配置参数

        Returns:
            LLM实例
        """
        provider_type = LLMFactory.resolve_provider_type(model_type, config)
        llm_class = LLM_MODELS[provider_type]
        api_key = config.get("api_key", "")
        model = config.get("model", "")

        # 额外参数
        kwargs = {k: v for k, v in config.items() if k not in ["api_key", "model", "provider", "type"]}

        return llm_class(api_key=api_key, model=model, **kwargs)

    @staticmethod
    def create_from_config_file(config_file: str = "config.json", model_type: Optional[str] = None) -> BaseLLM:
        """
        从配置文件创建LLM实例

        Args:
            config_file: 配置文件路径
            model_type: 指定模型类型，如果为None则使用配置中的默认模型

        Returns:
            LLM实例
        """
        # 读取配置文件
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Config file does not exist: {config_file}")

        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)

        # 获取LLM配置
        llm_config = config.get("llm", {})

        # 确定要使用的模型类型
        if model_type is None:
            model_type = llm_config.get("default_model", "claude")

        if model_type not in llm_config:
            raise ValueError(f"Model type not found in config file: {model_type}")

        # 创建LLM实例
        model_config = llm_config.get(model_type, {})
        return LLMFactory.create_llm(model_type, model_config)
