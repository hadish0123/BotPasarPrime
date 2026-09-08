from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "3XSHOP"
    app_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./3xshop.db"
    jwt_secret: str = "CHANGE_ME"
    fernet_key: str = "CHANGE_ME"
    telegram_bot_token: str = ""
    central_bot_token: str = ""
    telegram_webhook_secret: str = "CHANGE_ME"
    cors_origins: str = "http://localhost:5173"
    activation_fee_toman: int = 250000
    owner_telegram_id: int | None = None
    pasarguard_timeout_seconds: float = 15
    pasarguard_base_url: str = ""
    pasarguard_api_token: str = ""
    log_level: str = "INFO"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
