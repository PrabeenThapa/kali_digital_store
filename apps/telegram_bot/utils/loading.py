"""
Loading animation helper.
Shows a custom animated premium emoji message while processing,
then the caller replaces it with the actual content.
"""
from aiogram.types import CallbackQuery, Message
from apps.telegram_bot.utils.menu_icons import get_menu_icons


async def show_loading(call: CallbackQuery, text: str = "Loading…") -> None:
    """
    Temporarily show a loading message with the configured animated emoji.
    The caller should immediately follow with edit_text() to replace it.
    """
    icons = await get_menu_icons()
    emoji_id = icons.get("loading_emoji")

    if emoji_id:
        try:
            await call.message.edit_text(
                f'<tg-emoji emoji-id="{emoji_id}">⚡</tg-emoji>',
                parse_mode="HTML"
            )
        except Exception:
            pass
    else:
        # Fallback: just answer the callback to remove the loading spinner
        try:
            await call.answer()
        except Exception:
            pass


async def get_loading_emoji_text() -> str:
    """
    Return a text string containing the loading custom emoji, or empty string.
    Use this to prefix messages with the loading emoji.
    """
    icons = await get_menu_icons()
    emoji_id = icons.get("loading_emoji")
    if emoji_id:
        # Return the raw custom emoji placeholder
        return f"<tg-emoji emoji-id=\"{emoji_id}\">⏳</tg-emoji>"
    return "⏳"
