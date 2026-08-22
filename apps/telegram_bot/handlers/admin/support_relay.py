"""
Live Support — Admin Relay Handler
Watches the support supergroup and handles replies to customer support tickets.
1. Handles forum topic messages (when topics are enabled).
2. Handles direct Telegram message replies to support ticket alerts.
3. Handles inline '✉️ Reply to Customer' button clicks.
4. Supports /close command inside a topic to close the ticket.
"""
import re
import html
import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from sqlalchemy import select

from packages.config.config import EnvKeys
from packages.database.engine import Database
from packages.database.models.main import User, Payments, PaymentStatus, BoughtGoods
from apps.telegram_bot.states.support import AdminSupportReplyStates, AdminDeliverItemStates
from apps.telegram_bot.handlers.user.support import get_ticket_by_topic, close_ticket_db
from packages.services.email_service import send_order_delivery_email

logger = logging.getLogger(__name__)
router = Router()


def _extract_user_id_from_text(text: str) -> int | None:
    """Extract Telegram/User ID from a ticket notification message (supports negative IDs)."""
    if not text:
        return None
    # Pattern 1: ID: <code>123456</code> or <code>-123456</code>
    match = re.search(r'ID:\s*<code>(-?\d+)</code>', text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    # Pattern 2: (ID: 123456) or User 123456
    match = re.search(r'\(ID:\s*(-?\d+)\)', text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r'User\s+(-?\d+)', text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


async def _deliver_reply_to_user(bot, target_user_id: int, reply_text: str) -> tuple[bool, str]:
    """Deliver admin reply to user's Telegram DM and/or email."""
    success_tg = False
    success_email = False
    error_msg = ""

    # 1. Send via Telegram DM (only for real positive Telegram user IDs)
    if target_user_id > 0:
        try:
            await bot.send_message(
                chat_id=target_user_id,
                text=f"🎧 <b>Support Team Response:</b>\n\n{reply_text}",
                parse_mode="HTML"
            )
            success_tg = True
        except TelegramForbiddenError:
            error_msg = "User has blocked or not started the Telegram bot."
        except Exception as e:
            error_msg = f"Telegram error: {e}"

    # 2. Check if user has an email in DB and dispatch email notification
    target_email = None
    try:
        async with Database().session() as session:
            db_user = (await session.execute(
                select(User).where(User.telegram_id == target_user_id)
            )).scalar_one_or_none()

            if db_user and db_user.email and "@" in db_user.email:
                target_email = db_user.email
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                import smtplib
                from packages.services.email_service import (
                    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_TLS
                )

                if SMTP_USER and SMTP_PASSWORD:
                    msg = MIMEMultipart("alternative")
                    msg["Subject"] = "🎧 Support Response from KDS Digital Store"
                    msg["From"] = SMTP_FROM
                    msg["To"] = db_user.email

                    html_body = f"""
                    <div style="font-family: sans-serif; background-color: #0b0f19; color: #f1f5f9; padding: 30px; border-radius: 16px;">
                        <h2 style="color: #ef4444;">🎧 KDS Support Team Response</h2>
                        <p style="font-size: 14px; line-height: 1.6; color: #cbd5e1;">
                            Hello,<br>Our support team has responded to your message:
                        </p>
                        <div style="background: rgba(255,255,255,0.05); border-left: 4px solid #ef4444; padding: 16px; border-radius: 8px; font-size: 14px; line-height: 1.6; margin: 20px 0;">
                            {html.escape(reply_text)}
                        </div>
                        <p style="font-size: 12px; color: #64748b;">
                            You can also continue the conversation on our web store dashboard.
                        </p>
                    </div>
                    """
                    msg.attach(MIMEText(reply_text, "plain"))
                    msg.attach(MIMEText(html_body, "html"))

                    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                        if SMTP_TLS:
                            server.starttls()
                        server.login(SMTP_USER, SMTP_PASSWORD)
                        server.sendmail(SMTP_FROM, [db_user.email], msg.as_string())
                    success_email = True
                else:
                    logger.info(f"📧 [DEV EMAIL LOG] Sent support reply to {db_user.email}: {reply_text}")
                    success_email = True
    except Exception as exc:
        logger.error(f"Failed to send support reply email: {exc}")

    # 3. Store message in SupportMessage table for the Web Live Chat
    try:
        from packages.database.models.main import SupportMessage
        async with Database().session() as session:
            msg_obj = SupportMessage(
                user_id=target_user_id,
                message=reply_text,
                sender="admin",
                sender_name="KDS Support Team"
            )
            session.add(msg_obj)
            await session.commit()
    except Exception as e:
        logger.warning(f"Could not store support reply in database: {e}")

    if success_tg or success_email:
        channels = []
        if success_tg:
            channels.append("Telegram DM")
        if success_email:
            channels.append(f"Email ({target_email})")
        channels.append("Web Live Chat")
        return True, f"Delivered via {' & '.join(channels)}"
    
    # If not delivered via TG or email, still succeeded via web live chat
    return True, "Delivered via Web Live Chat"


# ── 1. Inline Button: 'Reply to Customer' Callback ───────────────────────────

@router.callback_query(F.data.startswith("support_reply_"))
async def callback_support_reply(call: CallbackQuery, state: FSMContext):
    """Admin clicked '✉️ Reply to Customer' button on a ticket message."""
    try:
        target_user_id = int(call.data.replace("support_reply_", ""))
    except ValueError:
        await call.answer("Invalid User ID.", show_alert=True)
        return

    await state.set_state(AdminSupportReplyStates.waiting_for_reply)
    await state.update_data(target_user_id=target_user_id)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel Reply", callback_data="cancel_support_reply")]
    ])

    await call.message.reply(
        f"✏️ <b>Replying to Customer <code>{target_user_id}</code></b>\n\n"
        f"Type your response below. It will be delivered directly to their Telegram chat and registered email.\n\n"
        f"<i>Send /cancel or tap Cancel to abort.</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )
    await call.answer()


@router.callback_query(F.data == "cancel_support_reply")
async def callback_cancel_support_reply(call: CallbackQuery, state: FSMContext):
    """Admin canceled the reply."""
    await state.clear()
    await call.message.edit_text("❌ <i>Support reply cancelled.</i>", parse_mode="HTML")
    await call.answer("Cancelled")


# ── 2. Admin Enters Reply in State ───────────────────────────────────────────

@router.message(AdminSupportReplyStates.waiting_for_reply)
async def handle_admin_reply_text(message: Message, state: FSMContext):
    """Admin sent their reply text while in waiting_for_reply state."""
    if message.text and message.text.strip().lower() in ["/cancel", "cancel"]:
        await state.clear()
        await message.reply("❌ <i>Support reply cancelled.</i>", parse_mode="HTML")
        return

    data = await state.get_data()
    target_user_id = data.get("target_user_id")

    if not target_user_id:
        await state.clear()
        await message.reply("⚠️ Session expired. Please tap 'Reply to Customer' again.")
        return

    reply_content = message.text or (message.caption if message.caption else "")
    if not reply_content:
        await message.reply("⚠️ Please enter a text message to reply.")
        return

    ok, detail = await _deliver_reply_to_user(message.bot, target_user_id, reply_content)
    await state.clear()

    if ok:
        await message.reply(
            f"✅ <b>Reply successfully sent to Customer <code>{target_user_id}</code>!</b>\n"
            f"<i>({detail})</i>",
            parse_mode="HTML"
        )
    else:
        await message.reply(
            f"⚠️ <b>Could not deliver reply:</b> {detail}\n"
            f"<i>(The user might not have started the bot yet)</i>",
            parse_mode="HTML"
        )


# ── 3. Telegram Native Reply on Ticket Alert Message ─────────────────────────

@router.message(
    F.chat.id.in_([EnvKeys.SUPPORT_GROUP_ID, EnvKeys.ALERT_GROUP_ID]),
    F.reply_to_message.is_not(None),
    ~F.text.startswith("/")
)
async def handle_direct_telegram_reply(message: Message):
    """
    Admin uses native Telegram 'Reply' to reply to a support ticket or user notification message.
    """
    if message.from_user and message.from_user.is_bot:
        return

    replied = message.reply_to_message
    if not replied:
        return

    # Check if the replied message is from the bot and contains a User ID
    replied_text = replied.text or replied.caption or ""
    target_user_id = _extract_user_id_from_text(replied_text)

    # If replied message has an inline keyboard with support_reply_
    if not target_user_id and replied.reply_markup and replied.reply_markup.inline_keyboard:
        for row in replied.reply_markup.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("support_reply_"):
                    try:
                        target_user_id = int(btn.callback_data.replace("support_reply_", ""))
                    except ValueError:
                        pass

    if not target_user_id:
        return  # Not replying to a user ticket message, let standard group chat continue

    reply_content = message.text or (message.caption if message.caption else "")
    if not reply_content:
        return

    ok, detail = await _deliver_reply_to_user(message.bot, target_user_id, reply_content)

    if ok:
        await message.reply(
            f"✅ <b>Delivered reply to Customer <code>{target_user_id}</code>!</b>\n"
            f"<i>({detail})</i>",
            parse_mode="HTML"
        )
    else:
        await message.reply(
            f"⚠️ <b>Delivery notice:</b> {detail}",
            parse_mode="HTML"
        )


# ── 4. Forum Topic Support Relay (Supergroups with Topics) ────────────────────

@router.message(F.chat.id == EnvKeys.SUPPORT_GROUP_ID, F.message_thread_id.is_not(None))
async def support_group_topic_relay(message: Message):
    """
    Admin types in a topic inside the support forum supergroup.
    Relay their message back to the user's private chat.
    """
    if message.from_user and message.from_user.is_bot:
        return

    topic_id = message.message_thread_id
    ticket = await get_ticket_by_topic(topic_id)

    if not ticket:
        return  # Topic not linked to any active ticket

    user_id = ticket.user_id

    try:
        if message.text:
            await message.bot.send_message(
                chat_id=user_id,
                text=f"🎧 <b>Support:</b> {message.text}",
                parse_mode="HTML",
            )
        else:
            await message.copy_to(chat_id=user_id)
    except TelegramForbiddenError:
        await message.reply("⚠️ <b>Cannot deliver:</b> user has blocked the bot.", parse_mode="HTML")
    except TelegramBadRequest as e:
        logger.warning(f"Failed to relay admin message to user {user_id}: {e}")
        await message.reply(f"⚠️ Delivery failed: {e}")


@router.message(
    Command("close"),
    F.chat.id == EnvKeys.SUPPORT_GROUP_ID,
    F.message_thread_id.is_not(None),
)
async def admin_close_ticket(message: Message):
    """Admin sends /close inside a topic to close the ticket."""
    topic_id = message.message_thread_id
    ticket = await get_ticket_by_topic(topic_id)

    if not ticket:
        await message.reply("⚠️ No active ticket found for this topic.")
        return

    user_id = ticket.user_id
    await close_ticket_db(user_id)

    # Notify user
    try:
        await message.bot.send_message(
            chat_id=user_id,
            text=(
                "✅ <b>Your support ticket has been resolved.</b>\n\n"
                "Our team has marked this issue as closed.\n"
                "If you need further help, tap <b>🆘 Support</b> in the menu."
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass

    # Close and archive the topic
    try:
        await message.bot.send_message(
            chat_id=EnvKeys.SUPPORT_GROUP_ID,
            message_thread_id=topic_id,
            text="🔒 <b>Ticket closed by admin.</b>",
            parse_mode="HTML",
        )
        await message.bot.edit_forum_topic(
            chat_id=EnvKeys.SUPPORT_GROUP_ID,
            message_thread_id=topic_id,
            name=f"[CLOSED] User {user_id}",
        )
        await message.bot.close_forum_topic(
            chat_id=EnvKeys.SUPPORT_GROUP_ID,
            message_thread_id=topic_id,
        )
    except Exception as e:
        logger.warning(f"Could not archive topic {topic_id}: {e}")


# ── 5. Admin Payment Alert Panel (Approve / Deliver / Reject) ─────────────────

@router.callback_query(F.data.startswith("adm_custom_deliver_"))
async def callback_admin_custom_deliver_prompt(call: CallbackQuery, state: FSMContext):
    """Admin tapped '✍️ Deliver Custom Key/Item' to type credentials and preview before dispatch."""
    try:
        payment_id = int(call.data.replace("adm_custom_deliver_", ""))
    except ValueError:
        await call.answer("Invalid payment ID.", show_alert=True)
        return

    async with Database().session() as session:
        pmt = (await session.execute(
            select(Payments).where(Payments.id == payment_id)
        )).scalar_one_or_none()

        if not pmt:
            await call.answer("⚠️ Payment record not found.", show_alert=True)
            return

        if pmt.status == PaymentStatus.SUCCEEDED:
            await call.answer("ℹ️ This order is already fulfilled/approved.", show_alert=True)
            return

        # Fetch customer email
        customer_email = "Not provided"
        if pmt.user_id:
            user = (await session.execute(
                select(User).where(User.telegram_id == pmt.user_id)
            )).scalar_one_or_none()
            if user and user.email:
                customer_email = user.email

    ext_parts = (pmt.external_id or "").split("::")
    tx_code = ext_parts[0] if ext_parts else (pmt.external_id or "N/A")
    npr_amount = int(pmt.amount * 300)

    await state.set_state(AdminDeliverItemStates.waiting_for_content)
    await state.update_data(
        payment_id=payment_id,
        user_id=pmt.user_id,
        customer_email=customer_email,
        amount_usd=float(pmt.amount),
        amount_npr=npr_amount,
        tx_code=tx_code,
        original_msg_id=call.message.message_id,
        original_chat_id=call.message.chat.id
    )

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel Delivery", callback_data="cancel_custom_delivery")]
    ])

    await call.message.reply(
        f"✍️ <b>Enter Digital Item / Credentials to Deliver</b>\n\n"
        f"👤 <b>Customer:</b> <code>{customer_email}</code> (ID: <code>{pmt.user_id}</code>)\n"
        f"💰 <b>Amount:</b> NPR {npr_amount:,} (${float(pmt.amount):.2f} USD)\n"
        f"📌 <b>Order Reference:</b> <code>{tx_code}</code>\n\n"
        f"<i>Please type or paste the digital key, account login, or credentials below.\n"
        f"You will see a formatted preview to approve before it is dispatched to the customer's Gmail and Dashboard.</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )
    await call.answer()


@router.message(AdminDeliverItemStates.waiting_for_content)
async def handle_admin_custom_deliver_text(message: Message, state: FSMContext):
    """Admin typed the item content / credentials. Show preview for confirmation."""
    if message.text and message.text.strip().lower() in ["/cancel", "cancel"]:
        await state.clear()
        await message.reply("❌ <i>Item delivery cancelled.</i>", parse_mode="HTML")
        return

    content = message.text or (message.caption if message.caption else "")
    if not content or not content.strip():
        await message.reply("⚠️ Please send valid text credentials or digital key.")
        return

    data = await state.get_data()
    payment_id = data.get("payment_id")
    customer_email = data.get("customer_email", "N/A")
    amount_npr = data.get("amount_npr", 0)
    tx_code = data.get("tx_code", "N/A")

    await state.update_data(item_content=content.strip())
    await state.set_state(AdminDeliverItemStates.waiting_for_confirmation)

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚀 Confirm & Dispatch Now", callback_data="confirm_custom_delivery")
        ],
        [
            InlineKeyboardButton(text="✏️ Re-enter Content", callback_data="reenter_custom_delivery"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_custom_delivery")
        ]
    ])

    preview_text = (
        f"📋 <b>DELIVERY PREVIEW — REVIEW BEFORE DISPATCH</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Customer:</b> <code>{customer_email}</code>\n"
        f"🛍️ <b>Order:</b> #{payment_id} (Ref: <code>{tx_code}</code>)\n"
        f"💰 <b>Total:</b> NPR {amount_npr:,}\n\n"
        f"📦 <b>Delivered Item / Credentials:</b>\n"
        f"<pre>{html.escape(content.strip())}</pre>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🚀 <b>Automatic Delivery Destinations:</b>\n"
        f"✉️ Customer Gmail: <code>{customer_email}</code>\n"
        f"💻 Customer Dashboard: <code>/dashboard -> Purchases</code>\n\n"
        f"<i>Tap Confirm & Dispatch below to fulfill the order immediately!</i>"
    )

    await message.reply(preview_text, parse_mode="HTML", reply_markup=confirm_kb)


