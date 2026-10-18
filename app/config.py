from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    
    app_name: str = "Operations Under Pressure"
    app_version: str = "0.1.0"
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/ops_challenge"


settings = Settings()
