from typing import Protocol, List, Dict, Any


class LLM(Protocol):
    """用于 Agent 应用与 LLM 进行交互的接口协议"""

    async def invoke(
            self,
            messages: List[Dict[str, Any]],
            tools: List[Dict[str, Any]] = None,
            response_format: Dict[str, Any] = None,
            tool_choice: str = None,
    ) -> Dict[str, Any]:
        """传递消息列表、工具列表、响应格式、工具选择策略调用 LLM 接口"""
        ...

    @property
    def model_name(self) -> str:
        """只读属性，返回 LLM 的名字"""
        ...

    @property
    def temperature(self) -> float:
        """只读属性，返回 LLM 的温度"""
        ...

    @property
    def max_tokens(self) -> int:
        """只读属性，返回 LLM 的最大生成 token 数"""
        ...