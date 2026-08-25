import html
import httpx
import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from decimal import Decimal
import uuid
from datetime import datetime, timezone

from apps.api.dependencies import get_db, get_current_user, get_optional_current_user
from packages.database.models import (
    User, Goods, BoughtGoods, ItemValues, ResellerProduct, 
    ResellerSource, ResellerOrder, BotSettings, Payments, PaymentStatus
)
from packages.database.methods.transactions import buy_item_transaction
from packages.services.reseller import fulfill_reseller_purchase
from packages.services.email_service import send_order_delivery_email
from packages.services.geo_service import is_nepal_client
from packages.config.config import EnvKeys


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["Payments"])


class CartItem(BaseModel):
    product_id: str
    quantity: int = 1


class CheckoutRequest(BaseModel):
    items: List[CartItem]
    promo_code: Optional[str] = None
    payment_method: str = "balance"
    customer_email: Optional[str] = None


class TopupRequest(BaseModel):
    amount: float
    method: str = "cryptopay"  # cryptopay, bep20, trc20, bybit, binance, nepal_qr


class NepalPaymentSubmitRequest(BaseModel):
    tx_id: str
    amount_usd: float
    amount_npr: float
    note: Optional[str] = None
    product_id: Optional[str] = None
    customer_email: Optional[str] = None
    proof_image: Optional[str] = None


class BybitInitRequest(BaseModel):
    amount_usd: float


class BybitVerifyRequest(BaseModel):
    payment_uuid: str
    unique_amount: float
    credited_amount: float
    created_at_ms: int
    tx_id: Optional[str] = None  # optional Bybit Transfer ID for direct lookup
    proof_image: Optional[str] = None


class BinanceInitRequest(BaseModel):
    amount_usd: float


class BinanceVerifyRequest(BaseModel):
    payment_uuid: str
    unique_amount: float
    credited_amount: float
    remark_code: str
    created_at_ms: int
    proof_image: Optional[str] = None


def _get_target_alert_chats() -> list[int | str]:
    """Returns unique target chat IDs for admin payment alerts (ALERT_GROUP_ID or OWNER_ID only, never public support/discussion groups)."""
    chats = []
    forbidden_chats = [str(EnvKeys.SUPPORT_GROUP_ID), str(EnvKeys.CHANNEL_ID)]
    
    if EnvKeys.ALERT_GROUP_ID and str(EnvKeys.ALERT_GROUP_ID) not in forbidden_chats and EnvKeys.ALERT_GROUP_ID not in chats:
        chats.append(EnvKeys.ALERT_GROUP_ID)
        
    if EnvKeys.OWNER_ID and EnvKeys.OWNER_ID not in chats:
        chats.append(EnvKeys.OWNER_ID)
        
    return chats


async def send_kds_channel_notification(message: str, reply_markup: Optional[dict] = None) -> None:
    """Send real-time alert to Customer Support and Payment Channels."""
    if not EnvKeys.TOKEN:
        return
    targets = _get_target_alert_chats()
    if not targets:
        return
    url = f"https://api.telegram.org/bot{EnvKeys.TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        for chat_id in targets:
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            try:
                await client.post(url, json=payload, timeout=5.0)
            except Exception as e:
                logger.error(f"Failed to post alert to chat {chat_id}: {e}")


async def send_kds_channel_photo(photo_bytes: bytes, caption: str, reply_markup: Optional[dict] = None) -> None:
    """Send receipt photo with caption to Customer Support and Payment Channels."""
    if not EnvKeys.TOKEN:
        return
    targets = _get_target_alert_chats()
    if not targets:
        return
    import json
    url = f"https://api.telegram.org/bot{EnvKeys.TOKEN}/sendPhoto"
    async with httpx.AsyncClient() as client:
        for chat_id in targets:
            files = {"photo": ("receipt.jpg", photo_bytes, "image/jpeg")}
            data = {"chat_id": str(chat_id), "caption": caption, "parse_mode": "HTML"}
            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup)
            try:
                await client.post(url, data=data, files=files, timeout=10.0)
            except Exception as e:
                logger.error(f"Failed to post receipt photo to chat {chat_id}: {e}")


@router.get("/nepal-qr")
async def get_nepal_qr_details(db: AsyncSession = Depends(get_db)):
    """Public endpoint to fetch active Nepal QR Code payment configuration and Coming Soon banner status."""
    keys = ["nepal_qr_url", "nepal_qr_title", "nepal_qr_account_name", "nepal_qr_account_id", "nepal_qr_instructions", "nepal_coming_soon", "nepal_coming_soon_text"]
    res = await db.execute(select(BotSettings).where(BotSettings.key.in_(keys)))
    settings = {s.key: s.value for s in res.scalars().all()}
    return {
        "qr_url": settings.get("nepal_qr_url") or "https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=eSewa-Fonepay-Pay-KaliStore",
        "title": settings.get("nepal_qr_title") or "eSewa / Khalti / Fonepay Direct QR",
        "account_name": settings.get("nepal_qr_account_name") or "Kali Store Nepal",
        "account_id": settings.get("nepal_qr_account_id") or "9800000000",
        "instructions": settings.get("nepal_qr_instructions") or "Scan QR with eSewa/Khalti/Fonepay, transfer exact NPR amount, then submit your Tx Reference ID below.",
        "coming_soon": settings.get("nepal_coming_soon", "true").lower() == "true",
        "coming_soon_text": settings.get("nepal_coming_soon_text") or "🇳🇵 Nepal Store Direct Local Payment Gateway & Catalog Expansion is Coming Soon! Stay tuned as we roll out instant eSewa & Khalti automated API verification.",
    }


