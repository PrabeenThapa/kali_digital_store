"""
Category resolver for products.

Maps a product name to a canonical category label via keyword matching,
mirroring the keyword-map pattern in bot/utils/auto_icon.py.

Used to group the flat product list (local goods + reseller products) into
a category menu in the shop. Reseller products may carry an admin
`category_override`; when unset, the category is derived here.
"""
from __future__ import annotations

# ── Keyword → canonical category label (most specific first) ────────────────
_CATEGORY_MAP: list[tuple[tuple[str, ...], str]] = [
    # ── AI Video & Visuals ──────────────────────────────────────────────────
    (("kling ai", "kling"),                                              "Kling"),
    (("runwayml", "runway pro", "runway", "runwayrpo"),                  "Runway"),
    (("higgsfield", "higgs"),                                            "Higgsfield"),
    (("midjourney",),                                                    "Midjourney"),
    (("sora",),                                                         "Sora"),
    (("luma", "dream machine"),                                          "Luma AI"),
    (("suno",),                                                         "Suno"),
    (("openart",),                                                       "OpenArt"),
    (("stable diffusion", "stablediffusion", "dalle", "dall-e", "veo"),  "AI Media"),

    # ── AI Voice & Avatar ───────────────────────────────────────────────────
    (("elevenlabs", "eleven labs", "11labs"),                            "ElevenLabs"),
    (("heygen",),                                                       "HeyGen"),

    # ── AI Assistants ───────────────────────────────────────────────────────
    (("chatgpt", "chat gpt", "gpt plus", "gpt-4", "gpt4", "openai", "codex"),  "ChatGPT"),
    (("claude", "anthropic"),                                            "Claude"),
    (("perplexity",),                                                    "Perplexity"),
    (("grok", "supergrok", "super grok"),                                "Grok"),
    (("deepseek",),                                                      "DeepSeek"),
    (("gemini", "google ai", "google one"),                              "Gemini"),
    (("copilot",),                                                       "Copilot"),

    # ── Dedicated Dev & Automation Tools ────────────────────────────────────
    (("n8n",),                                                          "n8n"),
    (("replit",),                                                       "Replit"),
    (("gamma",),                                                        "Gamma"),
    (("manus",),                                                        "Manus"),
    (("supabase",),                                                     "Supabase"),
    (("cursor",),                                                       "Cursor"),
    (("lovable",),                                                      "Lovable"),
    (("framer",),                                                       "Framer"),
    (("railway",),                                                      "Railway"),
    (("vercel",),                                                       "Vercel"),
    (("warp",),                                                         "Warp"),
    (("posthog",),                                                      "PostHog"),
    (("gumloop",),                                                      "Gumloop"),
    (("chatprd",),                                                      "ChatPRD"),
    (("magic patterns", "magicpatterns"),                               "Magic Patterns"),
    (("bolt.new", "bolt new"),                                          "Bolt.new"),
    (("v0.dev", " v0 "),                                                "v0.dev"),
    (("windsurf",),                                                     "Windsurf"),

    # ── Creative / Design / Video ───────────────────────────────────────────
    (("capcut", "cap cut"),                                              "CapCut"),
    (("canva",),                                                         "Canva"),
    (("figma",),                                                         "Figma"),
    (("adobe", "photoshop", "illustrator", "premiere", "acrobat"),       "Adobe"),
    (("picsart", "pics art", "meitu", "lightroom"),                      "Photo Editing"),

    # ── Productivity & Education ────────────────────────────────────────────
    (("quillbot",),                                                      "QuillBot"),
    (("grammarly",),                                                    "Grammarly"),
    (("notion",),                                                        "Notion"),
    (("duolingo",),                                                     "Duolingo"),
    (("coursera",),                                                     "Coursera"),
    (("linkedin",),                                                      "LinkedIn"),
    (("microsoft 365", "ms 365", "office 365", "m365"),                  "Microsoft 365"),
    (("gmail",),                                                         "Gmail"),
    (("outlook", "hotmail", "mail", "email"),                            "Email"),

    # ── Streaming / Media ───────────────────────────────────────────────────
    (("youtube",),                                                       "YouTube"),
    (("netflix",),                                                       "Netflix"),
    (("spotify",),                                                       "Spotify"),

    # ── VPN / Security ──────────────────────────────────────────────────────
    (("nordvpn", "nord vpn"),                                            "NordVPN"),
    (("surfshark",),                                                     "Surfshark"),
    (("expressvpn", "express vpn"),                                      "ExpressVPN"),
    (("protonvpn", "proton vpn", "protonmail"),                          "ProtonVPN"),
    (("vpn",),                                                           "VPN"),

    # ── Gaming ──────────────────────────────────────────────────────────────
    (("xbox", "game pass", "playstation", "ps plus", "ps4", "ps5",
      "nintendo", "steam", "epic games", "roblox"),                      "Gaming"),

    # ── Fallback groups for remaining general tools ─────────────────────────
    (("developer tools", "dev tools", "docker", "postman", "huggingface",
      "digitalocean", "heroku", "cloudflare"),                           "Developer Tools"),
]

# Canonical list of labels used elsewhere (admin override validation, menus)
KNOWN_CATEGORIES: list[str] = list(dict.fromkeys([label for _, label in _CATEGORY_MAP]))
FALLBACK_CATEGORY = "Other"


def resolve_category(name: str) -> str:
    """Return the canonical category label for a product name, or 'Other'."""
    if not name:
        return FALLBACK_CATEGORY
    lowered = name.lower()
    for keywords, label in _CATEGORY_MAP:
        if any(kw in lowered for kw in keywords):
            return label
    return FALLBACK_CATEGORY


async def seed_known_categories():
    """Seed the database Categories table with KNOWN_CATEGORIES on startup."""
    from packages.database.engine import Database
    from packages.database.models.main import Categories
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy import select

    async with Database().session() as session:
        for cat_name in KNOWN_CATEGORIES + [FALLBACK_CATEGORY]:
            # Check if category exists by original_name OR name
            stmt = select(Categories).where(
                (Categories.original_name == cat_name) | (Categories.name == cat_name)
            )
            existing = (await session.execute(stmt)).scalars().first()
            if not existing:
                new_cat = Categories(name=cat_name, original_name=cat_name)
                session.add(new_cat)
                try:
                    await session.commit()
                except IntegrityError:
                    await session.rollback()
