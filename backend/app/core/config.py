from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "3XSHOP"
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/3xshop"
    jwt_secret: str = Field(default="", repr=False)
    fernet_key: str = Field(default="", repr=False)
    telegram_bot_token: str = Field(default="", repr=False)
    central_bot_token: str = Field(default="", repr=False)
    telegram_webhook_secret: str = Field(default="", repr=False)
    cors_origins: str = "http://localhost:5173"
    activation_fee_toman: int = 250000
    owner_telegram_id: int | None = None
    pasarguard_timeout_seconds: float = 15
    log_level: str = "INFO"
    rate_limit_per_minute: int = 120
    telegram_init_data_max_age: int = 300
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @field_validator("jwt_secret", "fernet_key", "telegram_webhook_secret")
    @classmethod
    def non_empty_secrets(cls, value: str) -> str:
        if value.strip() in {"", "CHANGE_ME", "changeme"}:
            return ""
        return value

    def validate_runtime(self) -> None:
        if self.app_env.lower() in {"production", "prod"}:
            required = {
                "JWT_SECRET": self.jwt_secret,
                "FERNET_KEY": self.fernet_key,
                "TELEGRAM_WEBHOOK_SECRET": self.telegram_webhook_secret,
                "CENTRAL_BOT_TOKEN": self.central_bot_token,
            }
            missing = [key for key, value in required.items() if not value]
            if missing:
                raise RuntimeError("Missing production secrets: " + ", ".join(missing))
            if not self.database_url.startswith(("postgresql+asyncpg://", "postgresql://")):
                raise RuntimeError("Production requires PostgreSQL")


settings = Settings()