@router.post("/nepal-submit")
async def submit_nepal_qr_payment(
    request: NepalPaymentSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Submit a Nepal eSewa/Khalti/Fonepay QR payment transaction reference ID & screenshot proof.
    Logs payment, alerts KDS payment channel with photo, and records destination customer email.
    """
    tx_id = request.tx_id.strip()
    if not tx_id or len(tx_id) < 3:
        raise HTTPException(status_code=400, detail="Please enter a valid Transaction ID / Reference Code")

    payment_uuid = f"nepal_{uuid.uuid4().hex[:12]}"
    dest_email = (request.customer_email or (current_user.email if current_user else "") or "").strip()
    
    # Associate user
    user_id = None
    if current_user:
        user_id = current_user.telegram_id
        user_name = current_user.email or f"User #{user_id}"
    elif dest_email:
        # Check if email is already registered
        existing = (await db.execute(select(User).where(User.email == dest_email))).scalar_one_or_none()
        if existing:
            user_id = existing.telegram_id
            user_name = existing.email or dest_email
        else:
            # Auto-create user account for this email
            import hashlib
            new_id = int(hashlib.md5(dest_email.encode()).hexdigest()[:8], 16)
            ex_id = (await db.execute(select(User).where(User.telegram_id == new_id))).scalar_one_or_none()
            if not ex_id:
                new_user = User(
                    telegram_id=new_id,
                    email=dest_email,
                    balance=Decimal("0.0"),
                    registration_date=datetime.now(timezone.utc)
                )
                db.add(new_user)
                await db.flush()
                user_id = new_id
            else:
                user_id = ex_id.telegram_id
            user_name = dest_email
    else:
        user_name = "Guest Customer"

    # Store email inside note for clear tracking
    full_note = request.note or ""
    if dest_email and f"[Email: {dest_email}]" not in full_note:
        full_note = f"[Email: {dest_email}] " + full_note

    # Create pending payment in DB
    pmt = Payments(
        provider="nepal_qr",
        external_id=f"{tx_id}::{payment_uuid}",
        user_id=user_id,
        amount=Decimal(str(request.amount_usd)),
        currency="USD",
        status=PaymentStatus.PENDING,
    )
    db.add(pmt)
    await db.commit()
    await db.refresh(pmt)

    # Parse screenshot photo if uploaded
    photo_bytes = None
    if request.proof_image and "base64," in request.proof_image:
        try:
            import base64
            _, encoded = request.proof_image.split("base64,", 1)
            photo_bytes = base64.b64decode(encoded)
        except Exception as e:
            logger.warning(f"Could not decode payment proof image: {e}")

    # Dispatch rich notification to KDS payment channel
    safe_name = html.escape(str(user_name))
    email_str = html.escape(dest_email) if dest_email else "<i>Not specified</i>"
    safe_tx = html.escape(tx_id)
    safe_note = html.escape(full_note or "N/A")

    channel_msg = (
        f"🇳🇵 <b>NEW NEPAL PAYMENT SUBMITTED!</b>\n\n"
        f"👤 <b>Customer:</b> {safe_name} (ID: <code>{user_id}</code>)\n"
        f"📧 <b>Delivery Email:</b> <code>{email_str}</code>\n"
        f"💰 <b>Amount:</b> <b>NPR {request.amount_npr:,.2f}</b> (${request.amount_usd:.2f} USD)\n"
        f"📌 <b>Tx / Reference ID:</b> <code>{safe_tx}</code>\n"
        f"📝 <b>Order Details:</b> {safe_note}\n"
        f"📷 <b>Receipt Attached:</b> {'Yes (Photo below)' if photo_bytes else 'No'}\n\n"
        f"⚡ <i>Action: Tap <b>Approve & Deliver</b> to credit/fulfill automatically!</i>"
    )

    action_keyboard = {
        "inline_keyboard": [
            [
                {"text": "⚡ Auto Approve", "callback_data": f"adm_appr_pmt_{pmt.id}"},
                {"text": "✍️ Deliver Key/Item", "callback_data": f"adm_custom_deliver_{pmt.id}"}
            ],
            [
                {"text": "❌ Reject", "callback_data": f"adm_rej_pmt_{pmt.id}"},
                {"text": "✉️ Reply to Customer", "callback_data": f"support_reply_{user_id}"}
            ]
        ]
    }

    if photo_bytes:
        asyncio.create_task(send_kds_channel_photo(photo_bytes, channel_msg, reply_markup=action_keyboard))
    else:
        asyncio.create_task(send_kds_channel_notification(channel_msg, reply_markup=action_keyboard))

    return {
        "status": "success",
        "message": "Payment reference submitted! Order credentials will be automatically delivered to your email upon admin verification.",
        "payment_uuid": payment_uuid,
        "tx_id": tx_id,
        "amount_npr": request.amount_npr,
        "customer_email": dest_email,
        "has_receipt_image": photo_bytes is not None,
    }


@router.post("/checkout")
async def checkout(
    request: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Process web customer checkout, deduct wallet balance, deliver digital keys,
    and automatically send the credentials to the customer's email.
    """
    if not request.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    item = request.items[0]
    prod_id_str = str(item.product_id)
    qty = max(1, item.quantity)
    promo_code = request.promo_code.strip() if request.promo_code else None
    target_email = (request.customer_email or current_user.email or "").strip()

    # Case A: Reseller Product (e.g. reseller_5)
    if prod_id_str.startswith("reseller_"):
        res_id = int(prod_id_str.replace("reseller_", ""))
        rprod = (await db.execute(
            select(ResellerProduct, ResellerSource)
            .join(ResellerSource, ResellerProduct.source_id == ResellerSource.id)
            .where(ResellerProduct.id == res_id, ResellerProduct.is_enabled == True)
        )).first()

        if not rprod:
            raise HTTPException(status_code=404, detail="Reseller product unavailable")

        p, src = rprod
        unit_price = Decimal(str(p.sell_price))
        total_price = unit_price * qty

        # Check user balance
        if current_user.balance < total_price:
            npr_req = int(total_price * 300)
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient balance. Required: NPR {npr_req:,} (${total_price:.2f}), Balance: NPR {int(current_user.balance * 300):,}"
            )

        # Deduct balance
        current_user.balance -= total_price
        
        # Create ResellerOrder record
        idempotency = f"web_{uuid.uuid4().hex[:12]}"
        res_order = ResellerOrder(
            user_id=current_user.telegram_id,
            source_id=src.id,
            reseller_product_id=p.id,
            product_name=p.name,
            product_type=p.product_type,
            quantity=qty,
            cost_price=Decimal(str(p.cost_price or 0)),
            sell_price=unit_price,
            total_cost=Decimal(str(p.cost_price or 0)) * qty,
            total_sell=total_price,
            status="pending",
            idempotency_key=idempotency,
        )
        db.add(res_order)
        await db.commit()
        await db.refresh(res_order)

        # Fulfill order
        success, msg, codes = await fulfill_reseller_purchase(
            product_name=p.name,
            product_id=p.id,
            user_id=current_user.telegram_id,
            quantity=qty,
            reseller_order_id=res_order.id,
            bot=None,
            idempotency_key=idempotency,
        )

        delivered = "\n".join(codes) if codes else "Order accepted. Your digital asset is ready."

        # Save to BoughtGoods for customer dashboard history
        bg = BoughtGoods(
            buyer_id=current_user.telegram_id,
            item_name=p.name,
            price=total_price,
            value=delivered,
            bought_datetime=datetime.now(timezone.utc),
        )
        db.add(bg)
        await db.commit()

        # Automatic Customer Email Delivery
        if target_email:
            npr_amount_str = f"NPR {int(total_price * 300):,}"
            asyncio.create_task(
                send_order_delivery_email(
                    customer_email=target_email,
                    product_name=p.name,
                    quantity=qty,
                    amount_str=npr_amount_str,
                    delivered_content=delivered,
                    order_id=str(res_order.id),
                )
            )

        # Alert KDS Payment Channel
        user_name = current_user.first_name or current_user.username or f"User #{current_user.telegram_id}"
        channel_msg = (
            f"🎉 <b>ORDER FULFILLED & DELIVERED!</b>\n\n"
            f"👤 <b>Customer:</b> {html.escape(user_name)}\n"
            f"📧 <b>Email:</b> <code>{html.escape(target_email or 'N/A')}</code>\n"
            f"🛍️ <b>Product:</b> {html.escape(p.name)} (x{qty})\n"
            f"💰 <b>Total Paid:</b> NPR {int(total_price * 300):,} (${float(total_price):.2f} USD)\n"
            f"⚡ <b>Delivery:</b> Sent automatically to customer email & dashboard"
        )
        asyncio.create_task(send_kds_channel_notification(channel_msg))

        return {
            "status": "success",
            "message": "Purchase successful! Digital keys have been delivered to your email.",
            "order_id": res_order.id,
            "product_name": p.name,
            "quantity": qty,
            "total_paid": float(total_price),
            "delivered_content": delivered,
            "codes": codes,
            "delivered_to_email": target_email or None,
        }

    # Case B: Local Product (e.g. local_1)
    raw_id = int(prod_id_str.replace("local_", ""))
    goods = (await db.execute(select(Goods).where(Goods.id == raw_id))).scalar_one_or_none()

    if not goods:
        raise HTTPException(status_code=404, detail="Product not found")

    success, msg, purchase_data = await buy_item_transaction(
        telegram_id=current_user.telegram_id,
        item_name=goods.name,
        promo_code=promo_code,
    )

    if not success:
        raise HTTPException(status_code=400, detail=f"Checkout failed: {msg}")

    delivered = purchase_data.get("value", "") if purchase_data else "Key delivered."
    paid_usd = float(purchase_data.get("price", goods.price)) if purchase_data else float(goods.price)

    # Automatic Customer Email Delivery
    if target_email:
        npr_amount_str = f"NPR {int(paid_usd * 300):,}"
        asyncio.create_task(
            send_order_delivery_email(
                customer_email=target_email,
                product_name=goods.name,
                quantity=qty,
                amount_str=npr_amount_str,
                delivered_content=delivered,
                order_id=str(purchase_data.get("unique_id", "")),
            )
        )

    # Alert KDS Payment Channel
    user_name = current_user.first_name or current_user.username or f"User #{current_user.telegram_id}"
    channel_msg = (
        f"🎉 <b>ORDER FULFILLED & DELIVERED!</b>\n\n"
        f"👤 <b>Customer:</b> {html.escape(user_name)}\n"
        f"📧 <b>Email:</b> <code>{html.escape(target_email or 'N/A')}</code>\n"
        f"🛍️ <b>Product:</b> {html.escape(goods.name)} (x{qty})\n"
        f"💰 <b>Total Paid:</b> NPR {int(paid_usd * 300):,} (${paid_usd:.2f} USD)\n"
        f"⚡ <b>Delivery:</b> Sent automatically to customer email & dashboard"
    )
    asyncio.create_task(send_kds_channel_notification(channel_msg))

    return {
        "status": "success",
        "message": "Purchase successful! Digital keys have been delivered to your email.",
        "product_name": goods.name,
        "quantity": qty,
        "total_paid": paid_usd,
        "delivered_content": delivered,
        "unique_id": purchase_data.get("unique_id") if purchase_data else None,
        "delivered_to_email": target_email or None,
    }


