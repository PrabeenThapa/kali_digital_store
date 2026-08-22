"""
Sends every sticker in a Telegram sticker pack to the bot owner, each preceded
by a small "[index]" text label, so you can identify which index = which brand
by eye and reply back with a mapping.

Unlike custom emoji, real stickers render for ALL users (not just Premium),
so whatever we wire up here will actually display for every shop visitor.

Usage:
    python scripts/preview_sticker_pack.py <pack_shortname> [pack_shortname2 ...]

Pack shortname is the part after t.me/addstickers/ in the pack's share link.
"""
import asyncio
import os
import sys


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
    if len(sys.argv) < 2:
        print("Usage: python scripts/preview_sticker_pack.py <pack_shortname> [more_packs...]", file=sys.stderr)
        sys.exit(1)

    pack_names = sys.argv[1:]
    token, owner_id = _load_env()
    if not token or not owner_id:
        print("ERROR: TOKEN and OWNER_ID must be set.", file=sys.stderr)
        sys.exit(1)

    from aiogram import Bot
    from aiogram.types import BufferedInputFile

    bot = Bot(token=token)
    try:
        for pack_name in pack_names:
            try:
                pack = await bot.get_sticker_set(pack_name)
            except Exception as e:
                await bot.send_message(int(owner_id), f"ERROR fetching pack '{pack_name}': {e}")
                print(f"ERROR fetching pack '{pack_name}': {e}", file=sys.stderr)
                continue

            await bot.send_message(
                int(owner_id),
                f"📦 Pack: {pack.title} ({pack_name}) — {len(pack.stickers)} stickers\n"
                f"Reply with mapping like:\nchatgpt={pack_name}:0\nnetflix={pack_name}:3",
            )
            for idx, s in enumerate(pack.stickers):
                caption = f"[{pack_name}:{idx}]"
                try:
                    # custom_emoji / regular stickers can't go through send_sticker
                    # as a plain message — download the raw file and resend as a
                    # photo instead, which renders for every user, no restrictions.
                    buf = await bot.download(s.file_id)
                    await bot.send_photo(
                        int(owner_id),
                        BufferedInputFile(buf.read(), filename=f"{idx}.webp"),
                        caption=caption,
                    )
                except Exception as e:
                    await bot.send_message(int(owner_id), f"{caption} ERROR: {e}")
                await asyncio.sleep(0.2)

        await bot.send_message(int(owner_id), "✅ Done sending all packs.")
        print("Done. Check your Telegram.")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
