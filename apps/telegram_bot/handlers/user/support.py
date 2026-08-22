"""
Live Support — User Side Handler
When user taps Support → creates/resumes a Forum Topic in the support group.
All messages the user sends while in SupportStates.chatting are relayed to their topic.
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

from packages.config.config import EnvKeys
from apps.telegram_bot.states.support import SupportStates
from packages.database.engine import Database
from packages.database.models.main import SupportTicket
from sqlalchemy import select

logger = logging.getLogger(__name__)
router = Router()


# ── DB helpers ────────────────────────────────────────────────────────────────

async def get_open_ticket(user_id: int) -> SupportTicket | None:
    async with Database().session() as s:
        result = await s.execute(
            select(SupportTicket)
            .where(SupportTicket.user_id == user_id, SupportTicket.status == 'open')
        )
        return result.scalars().first()


async def create_ticket(user_id: int, topic_id: int) -> SupportTicket:
    async with Database().session() as s:
        ticket = SupportTicket(user_id=user_id, topic_id=topic_id)
        s.add(ticket)
        await s.commit()
        await s.refresh(ticket)
        return ticket


async def close_ticket_db(user_id: int) -> int | None:
    """Mark the user's open ticket as closed. Returns topic_id or None."""
    async with Database().session() as s:
        result = await s.execute(
            select(SupportTicket)
            .where(SupportTicket.user_id == user_id, SupportTicket.status == 'open')
        )
        ticket = result.scalars().first()
        if ticket:
            topic_id = ticket.topic_id
            ticket.status = 'closed'
            await s.commit()
            return topic_id
    return None


async def get_ticket_by_topic(topic_id: int) -> SupportTicket | None:
    async with Database().session() as s:
        result = await s.execute(
            select(SupportTicket)
            .where(SupportTicket.topic_id == topic_id, SupportTicket.status == 'open')
        )
        return result.scalars().first()


# ── Support entry point ───────────────────────────────────────────────────────

@router.callback_query(F.data == "support")
async def support_handler(call: CallbackQuery, state: FSMContext):
    """User tapped Support — open or resume their support thread."""
    if not EnvKeys.SUPPORT_GROUP_ID:
        await call.answer("⚠️ Support is not configured yet. Please contact admin directly.", show_alert=True)
        return

    user_id = call.from_user.id
    user = call.from_user
    username = f"@{user.username}" if user.username else user.first_name or f"User {user_id}"

    # Check for existing open ticket
    existing = await get_open_ticket(user_id)

    if existing:
        # Resume existing ticket
        await state.set_state(SupportStates.chatting)
        await state.update_data(support_topic_id=existing.topic_id)

        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="❌ Close Ticket", callback_data="support_close"))
        kb.row(InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu"))

        await call.message.edit_text(
            "<b>Live Support</b>\n\n"
            "You already have an open ticket.\n"
            "Just type your message below and our team will respond shortly.\n\n"
            "Tap <b>Close Ticket</b> when your issue is resolved.",
            parse_mode="HTML",
            reply_markup=kb.as_markup(),
        )
        return

    # Create a new Forum Topic for this user
    topic_name = f"👤 {username} (ID: {user_id})"
    try:
        topic = await call.bot.create_forum_topic(
            chat_id=EnvKeys.SUPPORT_GROUP_ID,
            name=topic_name,
        )
        topic_id = topic.message_thread_id
    except TelegramBadRequest as e:
        logger.error(f"Failed to create forum topic for user {user_id}: {e}")
        await call.answer(
            "⚠️ Could not open support chat. Please try again or contact admin.",
            show_alert=True
        )
        return

    # Save to DB
    await create_ticket(user_id=user_id, topic_id=topic_id)

    # Post welcome card in the topic
    try:
        tg_link = f"tg://user?id={user_id}"
        await call.bot.send_message(
            chat_id=EnvKeys.SUPPORT_GROUP_ID,
            message_thread_id=topic_id,
            text=(
                f"🎫 <b>New Support Ticket</b>\n\n"
                f"👤 User: <a href='{tg_link}'>{username}</a> (ID: <code>{user_id}</code>)\n"
                f"📅 Opened: just now\n\n"
                f"<i>Reply here — messages forward to the user automatically.</i>\n"
                f"Send /close in this topic to close the ticket."
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not post welcome card to topic {topic_id}: {e}")

    await state.set_state(SupportStates.chatting)
    await state.update_data(support_topic_id=topic_id)

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="❌ Close Ticket", callback_data="support_close"))
    kb.row(InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu"))

    await call.message.edit_text(
        "<b>Live Support — Connected</b>\n\n"
        "Your support chat is open. Just type your message below.\n"
        "Our team will respond shortly.\n\n"
        "Tap <b>Close Ticket</b> when your issue is resolved.",
        parse_mode="HTML",
        reply_markup=kb.as_markup(),
    )


# ── Relay user messages to topic ─────────────────────────────────────────────

@router.message(SupportStates.chatting)
async def support_message_relay(message: Message, state: FSMContext):
    """Forward every user message to their support topic."""
    if not EnvKeys.SUPPORT_GROUP_ID:
        return

    data = await state.get_data()
    topic_id = data.get("support_topic_id")
    if not topic_id:
        await message.answer("⚠️ Session expired. Tap Support again to reconnect.")
        await state.clear()
        return

    user = message.from_user


    try:
        # Copy message to the topic (preserves photo, voice, sticker, etc.)
        await message.copy_to(
            chat_id=EnvKeys.SUPPORT_GROUP_ID,
            message_thread_id=topic_id,
        )
    except TelegramBadRequest as e:
        logger.error(f"Failed to relay message to topic {topic_id}: {e}")
        await message.answer("⚠️ Failed to send. Please try again.")
        return

    # Small confirmation tick (non-intrusive)
    try:
        await message.react([{"type": "emoji", "emoji": "✅"}])
    except Exception:
        pass  # React not supported in all clients


# ── Close ticket ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "support_close")
async def close_ticket_handler(call: CallbackQuery, state: FSMContext):
    """User closes their support ticket."""
    user_id = call.from_user.id
    topic_id = await close_ticket_db(user_id)

    await state.clear()

    if topic_id and EnvKeys.SUPPORT_GROUP_ID:
        try:
            # Rename topic to show it's closed
            await call.bot.edit_forum_topic(
                chat_id=EnvKeys.SUPPORT_GROUP_ID,
                message_thread_id=topic_id,
                name=f"[CLOSED] User {user_id}",
            )
            await call.bot.close_forum_topic(
                chat_id=EnvKeys.SUPPORT_GROUP_ID,
                message_thread_id=topic_id,
            )
            await call.bot.send_message(
                chat_id=EnvKeys.SUPPORT_GROUP_ID,
                message_thread_id=topic_id,
                text="🔒 <b>Ticket closed by user.</b>",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Could not close topic {topic_id}: {e}")

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💬 New Ticket", callback_data="support"))
    kb.row(InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu"))

    await call.message.edit_text(
        "<b>Ticket Closed</b>\n\n"
        "Your support ticket has been closed.\n"
        "If you need help again, tap <b>New Ticket</b>.",
        parse_mode="HTML",
        reply_markup=kb.as_markup(),
    )
