from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    DB_PATH: str = os.getenv("DB_PATH", "data/polizas.db")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    PROJECT_ROOT: Path = Path(__file__).parent.parent


settings = Settings()
