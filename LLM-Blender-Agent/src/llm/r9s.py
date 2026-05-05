"""
R9S API实现
"""
import json
from typing import Dict, List, Any, Optional
from openai import OpenAI

from .base import BaseLLM


class R9SLLM(BaseLLM):
    """R9S API实现（基于OpenAI兼容接口）"""

    def __init__(self, api_key: str, model: str = "r9s-1-5-pro-32k-250115", **kwargs):
        """
        初始化R9S LLM接口

        Args:
            api_key: R9S API密钥
            model: R9S模型名称
            **kwargs: 其他参数，包括api_base等
        """
        super().__init__(api_key, model, **kwargs)
        api_base = kwargs.get("api_base", "https://api.r9s.ai/v1")
        self.client = OpenAI(api_key=api_key, base_url=api_base)

    def chat(self, messages: List[Dict[str, str]], functions: List[Dict[str, Any]],
            temperature: float = 0.7, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """
        与R9S进行对话，支持function calling
        """
        formatted_messages = self.format_messages(messages)
        formatted_functions = self.format_functions(functions)

        try:
            params = {
                "model": self.model,
                "messages": formatted_messages,
                "temperature": temperature,
                "max_tokens": max_tokens or 4096,
            }

            if formatted_functions:
                params["tools"] = formatted_functions
                params["tool_choice"] = "auto"

            try:
                response = self.client.chat.completions.create(**params)
                return self.parse_response(response)
            except Exception as e:
                # 某些模型（如 gpt-5.2-codex）不支持 /v1/chat/completions，
                # 需要使用 /v1/responses 端点；在收到相应错误时回退到 responses
                msg = str(e)
                if "use /v1/responses" in msg or "request_endpoint_disabled_for_model" in msg:
                    # 将消息合并为单条输入文本作为 fallback
                    prompt_parts = []
                    for m in formatted_messages:
                        role = m.get("role", "user")
                        content = m.get("content", "")
                        prompt_parts.append(f"[{role}] {content}")
                    prompt = "\n".join(prompt_parts)

                    try:
                        resp = self.client.responses.create(model=self.model, input=prompt)
                        # 尝试解析 responses 格式的返回
                        # 优先使用常见字段
                        if hasattr(resp, "output_text") and resp.output_text:
                            return {"content": resp.output_text, "function_call": None}
                        if hasattr(resp, "output") and len(resp.output) > 0:
                            # output 可能包含多个块，尝试拼接 text
                            texts = []
                            for out in resp.output:
                                if hasattr(out, "content") and isinstance(out.content, list):
                                    for c in out.content:
                                        if isinstance(c, dict) and c.get("type") == "output_text":
                                            texts.append(c.get("text", ""))
                                elif isinstance(out, str):
                                    texts.append(out)
                            return {"content": "".join(texts), "function_call": None}
                        # 作为最后手段返回原始对象字符串
                        return {"content": str(resp), "function_call": None}
                    except Exception as e2:
                        return {"content": f"与R9S API通信出错: {str(e2)}", "function_call": None, "error": str(e2)}
                else:
                    return {"content": f"与R9S API通信出错: {str(e)}", "function_call": None, "error": str(e)}

        except Exception as e:
            return {
                "content": f"与R9S API通信出错: {str(e)}",
                "function_call": None,
                "error": str(e)
            }

    def format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将消息列表规范化为R9S/OpenAI兼容格式
        """
        formatted_messages = []

        for msg in messages:
            formatted_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })

        return formatted_messages

    def format_functions(self, functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将统一格式的函数定义转换为R9S兼容的OpenAI格式"""
        formatted_tools = []
        for func in functions:
            tool = {
                "type": "function",
                "function": {
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": func.get("required", [])
                    }
                }
            }

            if "parameters" in func:
                for param_name, param_info in func["parameters"].items():
                    tool["function"]["parameters"]["properties"][param_name] = {
                        "type": param_info.get("type", "string"),
                        "description": param_info.get("description", "")
                    }

                    if "enum" in param_info:
                        tool["function"]["parameters"]["properties"][param_name]["enum"] = param_info["enum"]

            formatted_tools.append(tool)

        return formatted_tools

    def parse_response(self, response: Any) -> Dict[str, Any]:
        """解析R9S原始响应为统一格式"""
        result = {
            "content": None,
            "function_call": None,
        }

        try:
            message = response.choices[0].message

            if hasattr(message, "content") and message.content:
                result["content"] = message.content

            if hasattr(message, "tool_calls") and message.tool_calls:
                tool_call = message.tool_calls[0]
                if tool_call.type == "function":
                    function_call = tool_call.function
                    arguments = json.loads(function_call.arguments) if isinstance(function_call.arguments, str) else function_call.arguments
                    result["function_call"] = {
                        "name": function_call.name,
                        "arguments": arguments
                    }

            return result

        except Exception as e:
            result["content"] = f"解析R9S API响应出错: {str(e)}"
            result["error"] = str(e)
            return result