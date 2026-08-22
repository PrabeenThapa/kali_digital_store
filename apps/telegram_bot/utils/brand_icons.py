"""
Native Telegram brand icon resolver.

Maps a product/category name to a Telegram photo file_id captured from the
AppsIconsWB custom-emoji pack (see scripts/capture_brand_icons.py). These
render instantly via send_photo — no external network fetch — and take
priority over the unavatar.io logo in bot/utils/logo_resolver.py, which
remains as a fallback for brands not covered here.
"""
from __future__ import annotations

_BRAND_FILE_ID_MAP: list[tuple[tuple[str, ...], str]] = [
    (("chatgpt", "chat gpt", "gpt-4", "gpt4", "gpt plus", "openai"),
     "AgACAgUAAxkDAAIC82pQdyaW197PdZxGSmMk7GxsCBYaAAIxEWsbMnmAVhSDcuP9F96iAQADAgADbQADPAQ"),
    (("gemini", "google ai", "google one"),
     "AgACAgUAAxkDAAIC02pQdv1CuN3hVbe7YUFiO9J9XWIOAAIREWsbMnmAVtOtRb7TgdWqAQADAgADbQADPAQ"),
    (("lovable",),
     "AgACAgUAAxkDAAIC1WpQdwABJ4q5Jg8lO_8uy8nPVIA0aQACExFrGzJ5gFYgbLudwzJELgEAAwIAA20AAzwE"),
    (("picsart", "pics art"),
     "AgACAgUAAxkDAAIC4GpQdw5_dxzMcJYJ5oAmYKUPFhvUAAIeEWsbMnmAVhnpBROXixRGAQADAgADbQADPAQ"),
    (("canva",),
     "AgACAgUAAxkDAAIC4WpQdw8B1Uvbt9Yi6XL2_DFtjrSLAAIfEWsbMnmAVpkeT_9KOCBQAQADAgADbQADPAQ"),
    (("grammarly",),
     "AgACAgUAAxkDAAIC5GpQdxNyEDOMj8SgN7AY1bKIT5ZWAAIiEWsbMnmAVjAkOSamJfyJAQADAgADbQADPAQ"),
    (("microsoft 365", "ms 365", "office 365", "m365"),
     "AgACAgUAAxkDAAIC62pQdxwcfpKK_vy0J5jJrG-rlpIaAAIpEWsbMnmAVgEin4V5OQGwAQADAgADbQADPAQ"),
    (("gmail",),
     "AgACAgUAAxkDAAIC8mpQdyVbUSgG8D08Ykv-cA9rDxlaAAIwEWsbMnmAVueu7FCuF_h5AQADAgADbQADPAQ"),
    (("netflix",),
     "AgACAgUAAxkDAAIDLGpQd22c8yYlPAKKMovEj7ctAAHnuAACaRFrGzJ5gFYuI3zxJoEFuwEAAwIAA20AAzwE"),
    (("prime video", "amazon prime", "primevideo"),
     "AgACAgUAAxkDAAIDLWpQd28aGtvqUVx9hqM_qum76omnAAJqEWsbMnmAVvMDgENxjs44AQADAgADbQADPAQ"),
    (("linkedin",),
     "AgACAgUAAxkDAAIDYWpQd7CYgfDolh64EKMGzgWM0gFsAAKdEWsbMnmAVv89CrYvLV66AQADAgADbQADPAQ"),
    (("youtube",),
     "AgACAgUAAxkDAAIDYmpQd7F-7BNzulFnpB2fB6svAAGS3wACnhFrGzJ5gFYPubyeQsrTpAEAAwIAA20AAzwE"),
    (("duolingo",),
     "AgACAgUAAxkDAAIDa2pQd73aamNbMYiZkujy0CamMl6TAAKmEWsbMnmAVmL8DeiZFY_GAQADAgADbQADPAQ"),
    (("crunchyroll", "crunchy roll"),
     "AgACAgUAAxkDAAIDc2pQd8dVyB5XC1slu_FRBw9Q9TyhAAKuEWsbMnmAVlhzM2Dcb3GtAQADAgADbQADPAQ"),
    (("spotify",),
     "AgACAgUAAxkDAAICr2pQds2AwDXuGH9k1jqGqzHHa-YGAALtEGsbMnmAVlDKLgqTCbk6AQADAgADbQADPAQ"),
    (("expressvpn", "express vpn"),
     "AgACAgUAAxkDAAICsmpQdtLenFg5l3pDPG7LpCkyUPalAALwEGsbMnmAVuVw0RgH3YSvAQADAgADbQADPAQ"),
    (("protonvpn", "proton vpn"),
     "AgACAgUAAxkDAAICumpQdt3DqDn30wvfaCKKg1xgBc9tAAL4EGsbMnmAVlDfCx62B-_UAQADAgADbQADPAQ"),
    (("bybit",),
     "AgACAgUAAxkDAAICvmpQduIljt93uvRNaz-PPAGbNf5_AAL8EGsbMnmAVolUYlmFRbwWAQADAgADbQADPAQ"),
    (("whatsapp",),
     "AgACAgUAAxkDAAICwmpQdugdx9rdQ50cz87aj12vdEyuAAMRaxsyeYBWnDAV4TQjWJEBAAMCAANtAAM8BA"),
    (("telegram",),
     "AgACAgUAAxkDAAICw2pQdunJwm1ijO1PnVYxYinbX-UiAAIBEWsbMnmAVoYoHAWwVXrfAQADAgADbQADPAQ"),
]


def icon_file_id_for(name: str) -> str | None:
    """Return a native Telegram photo file_id for a product/category name, or None if no brand match."""
    if not name:
        return None
    lowered = name.lower()
    for keywords, file_id in _BRAND_FILE_ID_MAP:
        if any(kw in lowered for kw in keywords):
            return file_id
    return None
