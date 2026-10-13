from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecretKeys(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )
    REGION_NAME: str = Field(
        default="",
        validation_alias=AliasChoices("REGION_NAME", "AWS_REGION"),
    )
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET: str = ""
    S3_KEY: str = ""
    S3_PROCESSED_VIDEOS_BUCKET: str = ""
