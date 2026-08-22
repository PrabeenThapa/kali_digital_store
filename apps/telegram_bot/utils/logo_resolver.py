"""
Logo URL resolver for products.

Maps a product name to a brand domain, then to a logo image URL. Logos are
sourced from unavatar.io (a keyless aggregator over Clearbit, favicons, and
more — good consumer-brand coverage) and piped through wsrv.nl, which
rasterizes any input format (.ico / .svg / .png) into a clean PNG that
Telegram's send_photo accepts. Returns None when no brand domain matches, in
which case the detail page falls back to text-only.
"""
from __future__ import annotations
from urllib.parse import quote

# ── Brand keyword → canonical domain (most specific first) ──────────────────
_BRAND_DOMAIN_MAP: list[tuple[tuple[str, ...], str]] = [
    (("chatgpt", "chat gpt", "gpt plus", "gpt-4", "gpt4", "openai"),   "openai.com"),
    (("claude", "anthropic"),                                            "anthropic.com"),
    (("perplexity",),                                                    "perplexity.ai"),
    (("grok", "supergrok", "super grok"),                                "x.ai"),
    (("deepseek",),                                                      "deepseek.com"),
    (("gemini", "google ai", "google one"),                              "gemini.google.com"),
    (("copilot",),                                                       "microsoft.com"),

    (("kling ai", "kling"),                                              "klingai.com"),
    (("higgs",),                                                         "higgsfield.ai"),
    (("openart",),                                                       "openart.ai"),
    (("veo3", "veo ", "antigravity"),                                    "deepmind.google"),
    (("suno",),                                                          "suno.com"),
    (("midjourney",),                                                    "midjourney.com"),
    (("runway",),                                                        "runwayml.com"),

    (("capcut", "cap cut"),                                              "capcut.com"),
    (("canva",),                                                         "canva.com"),
    (("figma",),                                                         "figma.com"),
    (("adobe", "photoshop", "illustrator", "premiere", "acrobat"),       "adobe.com"),
    (("elevenlabs", "eleven labs"),                                      "elevenlabs.io"),
    (("heygen",),                                                        "heygen.com"),

    (("picsart", "pics art"),                                            "picsart.com"),
    (("meitu",),                                                         "meitu.com"),
    (("lightroom",),                                                     "adobe.com"),

    (("cursor",),                                                        "cursor.com"),
    (("lovable",),                                                       "lovable.dev"),
    (("railway",),                                                       "railway.app"),
    (("supabase",),                                                      "supabase.com"),
    (("vercel",),                                                        "vercel.com"),
    (("replit",),                                                        "replit.com"),
    (("n8n",),                                                           "n8n.io"),
    (("warp",),                                                          "warp.dev"),
    (("posthog",),                                                       "posthog.com"),
    (("gumloop",),                                                       "gumloop.com"),
    (("framer",),                                                        "framer.com"),
    (("factory",),                                                       "factory.ai"),
    (("magic patterns",),                                                "magicpatterns.com"),
    (("chatprd",),                                                       "chatprd.ai"),
    (("manus",),                                                         "manus.im"),
    (("gamma",),                                                         "gamma.app"),
    (("linear",),                                                        "linear.app"),
    (("wispr", "flow"),                                                  "wisprflow.ai"),
    (("windsurf", "codeium"),                                            "codeium.com"),
    (("bolt.new", "bolt new"),                                           "bolt.new"),
    ((" v0 ", "v0.dev"),                                                 "v0.dev"),
    (("netlify",),                                                       "netlify.com"),
    (("sentry",),                                                        "sentry.io"),
    (("postman",),                                                       "postman.com"),
    (("docker",),                                                        "docker.com"),
    (("huggingface", "hugging face"),                                   "huggingface.co"),
    (("langchain",),                                                     "langchain.com"),
    (("sourcegraph",),                                                   "sourcegraph.com"),
    (("tabnine",),                                                       "tabnine.com"),
    (("neon",),                                                          "neon.tech"),
    (("planetscale",),                                                   "planetscale.com"),
    (("render.com",),                                                    "render.com"),
    (("fly.io",),                                                        "fly.io"),
    (("jetbrains",),                                                     "jetbrains.com"),
    (("github",),                                                        "github.com"),
    (("gitlab",),                                                        "gitlab.com"),
    (("bitbucket",),                                                     "bitbucket.org"),
    (("heroku",),                                                        "heroku.com"),
    (("terraform",),                                                     "terraform.io"),
    (("npm",),                                                           "npmjs.com"),

    (("youtube",),                                                       "youtube.com"),
    (("netflix",),                                                       "netflix.com"),
    (("spotify",),                                                       "spotify.com"),

    (("nordvpn", "nord vpn"),                                            "nordvpn.com"),
    (("surfshark",),                                                     "surfshark.com"),
    (("expressvpn", "express vpn"),                                      "expressvpn.com"),
    (("protonvpn", "proton vpn"),                                        "proton.me"),

    (("linkedin",),                                                      "linkedin.com"),
    (("notion",),                                                        "notion.so"),
    (("microsoft 365", "ms 365", "office 365", "m365"),                  "microsoft.com"),
    (("coursera",),                                                      "coursera.org"),
    (("duolingo",),                                                      "duolingo.com"),
    (("quillbot",),                                                      "quillbot.com"),
    (("grammarly",),                                                     "grammarly.com"),
    (("gmail",),                                                         "gmail.com"),
    (("outlook", "hotmail"),                                             "outlook.com"),

    (("xbox", "game pass"),                                              "xbox.com"),
    (("playstation", "ps plus", "ps4", "ps5"),                           "playstation.com"),
    (("nintendo",),                                                      "nintendo.com"),
    (("steam",),                                                         "steampowered.com"),
    (("epic games",),                                                    "epicgames.com"),
    (("roblox",),                                                        "roblox.com"),
]

# unavatar.io fetches the brand logo by domain; wsrv.nl rasterizes/resizes it
# to a 256px PNG on a white background so Telegram always gets a valid photo.
_LOGO_SRC = "unavatar.io/{domain}"
_IMG_PROXY = (
    "https://wsrv.nl/?url={src}&output=png&w=256&h=256&fit=contain&bg=white"
)


def domain_for(name: str) -> str | None:
    """Return the brand domain for a product name, or None if no match."""
    if not name:
        return None
    lowered = name.lower()
    for keywords, domain in _BRAND_DOMAIN_MAP:
        if any(kw in lowered for kw in keywords):
            return domain
    return None


def logo_url_for(name: str) -> str | None:
    """Return a PNG logo image URL for a product name, or None if no brand match."""
    domain = domain_for(name)
    if not domain:
        return None
    src = quote(_LOGO_SRC.format(domain=domain), safe="")
    return _IMG_PROXY.format(src=src)
