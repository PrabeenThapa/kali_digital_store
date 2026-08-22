"""
For each (brand, pack_index) pair below, downloads that sticker from the
AppsIconsWB pack and re-sends it as a plain photo to the owner chat. The
resulting message's photo file_id is a normal, fully-reusable Telegram
file_id (unlike the source custom-emoji sticker file_id, which Telegram
refuses to resend via send_sticker/send_photo directly).

Dumps a brand -> file_id mapping to scripts/brand_icons_output.json so it can
be pasted into bot/utils/brand_icons.py.

Run: python scripts/capture_brand_icons.py
"""
import asyncio
import json
import os

PACK_NAME = "AppsIconsWB"

# brand key -> sticker index in the AppsIconsWB pack
BRAND_INDEX = {
    "spotify": 1,
    "expressvpn": 4,
    "protonvpn": 12,
    "bybit": 16,
    "whatsapp": 20,
    "telegram": 21,
    "gemini": 37,
    "lovable": 39,
    "picsart": 50,
    "canva": 51,
    "grammarly": 54,
    "microsoft365": 61,
    "gmail": 68,
    "chatgpt": 69,
    "netflix": 126,
    "primevideo": 127,
    "linkedin": 179,
    "youtube": 180,
    "duolingo": 189,
    "crunchyroll": 197,
}


def _load_env():
    token = os.getenv("TOKEN")
    owner_id = os.getenv("OWNER_ID")
    if not token or not owner_id:
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("TOKEN=") and not token:
                        token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if line.startswith("OWNER_ID=") and not owner_id:
                        owner_id = line.split("=", 1)[1].strip().strip('"').strip("'")
    return token, owner_id


async def main():
    token, owner_id = _load_env()
    if not token or not owner_id:
        raise SystemExit("ERROR: TOKEN and OWNER_ID must be set.")

    from aiogram import Bot
    from aiogram.types import BufferedInputFile

    bot = Bot(token=token)
    result = {}
    try:
        pack = await bot.get_sticker_set(PACK_NAME)
        for brand, idx in BRAND_INDEX.items():
            sticker = pack.stickers[idx]
            buf = await bot.download(sticker.file_id)
            msg = await bot.send_photo(
                int(owner_id),
                BufferedInputFile(buf.read(), filename=f"{brand}.webp"),
                caption=f"{brand} (idx {idx})",
            )
            result[brand] = msg.photo[-1].file_id
            print(f"{brand}: captured")
            await asyncio.sleep(0.2)
    finally:
        await bot.session.close()

    out_path = os.path.join(os.path.dirname(__file__), "brand_icons_output.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nWrote {len(result)} file_ids to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
