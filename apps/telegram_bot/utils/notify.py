import logging
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)

from packages.config.config import EnvKeys

async def notify_group(bot: Bot, message: str, chat_id: str | int = None, reply_markup=None) -> None:
    """
    Send a notification message to the specified admin alert group/channel.
    STRICT SECURITY: Never send alerts to public discussion groups or public channels.
    """
    forbidden_chats = [
        str(EnvKeys.SUPPORT_GROUP_ID),
        str(EnvKeys.CHANNEL_ID),
    ]

    if chat_id is None:
        chat_id = EnvKeys.ALERT_GROUP_ID
        if not chat_id or str(chat_id) in forbidden_chats:
            # Fallback to OWNER_ID directly if ALERT_GROUP_ID is unconfigured or is a public discussion group
            chat_id = EnvKeys.OWNER_ID

    # Safety check: redirect away from public discussion/support groups to OWNER_ID
    if str(chat_id) in forbidden_chats:
        chat_id = EnvKeys.OWNER_ID

    if not chat_id:
        return
            
    try:
        await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML", reply_markup=reply_markup)
    except TelegramAPIError as e:
        logger.error(f"Failed to send notification to {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error when sending notification: {e}")

async def broadcast_to_all_users(bot: Bot, message: str, reply_markup=None) -> None:
    """
    Send a broadcast message to all users in the background.
    """
    import asyncio
    from packages.services.broadcast import BroadcastManager
    from packages.database.methods import get_all_users
    
    async def _do_broadcast():
        try:
            users = await get_all_users()
            user_ids = [int(row[0]) for row in users]
            if not user_ids:
                return
            manager = BroadcastManager(bot=bot, batch_size=30, batch_delay=1.0)
            await manager.broadcast(user_ids=user_ids, text=message, parse_mode="HTML", reply_markup=reply_markup)
            logger.info(f"Successfully broadcasted to {len(user_ids)} users.")
        except Exception as e:
            logger.error(f"Failed to broadcast message to all users: {e}")
            
    # Fire and forget
    asyncio.create_task(_do_broadcast())


def mask_id(val: str | int) -> str:
    """Mask User ID or Order ID (e.g. 876543734 -> 876***734)."""
    s = str(val).strip()
    if len(s) <= 4:
        return s[0] + "***" + s[-1] if len(s) > 1 else s + "***"
    return s[:3] + "***" + s[-3:]


async def send_purchase_notification(
    bot: Bot,
    user_id: int | str,
    product_name: str,
    order_id: int | str,
    quantity: int,
    total_price: object,
    payment_method: str = "USDT Balance"
) -> None:
    """
    Send a formatted purchase alert to private admin alert group/owner.
    Never broadcasts to public groups.
    """
    import html
    from apps.telegram_bot.utils.menu_icons import get_menu_icons, format_icon_html
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    icons = await get_menu_icons()
    header_icon = format_icon_html("purchase_header", "🎉", icons)
    by_icon = format_icon_html("purchase_by", "👨", icons)
    product_icon = format_icon_html("purchase_product", "📱", icons)
    order_icon = format_icon_html("purchase_order_id", "🟦", icons)
    qty_icon = format_icon_html("purchase_qty", "✏️", icons)
    total_icon = format_icon_html("purchase_total", "📊", icons)
    method_icon = format_icon_html("purchase_method", "💳", icons)

    masked_user = mask_id(user_id)
    masked_order = mask_id(order_id)
    safe_product = html.escape(str(product_name))

    msg = (
        f"{header_icon} <b>NEW PURCHASE!</b>\n\n"
        f"<blockquote>"
        f"{by_icon} <b>By:</b> {masked_user}\n"
        f"{product_icon} <b>Product:</b> {safe_product}\n"
        f"{order_icon} <b>Order ID:</b> {masked_order}\n"
        f"{qty_icon} <b>Quantity:</b> {quantity}\n"
        f"{total_icon} <b>Total Purchase:</b> {float(total_price):g} USDT\n"
        f"{method_icon} <b>Method:</b> {payment_method}"
        f"</blockquote>"
    )

    try:
        me = await bot.get_me()
        safe_name = str(product_name).replace(' ', '_')[:50]
        btn_custom_id = icons.get("purchase_view_btn")

        kb = InlineKeyboardBuilder()
        if btn_custom_id:
            kb.button(
                text="View Product",
                url=f"https://t.me/{me.username}?start=item_{safe_name}",
                icon_custom_emoji_id=str(btn_custom_id)
            )
        else:
            kb.button(
                text="View Product ↗",
                url=f"https://t.me/{me.username}?start=item_{safe_name}"
            )
        reply_markup = kb.as_markup()
    except Exception:
        reply_markup = None

    # Send strictly to admin alert group / owner only
    await notify_group(bot, msg, reply_markup=reply_markup)
