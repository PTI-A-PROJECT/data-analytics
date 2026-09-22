from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "OSN Data & Analytics Service"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "sqlite:///./analytics.db"
    INTERNAL_TOKEN: str = "pilot-internal-secret-token"

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")


settings = Settings()
