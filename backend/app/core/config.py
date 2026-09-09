from cryptography.fernet import Fernet, InvalidToken
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
    central_bot_enabled: bool = True
    tenant_bots_enabled: bool = True
    mini_app_url: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @field_validator("jwt_secret", "fernet_key", "telegram_webhook_secret")
    @classmethod
    def non_empty_secrets(cls, value: str) -> str:
        if value.strip() in {"", "CHANGE_ME", "changeme"}:
            return ""
        return value.strip()

    def validate_runtime(self) -> None:
        if self.activation_fee_toman < 0:
            raise RuntimeError("ACTIVATION_FEE_TOMAN cannot be negative")
        if self.rate_limit_per_minute < 1:
            raise RuntimeError("RATE_LIMIT_PER_MINUTE must be positive")
        if not 30 <= self.telegram_init_data_max_age <= 86400:
            raise RuntimeError("TELEGRAM_INIT_DATA_MAX_AGE must be between 30 and 86400 seconds")
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
            if not self.database_url.startswith("postgresql+asyncpg://"):
                raise RuntimeError("Production requires PostgreSQL via asyncpg")
            if len(self.jwt_secret) < 32:
                raise RuntimeError("JWT_SECRET must contain at least 32 characters")
            try:
                Fernet(self.fernet_key)
            except (ValueError, TypeError, InvalidToken) as exc:
                raise RuntimeError("FERNET_KEY must be a valid Fernet key") from exc
            origins = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
            if not origins or "*" in origins:
                raise RuntimeError("Production CORS_ORIGINS must contain explicit origins")


settings = Settings()
