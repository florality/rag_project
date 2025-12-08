import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class AgentConfig:
    # 平台与密钥
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    qwen_base_url: str = "https://openrouter.ai/api/v1"
    gemini_base_url: str = "https://openrouter.ai/api/v1"
    gemini_api_key: str = ""
    
    # 模型名称（全部从环境变量覆盖）
    qwen_model_name: str = "qwen-max"
    qwen2_model_name: str = "qwen2.5-72b-instruct"
    gemini_model_name: str = "google/gemini-2.0-flash-exp:free"

    # 通用推理参数
    temperature: float = 0.2
    top_p: float = 0.9
    max_output_tokens: int = 512
    max_input_tokens: int = 3000  # 添加最大输入token限制
    language: str = "zh"

    # 业务上下文
    job_description: str = "面向 AI 产品方向的简历初筛"
    scoring_dimensions: List[str] = field(
        default_factory=lambda: ["技术能力", "产品经验", "业务理解", "沟通协作"]
    )


def get_config() -> AgentConfig:
    # 优先使用环境变量中的配置
    cfg = AgentConfig(
        api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("Gemini_Api_Key") or "",
        gemini_api_key=os.getenv("Gemini_Api_Key") or "",
        base_url=os.getenv("Gemini_Base_Url") or "https://openrouter.ai/api/v1",
        gemini_base_url=os.getenv("Gemini_Base_Url") or "https://openrouter.ai/api/v1",
        gemini_model_name=os.getenv("Gemini_Model_Name") or "google/gemini-2.0-flash-exp:free",
        qwen_model_name=os.getenv("Qwen_Model_name") or "qwen-max",
        qwen2_model_name=os.getenv("Qwen2_Model_Name") or "qwen2.5-72b-instruct",
        language=os.getenv("LANGUAGE") or "zh",
    )
    
    # 记录关键配置供调试
    print(f"[config] Using API Key: {'Yes' if cfg.api_key else 'No'}")
    print(f"[config] Using Base URL: {cfg.base_url}")
    print(f"[config] Using Model: {cfg.gemini_model_name}")
    
    if not cfg.api_key:
        print("[config] Warning: No API key found in environment variables")
        
    return cfg