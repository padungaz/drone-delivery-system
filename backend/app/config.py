from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./drone_delivery.db"
    telemetry_broadcast_interval: float = 2.0
    cors_origins: list[str] = ["*"]

    class Config:
        env_prefix = "DRONE_"


settings = Settings()
