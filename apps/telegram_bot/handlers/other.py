import html
import hashlib
import re
from urllib.parse import urlparse

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.enums import ChatMemberStatus

from packages.config.config import EnvKeys
from apps.telegram_bot.core.logging import logger

import time

router = Router()

_recent_welcomes: dict[tuple[int, int], float] = {}


def _should_welcome(chat_id: int, user_id: int) -> bool:
    """Deduplicate group welcome messages within 15 seconds."""
    now = time.time()
    expired = [k for k, t in _recent_welcomes.items() if now - t > 30]
    for k in expired:
        _recent_welcomes.pop(k, None)

    key = (chat_id, user_id)
    if key in _recent_welcomes and (now - _recent_welcomes[key]) < 15:
        return False
    _recent_welcomes[key] = now
    return True


def _format_user_mention(user) -> str:
    """Format a clickable user mention/tag for Telegram HTML messages."""
    raw_name = (user.full_name or user.first_name or "").strip()
    if raw_name and raw_name not in ("-", ".", "_", "None", ""):
        safe_name = html.escape(raw_name)
        return f"<a href='tg://user?id={user.id}'>{safe_name}</a>"
    elif user.username:
        return f"@{user.username}"
    return f"<a href='tg://user?id={user.id}'>Friend</a>"


@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def handle_chat_member_joined(event: ChatMemberUpdated):
    """Send warm welcome message when a new member joins the group chat."""
    new_user = event.new_chat_member.user
    if new_user.is_bot:
        return

    if not _should_welcome(event.chat.id, new_user.id):
        return

    from apps.telegram_bot.utils.menu_icons import get_menu_icons, format_icon_html
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    try:
        icons = await get_menu_icons()
        header_icon = format_icon_html("welcome_header", "🔥", icons)
        me = await event.bot.get_me()

        user_tag = _format_user_mention(new_user)
        welcome_text = (
            f"{header_icon} <b>Welcome to KALI DIGITAL STORE, {user_tag}!</b> 👋\n\n"
            f"<blockquote>"
            f"✨ We're glad to have you in our official community!\n"
            f"🛒 Explore top-tier digital products, instant delivery & 24/7 support."
            f"</blockquote>"
        )

        kb = InlineKeyboardBuilder()
        kb.button(text="🛒 Visit Shop Bot", url=f"https://t.me/{me.username}")

        await event.bot.send_message(
            chat_id=event.chat.id,
            text=welcome_text,
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )
    except Exception as e:
        logger.error(f"Error sending group welcome message on ChatMemberUpdated: {e}")


@router.message(F.new_chat_members)
async def handle_new_chat_members(message: Message):
    """Delete Telegram system join message and send a warm welcome message."""
    # 1. Delete system service message
    try:
        await message.delete()
        logger.info(f"Auto-deleted join service message in chat {message.chat.id}")
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.warning(f"Could not delete join message in chat {message.chat.id}: {e}")
    except Exception as e:
        logger.warning(f"Error deleting join message: {e}")

    # 2. Send warm welcome message for human members
    if not message.new_chat_members:
        return

    from apps.telegram_bot.utils.menu_icons import get_menu_icons, format_icon_html
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    try:
        icons = await get_menu_icons()
        header_icon = format_icon_html("welcome_header", "🔥", icons)
        me = await message.bot.get_me()

        for member in message.new_chat_members:
            if member.is_bot:
                continue

            if not _should_welcome(message.chat.id, member.id):
                continue

            user_tag = _format_user_mention(member)
            welcome_text = (
                f"{header_icon} <b>Welcome to KALI DIGITAL STORE, {user_tag}!</b> 👋\n\n"
                f"<blockquote>"
                f"✨ We're glad to have you in our official community!\n"
                f"🛒 Explore top-tier digital products, instant delivery & 24/7 support."
                f"</blockquote>"
            )

            kb = InlineKeyboardBuilder()
            kb.button(text="🛒 Visit Shop Bot", url=f"https://t.me/{me.username}")

            await message.answer(
                text=welcome_text,
                parse_mode="HTML",
                reply_markup=kb.as_markup()
            )
    except Exception as e:
        logger.error(f"Error sending group welcome message: {e}")


@router.message(F.left_chat_member)
async def handle_left_chat_member(message: Message):
    """Automatically delete 'User left the group' service messages silently."""
    try:
        await message.delete()
        logger.info(f"Auto-deleted leave service message in chat {message.chat.id}")
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.warning(f"Could not delete leave message in chat {message.chat.id}: {e}")
    except Exception as e:
        logger.warning(f"Error deleting leave message: {e}")


@router.callback_query(F.data == 'close')
async def close_callback_handler(call: CallbackQuery):
    """Delete the message when user taps close."""
    try:
        await call.message.delete()
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.warning(f"Failed to delete message: {e}")


@router.callback_query(F.data == 'dummy_button')
async def dummy_button(call: CallbackQuery):
    """Empty (dummy) button — acknowledges tap silently."""
    await call.answer("")


@router.callback_query(F.data == 'noop')
async def noop_handler(call: CallbackQuery):
    """Silent no-op for pagination indicator buttons."""
    await call.answer()


async def check_sub_channel(chat_member) -> bool:
    """Return True if the user is a member of the required channel."""
    return chat_member.status not in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)


async def get_bot_info(event) -> str:
    """Return the bot's username."""
    me = await event.bot.get_me()
    return me.username


def _any_payment_method_enabled() -> bool:
    """Return True if at least one payment method is configured."""
    return bool(
        EnvKeys.CRYPTO_PAY_TOKEN
        or EnvKeys.STARS_PER_VALUE
        or EnvKeys.TELEGRAM_PROVIDER_TOKEN
        or EnvKeys.BYBIT_UID
        or EnvKeys.BINANCE_PAY_ID
        or EnvKeys.BEP20_WALLET
        or EnvKeys.TRC20_WALLET
    )


def _parse_channel_username() -> str | None:
    """Extract channel username from CHANNEL_URL env variable."""
    channel_url = EnvKeys.CHANNEL_URL or ""
    parsed = urlparse(channel_url)
    return (
        parsed.path.lstrip('/')
        if parsed.path
        else channel_url.replace("https://t.me/", "").replace("t.me/", "").lstrip('@')
    ) or None


def generate_short_hash(text: str, length: int = 8) -> str:
    """Generate a short hash for long strings to fit in callback_data."""
    return hashlib.md5(text.encode()).hexdigest()[:length]


def is_safe_item_name(name: str) -> bool:
    """Return True if the product name is safe for display."""
    if len(name) > 100 or len(name) < 1:
        return False
    # Block control characters (0x00-0x1F, 0x7F) but allow all printable Unicode
    if re.search(r'[\x00-\x1f\x7f]', name):
        return False
    return True
