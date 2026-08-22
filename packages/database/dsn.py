import os
from pathlib import Path

from packages.config.config import EnvKeys


def dsn() -> str:
    """Return the database URL, preferring the env-var when running in Docker."""
    return os.getenv("DATABASE_URL") if Path("/.dockerenv").exists() else EnvKeys.DATABASE_URL
