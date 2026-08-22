"""
Sends visual previews of all 3 emoji packs to the bot owner.
Each message shows 15 emoji labeled by [pack:index] so you can identify brands.
Run: python scripts/preview_all_packs.py
"""
import asyncio
import os
import sys

PACKS = ["namlc1Emoji", "ApplicationEmoji", "ADROITPACKE"]
CHUNK = 15


async def main():
    token = os.getenv("TOKEN")
    owner_id = os.getenv("OWNER_ID")
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("TOKEN=") and not token:
                    token = line.split("=", 1)[1].strip().strip('"\'')
                if line.startswith("OWNER_ID=") and not owner_id:
                    owner_id = line.split("=", 1)[1].strip().strip('"\'')

    if not token or not owner_id:
        print("ERROR: TOKEN and OWNER_ID must be set.", file=sys.stderr)
        sys.exit(1)

    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode="HTML"))

    for pack_name in PACKS:
        try:
            pack = await bot.get_sticker_set(pack_name)
        except Exception as e:
            print(f"ERROR fetching {pack_name}: {e}", file=sys.stderr)
            continue

        stickers = pack.stickers
        print(f"{pack_name}: {len(stickers)} stickers")

        await bot.send_message(
            int(owner_id),
            f"📦 <b>Pack: {pack_name}</b> ({len(stickers)} emoji)\n"
            f"<i>Format: [index] emoji</i>"
        )
        await asyncio.sleep(0.3)

        for start in range(0, len(stickers), CHUNK):
            chunk = stickers[start:start + CHUNK]
            lines = []
            for s in chunk:
                idx = start + chunk.index(s)
                eid = getattr(s, "custom_emoji_id", None) or s.file_unique_id
                lines.append(f'[{idx}] <tg-emoji emoji-id="{eid}">📱</tg-emoji>')
            await bot.send_message(int(owner_id), "  ".join(lines))
            await asyncio.sleep(0.4)

    await bot.send_message(
        int(owner_id),
        "✅ All packs sent!\n\n"
        "Reply with brand→index mappings, e.g.:\n"
        "<code>chatgpt = ApplicationEmoji:5\n"
        "gemini = ApplicationEmoji:12\n"
        "capcut = ADROITPACKE:3</code>"
    )
    print("Done — check Telegram.")
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
