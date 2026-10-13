from pydantic_settings import BaseSettings, SettingsConfigDict


class SecretKeys(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    COGNITO_CLIENT_ID: str = ""
    COGNITO_CLIENT_SECRET: str = ""
    REGION_NAME: str = ""
    POSTGRES_DB_URL: str = ""
    S3_RAW_VIDEOS_BUCKET: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_VIDEO_THUMBNAIL_BUCKET: str = ""