@router.callback_query(F.data == "reenter_custom_delivery")
async def callback_reenter_custom_delivery(call: CallbackQuery, state: FSMContext):
    """Admin wants to change the text content."""
    await state.set_state(AdminDeliverItemStates.waiting_for_content)
    await call.message.edit_text(
        "✏️ <b>Please type the corrected digital key/credentials below:</b>\n"
        "<i>Send /cancel to abort.</i>",
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "cancel_custom_delivery")
async def callback_cancel_custom_delivery(call: CallbackQuery, state: FSMContext):
    """Admin canceled the delivery."""
    await state.clear()
    await call.message.edit_text("❌ <i>Custom delivery cancelled.</i>", parse_mode="HTML")
    await call.answer("Cancelled")


@router.callback_query(F.data == "confirm_custom_delivery")
async def callback_confirm_custom_delivery(call: CallbackQuery, state: FSMContext):
    """Admin clicked Confirm & Dispatch. Deliver to Email, Dashboard, and Telegram."""
    admin_user = call.from_user
    admin_name = f"@{admin_user.username}" if admin_user.username else (admin_user.first_name or "Admin")

    data = await state.get_data()
    payment_id = data.get("payment_id")
    target_user_id = data.get("user_id")
    customer_email = data.get("customer_email")
    item_content = data.get("item_content")
    amount_usd = data.get("amount_usd", 0.0)
    amount_npr = data.get("amount_npr", 0)
    tx_code = data.get("tx_code", "N/A")

    if not payment_id or not item_content:
        await state.clear()
        await call.answer("⚠️ Session expired. Please try again.", show_alert=True)
        return

    # 1. Database Updates (BoughtGoods + Payment Succeeded)
    order_uuid = str(uuid.uuid4())
    product_title = f"Digital Delivery — Ref: {tx_code}"

    async with Database().session() as session:
        pmt = (await session.execute(
            select(Payments).where(Payments.id == payment_id)
        )).scalar_one_or_none()

        if pmt:
            pmt.status = PaymentStatus.SUCCEEDED

        if target_user_id:
            bought = BoughtGoods(
                buyer_id=target_user_id,
                item_name=product_title,
                value=item_content,
                price=Decimal(str(amount_usd)),
                bought_datetime=datetime.now(timezone.utc),
                unique_id=uuid.UUID(order_uuid)
            )
            session.add(bought)

        await session.commit()

    await state.clear()

    # 2. Dispatch High-Quality HTML Delivery Email
    if customer_email and "@" in customer_email:
        try:
            await send_order_delivery_email(
                customer_email=customer_email,
                product_name=product_title,
                quantity=1,
                amount_str=f"NPR {amount_npr:,} (${amount_usd:.2f} USD)",
                delivered_content=item_content,
                order_id=order_uuid[:8].upper(),
                tx_id=tx_code
            )
        except Exception as e:
            logger.error(f"Failed to dispatch custom delivery email: {e}")

    # 3. Notify Customer on Telegram DM if applicable
    if target_user_id and target_user_id > 0:
        try:
            await call.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"🎉 <b>YOUR ORDER HAS BEEN DELIVERED!</b>\n\n"
                    f"🛍️ <b>Item:</b> {html.escape(product_title)}\n"
                    f"💰 <b>Amount:</b> NPR {amount_npr:,}\n\n"
                    f"📦 <b>Delivered Credentials / Key:</b>\n"
                    f"<pre>{html.escape(item_content)}</pre>\n\n"
                    f"<i>Credentials are also available in your web dashboard and email.</i>"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    # 4. Update the Telegram Message with Delivery Receipt
    delivered_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Delivered by {admin_name}", callback_data="noop")]
    ])

    delivery_receipt = (
        f"✅ <b>ORDER FULFILLED & DISPATCHED!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👮 <b>Processed By:</b> {admin_name}\n"
        f"👤 <b>Customer:</b> <code>{customer_email}</code> (ID: <code>{target_user_id}</code>)\n"
        f"💰 <b>Amount:</b> NPR {amount_npr:,} (${amount_usd:.2f})\n"
        f"📌 <b>Reference:</b> <code>{tx_code}</code>\n\n"
        f"📦 <b>Delivered Content:</b>\n"
        f"<pre>{html.escape(item_content)}</pre>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✉️ <i>Dispatched to customer Gmail and added to their Web Purchases Dashboard.</i>"
    )

    await call.message.edit_text(delivery_receipt, parse_mode="HTML", reply_markup=delivered_kb)
    await call.answer("🚀 Order successfully dispatched to customer!", show_alert=True)


