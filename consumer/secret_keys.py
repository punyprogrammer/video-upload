from pydantic_settings import BaseSettings, SettingsConfigDict


class SecretKeys(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    REGION_NAME: str = ""
    VIDEO_PROCESSING_QUEUE_URL: str = ""