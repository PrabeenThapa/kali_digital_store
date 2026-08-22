"""
Auto icon / emoji resolver for products and categories.
Maps product/category name keywords → brand emoji.
Used in shop button labels and category banners.
"""

# ── Keyword → emoji map (checked in order — put more specific first) ───────
_ICON_MAP: list[tuple[tuple[str, ...], str]] = [
    # ── AI / GPT ────────────────────────────────────────────────────────────
    (("chatgpt", "chat gpt", "gpt-4", "gpt4", "openai"),            "֎"),
    (("gpt",),                                                         "💬"),
    (("claude", "anthropic"),                                          "🟣"),
    (("gemini",),                                                       "🌎"),
    (("perplexity",),                                                   "🔍"),
    (("copilot",),                                                      "🪟"),
    (("grok", "supergrok"),                                             "𝕏"),
    (("deepseek",),                                                      "🐳"),
    (("cursor",),                                                       "🖱"),
    (("lovable",),                                                      "💗"),
    (("figma",),                                                        "🖌"),
    (("railway",),                                                      "🚄"),
    (("supabase",),                                                     "⚡"),
    (("replit",),                                                       "🌀"),
    (("vercel",),                                                       "▲"),
    (("n8n",),                                                          "🔗"),
    (("warp",),                                                         "🚀"),
    (("posthog",),                                                      "🦔"),
    (("framer",),                                                       "🔲"),
    (("gamma",),                                                        "📊"),
    (("manus",),                                                        "🤲"),
    (("developer tools", "dev tools"),                                  "🛠"),
    (("midjourney",),                                                   "🎨"),
    (("dalle", "dall-e"),                                               "🖼"),
    (("stable diffusion", "stablediffusion"),                          "🎭"),
    (("sora",),                                                         "🎬"),
    (("runway",),                                                       "🎥"),
    (("veo", "antigravity"),                                            "📹"),
    (("elevenlabs", "eleven labs"),                                     "🎙"),
    (("heygen",),                                                       "🧑‍💻"),
    (("kling ai", "kling"),                                             "🎞"),
    (("higgs",),                                                        "🌟"),
    (("openart",),                                                      "🖌"),
    (("suno",),                                                         "🎼"),

    # ── Design / Creative ───────────────────────────────────────────────────
    (("canva",),                                                        "🎨"),
    (("adobe", "photoshop", "illustrator", "premiere", "acrobat"),     "🅰"),
    (("capcut", "cap cut"),                                             "✂️"),
    (("figma",),                                                        "🖌"),
    (("picsart", "pics art"),                                           "🖼"),
    (("lightroom",),                                                    "📷"),

    # ── Streaming ───────────────────────────────────────────────────────────
    (("netflix",),                                                      "📺"),
    (("disney",),                                                       "🏰"),
    (("hulu",),                                                         "💚"),
    (("hbo", "max"),                                                    "🎭"),
    (("prime video", "amazon prime"),                                   "📦"),
    (("apple tv",),                                                     "🍎"),
    (("crunchyroll",),                                                  "🍥"),
    (("twitch",),                                                       "💜"),
    (("youtube",),                                                      "▶️"),

    # ── Music ───────────────────────────────────────────────────────────────
    (("spotify",),                                                      "🎵"),
    (("apple music",),                                                  "🍎"),
    (("tidal",),                                                        "🌊"),
    (("deezer",),                                                       "🎶"),

    # ── VPN / Security ──────────────────────────────────────────────────────
    (("nordvpn", "nord vpn"),                                           "🛡"),
    (("expressvpn", "express vpn"),                                     "⚡"),
    (("surfshark",),                                                    "🦈"),
    (("protonvpn", "proton vpn", "protonmail"),                        "🟠"),
    (("1password", "one password"),                                     "🔑"),
    (("lastpass",),                                                     "🔐"),
    (("bitwarden",),                                                    "🔏"),
    (("vpn",),                                                          "🔒"),

    # ── Productivity / Office ───────────────────────────────────────────────
    (("microsoft 365", "ms 365", "office 365", "m365"),                "🪟"),
    (("microsoft", "ms "),                                              "🪟"),
    (("onedrive",),                                                     "☁️"),
    (("google one", "google workspace", "google drive"),                "🔵"),
    (("gmail",),                                                         "📧"),
    (("notion",),                                                       "📝"),
    (("quillbot",),                                                     "🪶"),
    (("chatprd",),                                                      "📑"),
    (("magic patterns", "magicpatterns"),                               "✨"),
    (("gumloop",),                                                      "🔄"),
    (("grammarly",),                                                    "✍️"),
    (("duolingo",),                                                     "🦉"),

    # ── Gaming ──────────────────────────────────────────────────────────────
    (("xbox", "game pass"),                                             "🎮"),
    (("playstation", "ps plus", "ps4", "ps5"),                         "🎯"),
    (("nintendo", "switch"),                                            "🔴"),
    (("ea play", "ea sports"),                                          "🕹"),
    (("steam",),                                                        "♨️"),
    (("epic games", "epicgames"),                                       "⚔️"),
    (("roblox",),                                                       "🧱"),

    # ── Social / Communication ──────────────────────────────────────────────
    (("whatsapp",),                                                     "🟢"),
    (("telegram",),                                                     "✈️"),
    (("instagram",),                                                    "📸"),
    (("tiktok",),                                                       "🎵"),
    (("twitter", "x.com"),                                             "𝕏"),
    (("linkedin",),                                                     "💼"),
    (("discord",),                                                      "🎮"),
    (("zoom",),                                                         "📹"),
    (("slack",),                                                        "💬"),

    # ── Cloud / Dev ─────────────────────────────────────────────────────────
    (("github", "gitlab", "bitbucket"),                                 "🐙"),
    (("aws", "amazon web"),                                             "☁️"),
    (("digitalocean",),                                                 "🌊"),
    (("cloudflare",),                                                   "🌤"),
    (("vercel",),                                                       "▲"),
    (("windsurf", "codeium"),                                           "🏄"),
    (("bolt.new", "bolt new"),                                          "⚡"),
    ((" v0 ", "v0.dev"),                                                "▲"),
    (("netlify",),                                                      "🟩"),
    (("sentry",),                                                       "🔺"),
    (("postman",),                                                      "📮"),
    (("docker",),                                                       "🐳"),
    (("huggingface", "hugging face"),                                  "🤗"),
    (("langchain",),                                                    "🦜"),
    (("sourcegraph",),                                                  "🔎"),
    (("tabnine",),                                                      "🧩"),
    (("neon",),                                                         "⚡"),
    (("planetscale",),                                                  "🪐"),
    (("render.com",),                                                   "🎨"),
    (("fly.io",),                                                       "🪰"),
    (("jetbrains",),                                                    "🧠"),
    (("heroku",),                                                       "🟣"),
    (("terraform",),                                                    "🟪"),
    (("npm",),                                                          "📦"),

    # ── Finance ─────────────────────────────────────────────────────────────
    (("bybit",),                                                         "🟡"),
    (("wallet", "crypto", "usdt", "bitcoin", "btc", "eth"),            "💸"),

    # ── Generic fallbacks by category keyword ──────────────────────────────
    (("ai ", " ai", "artificial"),                                      "🤖"),
    (("streaming",),                                                    "📺"),
    (("gaming",),                                                       "🎮"),
    (("security", "proxy", "proxies"),                                  "🔒"),
    (("education", "course", "learning"),                               "📚"),
    (("email", "mail"),                                                 "📧"),
    (("phone", "mobile", "sim"),                                        "📱"),
    (("account",),                                                      "👤"),
    (("key", "license", "activation"),                                  "🔑"),
    (("gift", "card"),                                                  "🎁"),
    (("slot",),                                                         "🎰"),
]


def auto_icon(name: str) -> str:
    """
    Return the best-match emoji icon for the given product/category name.
    Checks keywords case-insensitively. Returns empty string if no match.
    """
    lower = name.lower()
    for keywords, icon in _ICON_MAP:
        if any(kw in lower for kw in keywords):
            return icon
    return "📦"  # generic default