@router.callback_query(F.data.startswith("adm_appr_pmt_"))
async def callback_admin_approve_payment(call: CallbackQuery):
    """Admin tapped '⚡ Auto Approve' button on a payment notification."""
    admin_user = call.from_user
    admin_name = f"@{admin_user.username}" if admin_user.username else (admin_user.first_name or "Admin")

    try:
        payment_id = int(call.data.replace("adm_appr_pmt_", ""))
    except ValueError:
        await call.answer("Invalid payment ID.", show_alert=True)
        return

    async with Database().session() as session:
        pmt = (await session.execute(
            select(Payments).where(Payments.id == payment_id)
        )).scalar_one_or_none()

        if not pmt:
            await call.answer("⚠️ Payment record not found.", show_alert=True)
            return

        if pmt.status == PaymentStatus.SUCCEEDED:
            await call.answer("ℹ️ This payment has already been approved!", show_alert=True)
            return
        elif pmt.status == PaymentStatus.FAILED:
            await call.answer("⚠️ This payment was previously rejected.", show_alert=True)
            return

        # Mark succeeded
        pmt.status = PaymentStatus.SUCCEEDED

        # Credit user balance if user exists
        customer_email = None
        if pmt.user_id:
            user = (await session.execute(
                select(User).where(User.telegram_id == pmt.user_id)
            )).scalar_one_or_none()

            if user:
                user.balance += pmt.amount
                customer_email = user.email

        await session.commit()

    # 1. Notify Customer on Telegram (works for Telegram users)
    if pmt.user_id and pmt.user_id > 0:
        try:
            await call.bot.send_message(
                chat_id=pmt.user_id,
                text=(
                    f"🎉 <b>Payment Approved &amp; Verified!</b>\n\n"
                    f"Your payment of <b>NPR {int(pmt.amount * 300):,}</b> (${float(pmt.amount):.2f} USD) has been verified and processed.\n"
                    f"Your balance/order is now updated!"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    # 1b. Always store in SupportMessage for web dashboard live chat notification
    if pmt.user_id:
        try:
            from packages.database.models.main import SupportMessage
            async with Database().session() as notif_session:
                approval_msg = SupportMessage(
                    user_id=pmt.user_id,
                    sender="admin",
                    sender_name="KDS Support Team",
                    message=(
                        f"✅ Your payment of ${float(pmt.amount):.2f} USD has been approved and your balance has been credited! "
                        f"Thank you for your deposit. If you have any questions, feel free to ask here."
                    )
                )
                notif_session.add(approval_msg)
                await notif_session.commit()
        except Exception as e:
            logger.warning(f"Could not store approval SupportMessage for user {pmt.user_id}: {e}")

    # 2. Send email notification if available
    if customer_email and "@" in customer_email:
        try:
            from packages.services.email_service import (
                SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_TLS
            )
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            import smtplib

            if SMTP_USER and SMTP_PASSWORD:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = "✅ Payment Approved & Order Confirmation - KDS Digital Store"
                msg["From"] = SMTP_FROM
                msg["To"] = customer_email

                html_body = f"""
                <div style="font-family: sans-serif; background-color: #0b0f19; color: #f1f5f9; padding: 30px; border-radius: 16px;">
                    <h2 style="color: #22c55e;">✅ Payment Approved & Verified!</h2>
                    <p style="font-size: 14px; line-height: 1.6; color: #cbd5e1;">
                        Hello,<br>Your payment of <b>NPR {int(pmt.amount * 300):,}</b> (${float(pmt.amount):.2f} USD) has been approved by our team.
                    </p>
                    <p style="font-size: 13px; color: #94a3b8;">
                        Transaction Ref: <code>{html.escape(pmt.external_id)}</code>
                    </p>
                    <p style="font-size: 12px; color: #64748b; margin-top: 24px;">
                        Thank you for choosing KDS Digital Store!
                    </p>
                </div>
                """
                msg.attach(MIMEText(f"Your payment of NPR {int(pmt.amount * 300):,} has been approved.", "plain"))
                msg.attach(MIMEText(html_body, "html"))

                with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                    if SMTP_TLS:
                        server.starttls()
                    server.login(SMTP_USER, SMTP_PASSWORD)
                    server.sendmail(SMTP_FROM, [customer_email], msg.as_string())
        except Exception as e:
            logger.error(f"Failed to dispatch approval email: {e}")

    # 3. Update the Telegram alert message & keyboard
    approved_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Approved by {admin_name}", callback_data="noop")]
    ])

    orig_text = call.message.text or call.message.caption or ""
    update_text = orig_text + f"\n\n✅ <b>APPROVED & PROCESSED</b>\n👮 Approved by: {admin_name}"

    try:
        if call.message.caption:
            await call.message.edit_caption(caption=update_text, parse_mode="HTML", reply_markup=approved_kb)
        else:
            await call.message.edit_text(text=update_text, parse_mode="HTML", reply_markup=approved_kb)
    except Exception as e:
        logger.warning(f"Could not edit message after approval: {e}")

    await call.answer("✅ Payment approved and customer notified!")


