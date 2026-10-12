from pydantic_settings import BaseSettings, SettingsConfigDict


class SecretKeys(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    COGNITO_CLIENT_ID: str = ""
    COGNITO_CLIENT_SECRET: str = ""
    REGION_NAME: str = ""
