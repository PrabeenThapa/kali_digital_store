import html
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import httpx

from apps.api.dependencies import get_current_user, get_db
from packages.config.config import EnvKeys
from packages.database.models import User, SupportMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/support", tags=["Support"])


class ChatMessageSend(BaseModel):
    message: str


class TicketCreate(BaseModel):
    subject: str = "General Inquiry"
    message: str


@router.get("/links")
async def get_support_links():
    """
    Returns the links to the Telegram Bot and community channels.
    """
    bot_user = EnvKeys.BOT_USERNAME or "kali_digital_store_bot"
    return {
        "bot_url": f"https://t.me/{bot_user.lstrip('@')}",
        "community_channel": EnvKeys.CHANNEL_URL or str(EnvKeys.ALERT_GROUP_ID),
        "support_group": str(EnvKeys.SUPPORT_GROUP_ID) if EnvKeys.SUPPORT_GROUP_ID else ""
    }


@router.get("/messages")
async def get_chat_messages(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve live chat conversation history for the current user.
    """
    res = await db.execute(
        select(SupportMessage)
        .where(SupportMessage.user_id == current_user.telegram_id)
        .order_by(SupportMessage.created_at.asc())
    )
    messages = res.scalars().all()
    
    # If no messages exist yet, return a welcoming system message
    display_name = getattr(current_user, 'username', None) or (current_user.email.split('@')[0] if current_user.email else f"User {current_user.telegram_id}")
    if not messages:
        return [
            {
                "id": 0,
                "sender": "admin",
                "sender_name": "KDS Support Team",
                "message": f"Hello {display_name}! 👋 How can we help you today? Ask any questions about your orders, payment verification, or product access.",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ]

    return [
        {
            "id": m.id,
            "sender": m.sender,
            "sender_name": m.sender_name or ("KDS Support" if m.sender == "admin" else "You"),
            "message": m.message,
            "created_at": m.created_at.isoformat() if m.created_at else datetime.now(timezone.utc).isoformat(),
        }
        for m in messages
    ]


@router.post("/send")
async def send_chat_message(
    chat_req: ChatMessageSend,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    User sends a live chat message. Stores in DB and forwards alert to Telegram support channel.
    """
    text = chat_req.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    user_name = getattr(current_user, 'username', None) or (current_user.email.split('@')[0] if current_user.email else f"User {current_user.telegram_id}")
    
    # 1. Save in SupportMessage table
    msg_entry = SupportMessage(
        user_id=current_user.telegram_id,
        message=text,
        sender="user",
        sender_name=user_name
    )
    db.add(msg_entry)
    await db.commit()
    await db.refresh(msg_entry)

    # 2. Forward to Telegram Support Group
    if EnvKeys.SUPPORT_GROUP_ID and EnvKeys.TOKEN:
        safe_name = html.escape(user_name)
        user_email = html.escape(current_user.email or "Not provided")
        safe_text = html.escape(text[:2000])

        telegram_text = (
            f"💬 <b>NEW LIVE CUSTOMER CHAT MESSAGE</b>\n\n"
            f"👤 <b>Customer:</b> {safe_name} (ID: <code>{current_user.telegram_id}</code>)\n"
            f"📧 <b>Email:</b> <code>{user_email}</code>\n\n"
            f"💭 <b>Message:</b>\n"
            f"<blockquote>{safe_text}</blockquote>\n\n"
            f"<i>👉 Admins: Tap <b>Reply to Customer</b> to respond back to customer live chat & email.</i>"
        )

        inline_keyboard = [
            [
                {"text": "✉️ Reply to Customer", "callback_data": f"support_reply_{current_user.telegram_id}"}
            ]
        ]
        username_val = getattr(current_user, 'username', None)
        if username_val:
            inline_keyboard[0].append(
                {"text": "👤 Profile", "url": f"https://t.me/{username_val}"}
            )

        url = f"https://api.telegram.org/bot{EnvKeys.TOKEN}/sendMessage"
        payload = {
            "chat_id": EnvKeys.SUPPORT_GROUP_ID,
            "text": telegram_text,
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": inline_keyboard}
        }
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(url, json=payload, timeout=5.0)
        except Exception as e:
            logger.error(f"Failed to forward chat message to Telegram support group: {e}")

    return {
        "status": "success",
        "id": msg_entry.id,
        "sender": "user",
        "sender_name": user_name,
        "message": text,
        "created_at": msg_entry.created_at.isoformat() if msg_entry.created_at else datetime.now(timezone.utc).isoformat()
    }


@router.post("/tickets")
async def create_support_ticket(
    ticket: TicketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Backwards-compatible support ticket endpoint that forwards into the live chat stream.
    """
    return await send_chat_message(ChatMessageSend(message=ticket.message), db=db, current_user=current_user)