class CryptoDepositSubmitRequest(BaseModel):
    network: str  # BEP20, TRC20, BYBIT, BINANCE
    tx_hash: str
    amount_usd: float
    proof_image: Optional[str] = None


@router.get("/crypto-methods")
async def get_crypto_payment_methods(raw_request: Request):
    """
    Returns all configured worldwide / USDT payment methods identical to the Telegram Bot.
    Filtered out (empty list) for visitors originating from Nepal.
    """
    if await is_nepal_client(raw_request):
        return []

    import os
    bep20_wallet = os.getenv("BEP20_WALLET") or getattr(EnvKeys, "BEP20_WALLET", None) or "0x71C67E3684d00120150d1829eDCE18c0c804f5D7"
    trc20_wallet = os.getenv("TRC20_WALLET") or getattr(EnvKeys, "TRC20_WALLET", None) or "TYDzsYUEpvnYmQk4zGP9sWWcTEd3MiAtW6"
    bybit_uid = os.getenv("BYBIT_UID") or getattr(EnvKeys, "BYBIT_UID", None) or "549212357"
    binance_id = os.getenv("BINANCE_PAY_ID") or getattr(EnvKeys, "BINANCE_PAY_ID", None) or "175541349"
    bot_user = os.getenv("BOT_USERNAME") or getattr(EnvKeys, "BOT_USERNAME", None) or "kali_digital_store_bot"
    
    methods = [
        {
            "id": "cryptopay",
            "name": "CryptoPay (CryptoBot)",
            "icon": "💎",
            "badge": "Instant Auto-Credit",
            "description": "Pay instantly via Telegram CryptoBot with USDT, TON, BTC, ETH, SOL, TRX, LTC, BNB.",
            "type": "invoice",
            "enabled": True,
        },
        {
            "id": "bep20",
            "name": "BEP20 USDT (BSC)",
            "icon": "🔷",
            "badge": "Low Fee (~$0.05)",
            "description": "Direct deposit via Binance Smart Chain (BEP20). Auto-verified on-chain with BscScan.",
            "type": "onchain",
            "network": "BEP20",
            "wallet_address": bep20_wallet,
            "qr_url": f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={bep20_wallet}",
            "enabled": True,
        },
        {
            "id": "trc20",
            "name": "TRC20 USDT (TRON)",
            "icon": "🌐",
            "badge": "TRON Network",
            "description": "Direct deposit via TRON network (TRC20). Verified on-chain via TronGrid.",
            "type": "onchain",
            "network": "TRC20",
            "wallet_address": trc20_wallet,
            "qr_url": f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={trc20_wallet}",
            "enabled": True,
        },
        {
            "id": "bybit",
            "name": "Bybit Pay",
            "icon": "⚡",
            "badge": "0% Fee Internal Transfer",
            "description": "Transfer USDT internally to our Bybit UID with zero fees and instant confirmation.",
            "type": "uid_transfer",
            "account_id": str(bybit_uid),
            "enabled": True,
        },
        {
            "id": "binance",
            "name": "Binance Pay",
            "icon": "🪙",
            "badge": "Binance ID Transfer",
            "description": "Send payment directly via Binance Pay ID or Binance App QR code.",
            "type": "uid_transfer",
            "account_id": str(binance_id),
            "enabled": True,
        },
        {
            "id": "stars",
            "name": "Telegram Stars",
            "icon": "🌟",
            "badge": "In-App Telegram",
            "description": "Pay with official Telegram Stars directly in our bot.",
            "type": "stars",
            "bot_url": f"https://t.me/{bot_user}",
            "enabled": True,
        },
    ]
    return methods


