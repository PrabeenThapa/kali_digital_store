"""
Admin Notification Bot — Handlers
Handles payment approval/rejection callbacks from the notify bot.
"""
import logging
from decimal import Decimal

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from packages.config.config import EnvKeys
from packages.database.methods import process_payment_with_referral
from packages.database.methods.audit import log_audit

logger = logging.getLogger(__name__)
router = Router()


def _approve_reject_kb(payment_uuid: str, user_id: int, amount: str, provider: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text=f"✅ Approve ${amount}",
            callback_data=f"nb_approve:{provider}:{payment_uuid}:{user_id}:{amount}"
        ),
        InlineKeyboardButton(
            text="❌ Reject",
            callback_data=f"nb_reject:{provider}:{payment_uuid}:{user_id}"
        )
    )
    return kb.as_markup()


@router.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "🔔 <b>KaliStore Admin Notifications</b>\n\n"
        "You'll receive payment approval requests here.\n"
        "Tap ✅ Approve or ❌ Reject on each notification.",
        parse_mode="HTML",
    )


async def _is_admin_user(user_id: int) -> bool:
    """Return True if user is owner or has admin management permission."""
    if user_id == EnvKeys.OWNER_ID:
        return True
    try:
        from packages.database.methods.read import check_role
        from packages.database.models.main import Permission
        perms = await check_role(user_id)
        if perms:
            return bool(perms & Permission.USERS_MANAGE) or bool(perms & Permission.OWN) or bool(perms & Permission.CATALOG_MANAGE)
    except Exception:
        pass
    return False


# ── Approve ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("nb_approve:"))
async def nb_approve_handler(call: CallbackQuery):
    """Notify bot: admin approves payment — credit balance, notify user via main bot."""
    if not await _is_admin_user(call.from_user.id):
        await call.answer("Not authorized.", show_alert=True)
        return

    # nb_approve:{provider}:{uuid}:{user_id}:{amount}
    parts = call.data.split(":")
    if len(parts) < 5:
        await call.answer("Invalid approval data.", show_alert=True)
        return

    provider = parts[1]
    payment_uuid = parts[2]
    try:
        user_id = int(parts[3])
        credited_amount = Decimal(parts[4])
    except (ValueError, Exception) as e:
        await call.answer(f"Parse error: {e}", show_alert=True)
        return

    # Credit balance via shared DB
    success, error_msg = await process_payment_with_referral(
        user_id=user_id,
        amount=credited_amount,
        provider=provider,
        external_id=payment_uuid,
        referral_percent=EnvKeys.REFERRAL_PERCENT,
    )

    if not success:
        if error_msg == "already_processed":
            await call.answer("⚠️ Already approved (by this or the main bot)!", show_alert=True)
        else:
            await call.answer(f"❌ Error: {error_msg}", show_alert=True)
        return

    # Notify user via MAIN bot
    if EnvKeys.TOKEN:
        try:
            main_bot = Bot(token=EnvKeys.TOKEN)
            await main_bot.send_message(
                chat_id=user_id,
                text=(
                    f"✅ <b>Payment Approved!</b>\n\n"
                    f"💰 <b>${credited_amount}</b> has been added to your balance.\n\n"
                    f"Thank you for your payment! 🎉"
                ),
                parse_mode="HTML",
            )
            await main_bot.session.close()
        except Exception as e:
            logger.warning(f"Could not notify user {user_id} via main bot: {e}")

    # Update the notification message
    await call.message.edit_text(
        call.message.text + f"\n\n✅ <b>APPROVED</b> — ${credited_amount} credited to user {user_id}",
        parse_mode="HTML",
        reply_markup=None,
    )
    await call.answer("✅ Payment approved and balance credited!")

    await log_audit(
        "nb_payment_approved",
        user_id=user_id,
        resource_type="Payment",
        details=f"provider={provider}, amount={credited_amount}, uuid={payment_uuid}, approved_by={call.from_user.id}",
    )


# ── Reject ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("nb_reject:"))
async def nb_reject_handler(call: CallbackQuery):
    """Notify bot: admin rejects payment — notify user via main bot."""
    if not await _is_admin_user(call.from_user.id):
        await call.answer("Not authorized.", show_alert=True)
        return

    # nb_reject:{provider}:{uuid}:{user_id}
    parts = call.data.split(":")
    if len(parts) < 4:
        await call.answer("Invalid rejection data.", show_alert=True)
        return

    provider = parts[1]
    payment_uuid = parts[2]
    try:
        user_id = int(parts[3])
    except ValueError:
        await call.answer("Invalid user ID.", show_alert=True)
        return

    # Notify user via MAIN bot
    if EnvKeys.TOKEN:
        try:
            main_bot = Bot(token=EnvKeys.TOKEN)
            await main_bot.send_message(
                chat_id=user_id,
                text=(
                    "❌ <b>Payment Not Verified</b>\n\n"
                    "We could not confirm your transfer.\n\n"
                    "Please make sure you:\n"
                    "• Sent the <b>correct amount</b>\n"
                    "• Included the <b>remark code</b>\n"
                    "• Sent to the correct UID/Pay ID\n\n"
                    "Try again or contact support."
                ),
                parse_mode="HTML",
            )
            await main_bot.session.close()
        except Exception as e:
            logger.warning(f"Could not notify user {user_id} via main bot: {e}")

    await call.message.edit_text(
        call.message.text + "\n\n❌ <b>REJECTED</b>",
        parse_mode="HTML",
        reply_markup=None,
    )
    await call.answer("❌ Rejected. User has been notified.")

    await log_audit(
        "nb_payment_rejected",
        user_id=user_id,
        resource_type="Payment",
        details=f"provider={provider}, uuid={payment_uuid}, rejected_by={call.from_user.id}",
    )
