from pathlib import Path
from pydantic_settings import BaseSettings

# Absolute path to backend directory: always resolves to backend/drone_delivery.db
BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = (BACKEND_DIR / "drone_delivery.db").as_posix()


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = f"sqlite+aiosqlite:///{DEFAULT_DB_PATH}"
    telemetry_broadcast_interval: float = 2.0
    cors_origins: list[str] = ["*"]

    class Config:
        env_prefix = "DRONE_"


settings = Settings()

