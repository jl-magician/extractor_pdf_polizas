from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    DB_PATH: str = os.getenv("DB_PATH", "data/polizas.db")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    PROJECT_ROOT: Path = Path(__file__).parent.parent

    # OCR settings
    TESSERACT_CMD: str = os.getenv("TESSERACT_CMD", "tesseract")
    OCR_LANGUAGE: str = os.getenv("OCR_LANGUAGE", "spa")
    OCR_CONFIDENCE_THRESHOLD: int = int(os.getenv("OCR_CONFIDENCE_THRESHOLD", "60"))
    PAGE_SCAN_THRESHOLD: float = float(os.getenv("PAGE_SCAN_THRESHOLD", "0.80"))
    DECORATIVE_IMAGE_MIN: float = float(os.getenv("DECORATIVE_IMAGE_MIN", "0.10"))


settings = Settings()