@router.callback_query(F.data.startswith("adm_rej_pmt_"))
async def callback_admin_reject_payment(call: CallbackQuery):
    """Admin tapped '❌ Reject' button on a payment notification."""
    admin_user = call.from_user
    admin_name = f"@{admin_user.username}" if admin_user.username else (admin_user.first_name or "Admin")

    try:
        payment_id = int(call.data.replace("adm_rej_pmt_", ""))
    except ValueError:
        await call.answer("Invalid payment ID.", show_alert=True)
        return

    async with Database().session() as session:
        pmt = (await session.execute(
            select(Payments).where(Payments.id == payment_id)
        )).scalar_one_or_none()

        if not pmt:
            await call.answer("⚠️ Payment record not found.", show_alert=True)
            return

        if pmt.status != PaymentStatus.PENDING:
            await call.answer(f"ℹ️ Payment status is already {pmt.status}.", show_alert=True)
            return

        pmt.status = PaymentStatus.FAILED
        await session.commit()

    rejected_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"❌ Rejected by {admin_name}", callback_data="noop")]
    ])

    orig_text = call.message.text or call.message.caption or ""
    update_text = orig_text + f"\n\n❌ <b>REJECTED</b>\n👮 Rejected by: {admin_name}"

    try:
        if call.message.caption:
            await call.message.edit_caption(caption=update_text, parse_mode="HTML", reply_markup=rejected_kb)
        else:
            await call.message.edit_text(text=update_text, parse_mode="HTML", reply_markup=rejected_kb)
    except Exception as e:
        logger.warning(f"Could not edit message after rejection: {e}")

    # Notify via SupportMessage for web-only users
    if pmt.user_id:
        try:
            from packages.database.models.main import SupportMessage
            async with Database().session() as notif_session:
                rej_msg = SupportMessage(
                    user_id=pmt.user_id,
                    sender="admin",
                    sender_name="KDS Support Team",
                    message=(
                        f"❌ Your payment submission of ${float(pmt.amount):.2f} USD could not be verified and has been rejected. "
                        f"Please double-check your transaction details and contact us if you believe this is an error."
                    )
                )
                notif_session.add(rej_msg)
                await notif_session.commit()
        except Exception as e:
            logger.warning(f"Could not store rejection SupportMessage for user {pmt.user_id}: {e}")

    await call.answer("❌ Payment rejected.")


@router.callback_query(F.data == "noop")
async def callback_noop(call: CallbackQuery):
    await call.answer("This action has already been completed.")
