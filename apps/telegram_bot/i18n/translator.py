from __future__ import annotations
from functools import lru_cache
from typing import Any

from packages.config.config import EnvKeys
from apps.telegram_bot.core.logging import logger
from .strings import TRANSLATIONS, DEFAULT_LOCALE


@lru_cache(maxsize=1)
def get_locale() -> str:
    """Return the active locale, falling back to DEFAULT_LOCALE."""
    loc = EnvKeys.BOT_LOCALE.lower().strip()
    return loc if loc in TRANSLATIONS else DEFAULT_LOCALE


def localize(key: str, /, **kwargs: Any) -> str:
    """
    Return the translation for *key* in the active locale.

    Fallback order: active locale → DEFAULT_LOCALE → key itself.
    """
    loc = get_locale()
    text = TRANSLATIONS.get(loc, {}).get(key)
    if text is None:
        text = TRANSLATIONS.get(DEFAULT_LOCALE, {}).get(key)
    if text is None:
        text = key

    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Failed to format translation key '{key}' with kwargs {kwargs}: {e}")

    return str(text)
