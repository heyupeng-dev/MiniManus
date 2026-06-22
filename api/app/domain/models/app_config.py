from pydantic import BaseModel, HttpUrl, Field, ConfigDict


class LLMConfig(BaseModel):
    """LLM 提供商配置"""
    # 模型基础 URL 地址
    base_url: HttpUrl = "https://api.deepseek.com"
    # 模型 API 秘钥
    api_key: str = ""
    # 模型名字，默认使用 deepseek-reasoner 推理模型，传递 tools 会自动切换到 deepseek-chat
    model_name: str = "deepseek-reasoner"
    # 温度，默认设置为 0.7
    temperature: float = Field(0.7)
    # 最大输出 token 数，默认设置为 deepseek-chat 模型的最大输出限制
    max_tokens: int = Field(8192, ge=0)

class AppConfig(BaseModel):
    """应用配置信息，包含 Agent 配置、LLM 提供商配置、MCP 配置、A2A 配置"""
    # 语言模型配置
    llm_config: LLMConfig

    # Pydantic 配置，允许传递额外的字段初始化
    model_config = ConfigDict(extra="allow")