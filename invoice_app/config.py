"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class AppConfig:
    host: str = "127.0.0.1"
    port: int = 8099
    debug: bool = False
    max_upload_files: int = 100
    max_content_length: int = 100 * 1024 * 1024
    database_path: Path = BASE_DIR / "data" / "invoices.sqlite3"

    @classmethod
    def from_env(cls) -> AppConfig:
        db_path = Path(os.environ.get("DATABASE_PATH", "data/invoices.sqlite3"))
        if not db_path.is_absolute():
            db_path = BASE_DIR / db_path

        return cls(
            host=os.environ.get("APP_HOST", "127.0.0.1"),
            port=_int_env("PORT", 8099),
            debug=os.environ.get("FLASK_DEBUG", "0") in {"1", "true", "True"},
            max_upload_files=_int_env("MAX_UPLOAD_FILES", 100),
            max_content_length=_int_env("MAX_CONTENT_LENGTH_MB", 100) * 1024 * 1024,
            database_path=db_path,
        )


CONFIG = AppConfig.from_env()
