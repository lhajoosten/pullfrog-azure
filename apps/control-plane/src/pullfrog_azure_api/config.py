from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PULLFROG_", extra="ignore")

    app_name: str = "Pullfrog Azure"
    app_version: str = "0.1.0"