@router.post("/deposit/onchain-submit")
async def submit_onchain_deposit(
    request: CryptoDepositSubmitRequest,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Process on-chain or internal crypto deposit submission (BEP20, TRC20, Bybit, Binance).
    Attempts on-chain verification if applicable, logs payment, and broadcasts alert to Telegram support.
    """
    if await is_nepal_client(raw_request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cryptocurrency and USDT payment services are restricted in Nepal due to local regulations."
        )

    tx_hash = request.tx_hash.strip()

    if not tx_hash:
        raise HTTPException(status_code=400, detail="Transaction hash / reference ID is required")
        
    net = request.network.upper()
    amount = Decimal(str(request.amount_usd))
    payment_uuid = f"{net.lower()}_{uuid.uuid4().hex[:12]}"
    
    # 1. Try on-chain auto-verification for BEP20
    verified = False
    if net == "BEP20" and EnvKeys.BEP20_WALLET:
        try:
            from packages.services.bscscan import verify_usdt_bep20_tx
            import time
            res = await verify_usdt_bep20_tx(
                tx_hash=tx_hash,
                wallet_address=EnvKeys.BEP20_WALLET,
                expected_amount=float(amount),
                since_timestamp_s=int(time.time()) - 3600,
            )
            if res:
                verified = True
        except Exception as e:
            logger.warning(f"BEP20 verification error: {e}")

    # 2. Record payment in database
    status = PaymentStatus.SUCCEEDED if verified else PaymentStatus.PENDING
    pmt = Payments(
        provider=f"crypto_{net.lower()}",
        external_id=f"{tx_hash}::{payment_uuid}",
        user_id=current_user.telegram_id,
        amount=amount,
        currency="USD",
        status=status,
    )
    db.add(pmt)
    if verified:
        current_user.balance += amount
    await db.commit()
    await db.refresh(pmt)

    # 3. Parse photo if attached
    photo_bytes = None
    if request.proof_image and "base64," in request.proof_image:
        try:
            import base64
            _, encoded = request.proof_image.split("base64,", 1)
            photo_bytes = base64.b64decode(encoded)
        except Exception:
            pass

    # 4. Notify Telegram Support & Alert Channels
    user_name = current_user.email or f"User #{current_user.telegram_id}"
    npr_equiv = int(float(amount) * 300)
    
    alert_msg = (
        f"💎 <b>NEW {net} CRYPTO DEPOSIT SUBMITTED!</b>\n\n"
        f"👤 <b>Customer:</b> {html.escape(user_name)} (ID: <code>{current_user.telegram_id}</code>)\n"
        f"📧 <b>Email:</b> <code>{html.escape(current_user.email or 'N/A')}</code>\n"
        f"💰 <b>Amount:</b> <b>${float(amount):.2f} USD</b> (NPR {npr_equiv:,})\n"
        f"🌐 <b>Network / Method:</b> {net}\n"
        f"📌 <b>TX Hash / Ref:</b> <code>{html.escape(tx_hash)}</code>\n"
        f"⚡ <b>Status:</b> {'✅ Auto-Verified On-Chain' if verified else '⏳ Pending Admin Verification'}\n"
        f"📷 <b>Receipt Attached:</b> {'Yes (Photo below)' if photo_bytes else 'No'}"
    )

    action_keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve & Credit", "callback_data": f"adm_appr_pmt_{pmt.id}"},
                {"text": "❌ Reject", "callback_data": f"adm_rej_pmt_{pmt.id}"}
            ],
            [
                {"text": "✉️ Reply to Customer", "callback_data": f"support_reply_{current_user.telegram_id}"}
            ]
        ]
    } if not verified else {
        "inline_keyboard": [
            [{"text": "✅ Auto-Verified On-Chain", "callback_data": "noop"}]
        ]
    }

    if photo_bytes:
        asyncio.create_task(send_kds_channel_photo(photo_bytes, alert_msg, reply_markup=action_keyboard))
    else:
        asyncio.create_task(send_kds_channel_notification(alert_msg, reply_markup=action_keyboard))

    return {
        "status": "success",
        "verified": verified,
        "amount_usd": float(amount),
        "message": "Payment verified and balance credited instantly!" if verified else "Deposit reference submitted! Balance will be credited upon verification.",
    }


@router.post("/deposit/cryptopay")
async def generate_cryptopay_invoice(
    amount: float,
    raw_request: Request,
    asset: str = "USDT",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a CryptoPay invoice. Returns invoice_url + invoice_id for polling.
    Accepted assets: TON, USDT, BTC, ETH, SOL, TRX, LTC, BNB
    """
    if await is_nepal_client(raw_request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cryptocurrency and USDT payment services are restricted in Nepal due to local regulations."
        )

    if not EnvKeys.CRYPTO_PAY_TOKEN:
        raise HTTPException(status_code=503, detail="CryptoPay is not configured on this server.")
    try:
        from packages.services.payment import CryptoPayAPI
        api_client = CryptoPayAPI(EnvKeys.CRYPTO_PAY_TOKEN)
        invoice = await api_client.create_invoice(
            amount=amount,
            asset=asset,
            description=f"KDS Store Balance Top-Up: ${amount:.2f} USD",
            payload=str(current_user.telegram_id),
            accepted_assets="TON,USDT,BTC,ETH,SOL,TRX,LTC,BNB",
        )
        invoice_id = invoice.get("invoice_id")
        pay_url = invoice.get("mini_app_invoice_url") or invoice.get("pay_url") or invoice.get("bot_invoice_url")

        # Record pending payment
        if invoice_id:
            pmt = Payments(
                provider="cryptopay",
                external_id=str(invoice_id),
                user_id=current_user.telegram_id,
                amount=Decimal(str(amount)),
                currency="USDT",
                status=PaymentStatus.PENDING,
            )
            db.add(pmt)
            await db.commit()
            await db.refresh(pmt)

        return {"invoice_url": pay_url, "invoice_id": invoice_id}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to generate invoice: {exc}")


@router.get("/deposit/cryptopay-check")
async def check_cryptopay_invoice(
    invoice_id: str,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Poll CryptoPay invoice status. If paid, credit user balance and return paid=true.
    Safe to call repeatedly — uses existing payment deduplication.
    """
    if await is_nepal_client(raw_request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cryptocurrency and USDT payment services are restricted in Nepal due to local regulations."
        )

    if not EnvKeys.CRYPTO_PAY_TOKEN:
        return {"paid": False, "status": "not_configured"}
    try:
        from packages.services.payment import CryptoPayAPI
        from packages.database.methods.transactions import process_payment_with_referral
        api_client = CryptoPayAPI(EnvKeys.CRYPTO_PAY_TOKEN)
        info = await api_client.get_invoice(invoice_id)
        status = info.get("status")
        if status == "paid":
            paid_amount = Decimal(str(info.get("amount", "0")))
            success, error_msg = await process_payment_with_referral(
                user_id=current_user.telegram_id,
                amount=paid_amount,
                provider="cryptopay",
                external_id=str(invoice_id),
                referral_percent=EnvKeys.REFERRAL_PERCENT,
            )
            if success or error_msg == "already_processed":
                # Refresh user's balance for response
                await db.refresh(current_user)
                # Notify admin channel
                user_name = current_user.email or f"User #{current_user.telegram_id}"
                asyncio.create_task(send_kds_channel_notification(
                    f"💎 <b>CryptoPay Top-Up!</b>\n\n"
                    f"👤 <b>Customer:</b> {html.escape(user_name)}\n"
                    f"💰 <b>Amount:</b> <b>${float(paid_amount):.2f} USDT</b>\n"
                    f"📌 <b>Invoice:</b> <code>{invoice_id}</code>\n"
                    f"⚡ <b>Status:</b> ✅ Auto-verified & balance credited"
                ))
                return {"paid": True, "amount": float(paid_amount), "balance": float(current_user.balance)}
        return {"paid": False, "status": status or "active"}
    except Exception as exc:
        logger.warning(f"CryptoPay check failed for invoice {invoice_id}: {exc}")
        return {"paid": False, "status": "error", "detail": str(exc)}


@router.post("/deposit/bybit-init")
async def init_bybit_payment(
    request: BybitInitRequest,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Initialize a Bybit UID transfer deposit.
    Returns the Bybit UID, unique amount (base + random cents), and payment UUID for tracking.
    Mirrors the Telegram bot's pay_bybit flow exactly.
    """
    if await is_nepal_client(raw_request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cryptocurrency and USDT payment services are restricted in Nepal due to local regulations."
        )

    import random, time as _time
    bybit_uid = (EnvKeys.BYBIT_UID or "").strip()
    if not bybit_uid:
        raise HTTPException(status_code=503, detail="Bybit Pay is not configured. Please contact support.")

    base_amount = float(request.amount_usd)
    # Generate unique amount: add random 1–20 cents for auto-identification
    unique_cents = random.randint(1, 20) / 100
    unique_amount = round(base_amount + unique_cents, 2)
    credited_amount = base_amount  # We credit the base amount (not the unique offset)
    created_at_ms = int(_time.time() * 1000)
    payment_uuid = str(uuid.uuid4())[:16]

    # Save pending payment record
    pmt = Payments(
        provider="bybit_uid",
        external_id=payment_uuid,
        user_id=current_user.telegram_id,
        amount=Decimal(str(unique_amount)),
        currency="USDT",
        status=PaymentStatus.PENDING,
    )
    db.add(pmt)
    await db.commit()
    await db.refresh(pmt)

    return {
        "bybit_uid": bybit_uid,
        "unique_amount": unique_amount,
        "credited_amount": credited_amount,
        "created_at_ms": created_at_ms,
        "payment_uuid": payment_uuid,
        "payment_id": pmt.id,
    }


@router.post("/deposit/bybit-verify")
async def verify_bybit_payment(
    request: BybitVerifyRequest,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verify a Bybit UID transfer. Tries direct TX ID lookup first, then amount-matching.
    Credits balance if verified; falls back to pending+manual admin alert if not.
    """
    if await is_nepal_client(raw_request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cryptocurrency and USDT payment services are restricted in Nepal due to local regulations."
        )

    import time as _time
    from packages.database.methods.transactions import process_payment_with_referral

    # Parse screenshot if any
    photo_bytes = None
    if request.proof_image and "base64," in request.proof_image:
        try:
            import base64
            _, encoded = request.proof_image.split("base64,", 1)
            photo_bytes = base64.b64decode(encoded)
        except Exception:
            pass

    verified = False
    verified_dep = None
    bybit_uid = (EnvKeys.BYBIT_UID or "").strip()

    if EnvKeys.BYBIT_API_KEY and EnvKeys.BYBIT_API_SECRET:
        try:
            from packages.services.bybit import BybitPayAPI, BybitPayError
            api = BybitPayAPI()
            # Try by Transfer ID first (most reliable)
            if request.tx_id and request.tx_id.strip():
                verified_dep = await api.find_internal_deposit_by_txid(
                    tx_id=request.tx_id.strip(),
                    since_timestamp_ms=request.created_at_ms - 300_000,  # 5 min grace
                )
            # Fallback: match by unique amount
            if not verified_dep:
                verified_dep = await api.find_matching_internal_deposit(
                    expected_amount=request.unique_amount,
                    since_timestamp_ms=request.created_at_ms - 300_000,
                )
            if verified_dep:
                verified = True
        except Exception as e:
            logger.warning(f"Bybit auto-verify error: {e}")

    if verified:
        credit = Decimal(str(request.credited_amount))
        success, error_msg = await process_payment_with_referral(
            user_id=current_user.telegram_id,
            amount=credit,
            provider="bybit_uid",
            external_id=request.payment_uuid,
            referral_percent=EnvKeys.REFERRAL_PERCENT,
        )
        if success or error_msg == "already_processed":
            await db.refresh(current_user)
            user_name = current_user.email or f"User #{current_user.telegram_id}"
            asyncio.create_task(send_kds_channel_notification(
                f"⚡ <b>Bybit Pay Verified!</b>\n\n"
                f"👤 <b>Customer:</b> {html.escape(user_name)}\n"
                f"💰 <b>Amount Credited:</b> <b>${float(credit):.2f} USDT</b>\n"
                f"📌 <b>TX/Ref:</b> <code>{request.tx_id or request.payment_uuid}</code>\n"
                f"⚡ <b>Status:</b> ✅ Auto-verified via Bybit API"
            ))
            return {"verified": True, "message": f"${float(credit):.2f} credited to your balance!", "balance": float(current_user.balance)}

    # Fallback: keep pending and notify admin
    user_name = current_user.email or f"User #{current_user.telegram_id}"
    credit = Decimal(str(request.credited_amount))
    alert_msg = (
        f"⚡ <b>BYBIT PAY — MANUAL REVIEW NEEDED</b>\n\n"
        f"👤 <b>Customer:</b> {html.escape(user_name)} (ID: <code>{current_user.telegram_id}</code>)\n"
        f"📧 <b>Email:</b> <code>{html.escape(current_user.email or 'N/A')}</code>\n"
        f"💰 <b>Amount:</b> <b>${request.unique_amount:.2f} USDT</b> (credit: ${float(credit):.2f})\n"
        f"🔑 <b>Bybit UID:</b> <code>{bybit_uid}</code>\n"
        f"📌 <b>Transfer ID:</b> <code>{html.escape(request.tx_id or 'Not provided')}</code>\n"
        f"🔗 <b>UUID:</b> <code>{request.payment_uuid}</code>\n"
        f"⚡ <b>Auto-verify:</b> Failed — please check Bybit internal transfers and approve."
    )
    # Find the Payments record to attach admin approve/reject buttons
    pmt = (await db.execute(select(Payments).where(Payments.external_id == request.payment_uuid))).scalar_one_or_none()
    pmt_id = pmt.id if pmt else 0
    action_keyboard = {
        "inline_keyboard": [
            [
                {"text": f"✅ Approve ${float(credit):.2f}", "callback_data": f"adm_appr_pmt_{pmt_id}"},
                {"text": "❌ Reject", "callback_data": f"adm_rej_pmt_{pmt_id}"}
            ],
            [{"text": "✉️ Reply to Customer", "callback_data": f"support_reply_{current_user.telegram_id}"}]
        ]
    }
    if photo_bytes:
        asyncio.create_task(send_kds_channel_photo(photo_bytes, alert_msg, reply_markup=action_keyboard))
    else:
        asyncio.create_task(send_kds_channel_notification(alert_msg, reply_markup=action_keyboard))

    return {"verified": False, "message": "Transfer submitted! Your balance will be credited after admin verification (usually within 15 minutes)."}


@router.post("/deposit/binance-init")
async def init_binance_payment(
    request: BinanceInitRequest,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Initialize a Binance Pay deposit. Generates unique amount + remark code for auto-detection.
    Mirrors the Telegram bot's pay_binance flow exactly.
    """
    if await is_nepal_client(raw_request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cryptocurrency and USDT payment services are restricted in Nepal due to local regulations."
        )

    import random, string as _string, time as _time
    binance_pay_id = (EnvKeys.BINANCE_PAY_ID or "").strip()
    if not binance_pay_id:
        raise HTTPException(status_code=503, detail="Binance Pay is not configured. Please contact support.")

    base_amount = float(request.amount_usd)
    unique_cents = random.randint(1, 20) / 100
    unique_amount = round(base_amount + unique_cents, 2)
    credited_amount = base_amount
    created_at_ms = int(_time.time() * 1000)
    payment_uuid = str(uuid.uuid4())[:16]
    remark_code = "BUY-" + "".join(random.choices(_string.ascii_uppercase + _string.digits, k=8))

    # Save pending payment record
    pmt = Payments(
        provider="binance_uid",
        external_id=payment_uuid,
        user_id=current_user.telegram_id,
        amount=Decimal(str(unique_amount)),
        currency="USDT",
        status=PaymentStatus.PENDING,
    )
    db.add(pmt)
    await db.commit()

    return {
        "binance_pay_id": binance_pay_id,
        "unique_amount": unique_amount,
        "credited_amount": credited_amount,
        "remark_code": remark_code,
        "created_at_ms": created_at_ms,
        "payment_uuid": payment_uuid,
        "payment_id": pmt.id,
    }


@router.post("/deposit/binance-verify")
async def verify_binance_payment(
    request: BinanceVerifyRequest,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Try to auto-verify a Binance Pay transfer by scanning recent transactions.
    Credits balance if found; falls back to pending+manual admin alert.
    """
    if await is_nepal_client(raw_request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cryptocurrency and USDT payment services are restricted in Nepal due to local regulations."
        )

    from packages.database.methods.transactions import process_payment_with_referral
    from decimal import Decimal as Dec

    # Parse screenshot if any
    photo_bytes = None
    if request.proof_image and "base64," in request.proof_image:
        try:
            import base64
            _, encoded = request.proof_image.split("base64,", 1)
            photo_bytes = base64.b64decode(encoded)
        except Exception:
            pass

    verified = False
    credit = Decimal(str(request.credited_amount))

    if EnvKeys.BINANCE_API_KEY and EnvKeys.BINANCE_API_SECRET:
        try:
            from packages.services.binance_pay import get_pay_transactions
            import time as _time
            end_ms = int(_time.time() * 1000)
            txns = await get_pay_transactions(start_ms=request.created_at_ms - 300_000, end_ms=end_ms)
            target = Dec(str(request.unique_amount)).quantize(Dec("0.01"))
            remark_upper = request.remark_code.strip().upper()
            for txn in txns:
                if txn.get("transStatus") != "SUCCESS":
                    continue
                try:
                    amt = Dec(str(txn.get("amount", 0))).quantize(Dec("0.01"))
                except Exception:
                    continue
                if amt != target:
                    continue
                if remark_upper and remark_upper not in str(txn).upper():
                    continue
                verified = True
                break
        except Exception as e:
            logger.warning(f"Binance auto-verify error: {e}")

    if verified:
        success, error_msg = await process_payment_with_referral(
            user_id=current_user.telegram_id,
            amount=credit,
            provider="binance_uid",
            external_id=request.payment_uuid,
            referral_percent=EnvKeys.REFERRAL_PERCENT,
        )
        if success or error_msg == "already_processed":
            await db.refresh(current_user)
            user_name = current_user.email or f"User #{current_user.telegram_id}"
            asyncio.create_task(send_kds_channel_notification(
                f"🪙 <b>Binance Pay Verified!</b>\n\n"
                f"👤 <b>Customer:</b> {html.escape(user_name)}\n"
                f"💰 <b>Amount Credited:</b> <b>${float(credit):.2f} USDT</b>\n"
                f"🏷️ <b>Remark Code:</b> <code>{html.escape(request.remark_code)}</code>\n"
                f"⚡ <b>Status:</b> ✅ Auto-verified via Binance Pay API"
            ))
            return {"verified": True, "message": f"${float(credit):.2f} credited to your balance!", "balance": float(current_user.balance)}

    # Fallback: notify admin
    binance_pay_id = (EnvKeys.BINANCE_PAY_ID or "").strip()
    user_name = current_user.email or f"User #{current_user.telegram_id}"
    alert_msg = (
        f"🪙 <b>BINANCE PAY — MANUAL REVIEW NEEDED</b>\n\n"
        f"👤 <b>Customer:</b> {html.escape(user_name)} (ID: <code>{current_user.telegram_id}</code>)\n"
        f"📧 <b>Email:</b> <code>{html.escape(current_user.email or 'N/A')}</code>\n"
        f"💰 <b>Unique Amount Sent:</b> <b>${request.unique_amount:.2f} USDT</b> (credit: ${float(credit):.2f})\n"
        f"🏷️ <b>Remark Code:</b> <code>{html.escape(request.remark_code)}</code>\n"
        f"🔑 <b>Binance Pay ID:</b> <code>{binance_pay_id}</code>\n"
        f"⚡ <b>Auto-verify:</b> Failed — check Binance Pay transactions and approve."
    )
    pmt = (await db.execute(select(Payments).where(Payments.external_id == request.payment_uuid))).scalar_one_or_none()
    pmt_id = pmt.id if pmt else 0
    action_keyboard = {
        "inline_keyboard": [
            [
                {"text": f"✅ Approve ${float(credit):.2f}", "callback_data": f"adm_appr_pmt_{pmt_id}"},
                {"text": "❌ Reject", "callback_data": f"adm_rej_pmt_{pmt_id}"}
            ],
            [{"text": "✉️ Reply to Customer", "callback_data": f"support_reply_{current_user.telegram_id}"}]
        ]
    }
    if photo_bytes:
        asyncio.create_task(send_kds_channel_photo(photo_bytes, alert_msg, reply_markup=action_keyboard))
    else:
        asyncio.create_task(send_kds_channel_notification(alert_msg, reply_markup=action_keyboard))

    return {"verified": False, "message": "Transfer submitted! Balance will be credited after admin verification (usually within 15 minutes)."}



# ─── DIRECT PURCHASE & DEPOSIT ROUTE ALIASES ────────────────────────────────

class DirectPurchaseRequest(BaseModel):
    product_id: str
    quantity: int = 1
    promocode: Optional[str] = None
    customer_email: Optional[str] = None


class CryptoPayInitRequest(BaseModel):
    amount_usd: float


class CryptoPayCheckRequest(BaseModel):
    invoice_id: str


class CryptoProofRequest(BaseModel):
    amount: float
    currency: str = "USDT"
    chain: str  # BEP20, TRC20, BYBIT, BINANCE
    tx_hash: str
    proof_image: Optional[str] = None


@router.post("/purchase")
async def purchase_direct(
    request: DirectPurchaseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Direct purchase alias that wraps checkout."""
    checkout_req = CheckoutRequest(
        items=[CartItem(product_id=request.product_id, quantity=request.quantity)],
        promo_code=request.promocode,
        customer_email=request.customer_email,
        payment_method="balance"
    )
    return await checkout(request=checkout_req, db=db, current_user=current_user)


@router.post("/deposit/cryptopay-init")
async def cryptopay_init_deposit(
    request: CryptoPayInitRequest,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate CryptoPay / CryptoBot invoice for automatic verification."""
    if await is_nepal_client(raw_request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cryptocurrency and USDT payment services are restricted in Nepal due to local regulations."
        )

    amount = max(0.5, float(request.amount_usd))
    try:
        from packages.services.payment import CryptoPayAPI
        client = CryptoPayAPI()
        if client.token:
            inv = await client.create_invoice(
                amount=amount,
                expires_in=1800,
                currency="USD",
                accepted_assets="USDT,TON,BTC,ETH,SOL,BNB,TRX",
                description=f"Kali Store Topup - ${amount:.2f} USD",
                payload=f"topup_{current_user.telegram_id}_{uuid.uuid4().hex[:6]}"
            )
            if inv and (inv.get("bot_invoice_url") or inv.get("pay_url") or inv.get("mini_app_invoice_url")):
                pay_url = inv.get("bot_invoice_url") or inv.get("mini_app_invoice_url") or inv.get("pay_url")
                return {
                    "invoice_id": str(inv.get("invoice_id")),
                    "bot_pay_url": pay_url,
                    "amount": amount,
                    "currency": "USD"
                }
    except Exception as e:
        logger.warning(f"CryptoPay invoice creation warning: {e}")

    # Fallback to direct bot topup or Telegram deep link
    bot_name = getattr(EnvKeys, "BOT_USERNAME", None) or "kali_digital_store_bot"
    return {
        "invoice_id": f"manual_cp_{uuid.uuid4().hex[:8]}",
        "bot_pay_url": f"https://t.me/{bot_name}?start=topup_{int(amount)}",
        "amount": amount,
        "currency": "USD"
    }


@router.post("/deposit/cryptopay-check")
async def cryptopay_check_deposit(
    request: CryptoPayCheckRequest,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check status of CryptoPay invoice."""
    if await is_nepal_client(raw_request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cryptocurrency and USDT payment services are restricted in Nepal due to local regulations."
        )

    try:
        from packages.services.payment import CryptoPayAPI
        client = CryptoPayAPI()
        if client.token and not request.invoice_id.startswith("manual_"):
            inv = await client.get_invoice(request.invoice_id)
            if inv and inv.get("status") == "paid":
                ext_id = f"cp_{request.invoice_id}"
                existing_pmt = (await db.execute(select(Payments).where(Payments.external_id == ext_id))).scalar_one_or_none()
                if not existing_pmt:
                    amount_paid = Decimal(str(inv.get("amount") or 0.0))
                    current_user.balance += amount_paid
                    pmt = Payments(
                        provider="cryptopay",
                        external_id=ext_id,
                        user_id=current_user.telegram_id,
                        amount=amount_paid,
                        currency="USD",
                        status=PaymentStatus.SUCCEEDED
                    )
                    db.add(pmt)
                    await db.commit()
                return {"status": "paid", "message": "Invoice paid and balance credited!"}
    except Exception as e:
        logger.error(f"Error checking CryptoPay invoice: {e}")
    
    return {"status": "pending", "message": "Invoice awaiting payment."}


@router.post("/deposit/crypto-proof")
async def submit_crypto_proof(
    request: CryptoProofRequest,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit proof for BEP20, TRC20, Bybit, or Binance deposit."""
    if await is_nepal_client(raw_request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cryptocurrency and USDT payment services are restricted in Nepal due to local regulations."
        )

    onchain_req = CryptoDepositSubmitRequest(
        network=request.chain,
        tx_hash=request.tx_hash,
        amount_usd=request.amount,
        proof_image=request.proof_image
    )
    return await submit_onchain_deposit(request=onchain_req, raw_request=raw_request, db=db, current_user=current_user)


