import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # API Keys
    # Explicitly using os.getenv to match ModelScope environment variable injection style
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    BAIDU_API_KEY: str = os.getenv("BAIDU_API_KEY", "")
    
    # Model Configuration
    # 默认使用 deepseek-chat
    MODEL_NAME: str = "deepseek-chat"
    EVALUATOR_MODEL_NAME: str = "deepseek-chat" 
    
    # Constants
    MODE_ACTIVE: str = "active"
    MODE_SOCRATIC: str = "socratic"
    
    # Thresholds
    MAX_ITERATIONS: int = 5  # 防止苏格拉底模式下死循环追问的最大次数
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
