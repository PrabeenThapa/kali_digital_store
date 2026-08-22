"""
Reseller order fulfillment service.

After a user pays for a reseller product, this service:
  1. Looks up the ResellerProduct by name
  2. Places the order on the external API
  3. For instant (`account` / `stock`) type → sends credentials to user immediately
  4. For `preorder` / `team_invite` → stores pending order + notifies admin

Fulfillment is triggered from the buy_item_callback_handler AFTER balance deduction.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from aiogram import Bot
from sqlalchemy import select

from packages.config.config import EnvKeys
from packages.database.engine import Database
from packages.database.models.main import ResellerSource, ResellerProduct, ResellerOrder

from .client import ForkPixelClient, CGPTClient, SafwanTigerClient, CanbosoClient, GGSomaClient

_log = logging.getLogger(__name__)

INSTANT_TYPES = {"account", "stock"}
MANUAL_TYPES  = {"preorder", "team_invite", "preorder"}


async def get_reseller_product_by_name(name: str) -> ResellerProduct | None:
    """Look up an enabled reseller product by display name."""
    async with Database().session() as s:
        return (await s.execute(
            select(ResellerProduct).where(
                ResellerProduct.name == name,
                ResellerProduct.is_enabled == True,  # noqa: E712
            )
        )).scalars().first()


async def get_reseller_product_by_id(product_id: int) -> ResellerProduct | None:
    """Look up an enabled reseller product by its stable local identifier."""
    async with Database().session() as s:
        return (await s.execute(
            select(ResellerProduct).where(
                ResellerProduct.id == product_id,
                ResellerProduct.is_enabled == True,  # noqa: E712
            )
        )).scalars().first()


async def _get_source(source_id: int) -> ResellerSource | None:
    async with Database().session() as s:
        return (await s.execute(
            select(ResellerSource).where(ResellerSource.id == source_id)
        )).scalars().first()


async def _place_forkpixel_order(source: ResellerSource, product: ResellerProduct, qty: int, idempotency: str) -> dict:
    """Place order on ForkPixel. Returns API response dict."""
    client = ForkPixelClient(
        api_key=source.api_key,
        base_url=source.base_url,
        currency=EnvKeys.FORKPIXEL_CURRENCY,
    )
    return await client.place_order(
        code=product.external_code or None,
        product_id=int(product.external_id) if not product.external_code else None,
        qty=qty,
        shop_order_id=idempotency,
    )


async def _place_cgpt_order(source: ResellerSource, product: ResellerProduct, qty: int, idempotency: str) -> dict:
    """Place order on CGPT. Returns API response dict."""
    client = CGPTClient(api_key=source.api_key, base_url=source.base_url)
    return await client.place_order(
        product_id=int(product.external_id),
        quantity=qty,
        idempotency_key=idempotency,
    )


async def _place_safwan_order(source: ResellerSource, product: ResellerProduct, qty: int, idempotency: str) -> dict:
    """Place order on SafwanTiger. Returns API response dict."""
    client = SafwanTigerClient(api_key=source.api_key, base_url=source.base_url)
    return await client.place_order(
        product_id=int(product.external_id),
        quantity=qty,
        request_id=idempotency,
    )


async def _place_canboso_order(source: ResellerSource, product: ResellerProduct, qty: int, idempotency: str) -> dict:
    """Place order on Canboso. The Buyer API has no idempotency-key param —
    duplicate submissions are the caller's responsibility to avoid."""
    client = CanbosoClient(api_key=source.api_key, base_url=source.base_url)
    return await client.place_order(
        product_id=product.external_id,
        quantity=qty,
    )


async def fulfill_reseller_purchase(
    *,
    product_name: str,
    product_id: int | None = None,
    user_id: int,
    quantity: int,
    reseller_order_id: int,
    bot: Bot,
    idempotency_key: str,
) -> tuple[bool, str, list[str]]:
    """
    Place an order on the reseller API and deliver credentials.

    Returns:
        (success, status_message_for_admin_log, list_of_delivered_codes)

    For instant products: returned codes are sent to user immediately by caller.
    For preorder / team_invite: returns empty list; admin is notified.
    """
    product = (
        await get_reseller_product_by_id(product_id)
        if product_id is not None
        else await get_reseller_product_by_name(product_name)
    )
    if not product:
        _log.warning("fulfill_reseller_purchase: product '%s' not found in reseller_products", product_name)
        return False, "product_not_found", []

    source = await _get_source(product.source_id)
    if not source or not source.is_active:
        return False, "source_inactive", []

    # Place order on external API
    try:
        if source.name == "forkpixel":
            api_resp = await _place_forkpixel_order(source, product, quantity, idempotency_key)
        elif source.name == "cgpt":
            api_resp = await _place_cgpt_order(source, product, quantity, idempotency_key)
        elif source.name == "safwan":
            api_resp = await _place_safwan_order(source, product, quantity, idempotency_key)
        elif source.name == "canboso":
            api_resp = await _place_canboso_order(source, product, quantity, idempotency_key)
        elif source.name == "ggsoma":
            api_resp = await _place_ggsoma_order(source, product, quantity, idempotency_key)
        else:
            raise RuntimeError(f"Unknown source: {source.name}")
    except Exception as exc:
        _log.error("Reseller order failed for user %s, product '%s': %s", user_id, product_name, exc)
        # Mark order as failed
        async with Database().session() as s:
            rec = (await s.execute(select(ResellerOrder).where(ResellerOrder.id == reseller_order_id))).scalars().first()
            if rec:
                rec.status = "failed"
                rec.error_message = str(exc)[:1000]
                await s.commit()
        return False, f"api_error: {exc}", []

    # ── Parse response ───────────────────────────────────────────────

    codes: list[str] = []
    external_order_id = ""

    if source.name == "forkpixel":
        order_data = api_resp.get("order", {})
        external_order_id = order_data.get("orderCode", "")
        raw_accounts = order_data.get("accounts", [])
        codes = [str(a) for a in raw_accounts if a]

    elif source.name == "cgpt":
        external_order_id = str(api_resp.get("order_id", ""))
        codes = [str(c) for c in api_resp.get("delivered_codes", [])]

    elif source.name == "safwan":
        external_order_id, codes = _parse_safwan_response(api_resp)

    elif source.name == "canboso":
        external_order_id, codes = _parse_canboso_response(api_resp)

    elif source.name == "ggsoma":
        external_order_id, codes = _parse_ggsoma_response(api_resp)

    is_instant = product.product_type in INSTANT_TYPES and bool(codes)

    # Update order record
    async with Database().session() as s:
        rec = (await s.execute(select(ResellerOrder).where(ResellerOrder.id == reseller_order_id))).scalars().first()
        if rec:
            rec.external_order_id = external_order_id
            rec.delivered_codes = json.dumps(codes)
            rec.status = "delivered" if is_instant else "placed"
            if is_instant:
                rec.fulfilled_at = datetime.now(timezone.utc)
            await s.commit()

    if is_instant:
        _log.info("Reseller order fulfilled instantly for user %s: %d codes.", user_id, len(codes))
        return True, "delivered", codes
    else:
        # Notify admin via NOTIFY_BOT if configured
        await _notify_admin_pending(bot, user_id, product_name, external_order_id, quantity, source.name)
        _log.info("Reseller preorder placed for user %s, ext_id=%s.", user_id, external_order_id)
        return True, "pending_preorder", []


def _parse_safwan_response(api_resp: dict) -> tuple[str, list[str]]:
    """
    Extract (order_id, delivered_codes) from a SafwanTiger order response.

    The API docs only state "returns delivered items in JSON" without naming
    the field, so we defensively probe the field names shops commonly use.
    Whatever we find gets flattened into a list of strings for delivery.
    """
    # Order identifier — try the usual keys, including a nested "order" object
    external_order_id = ""
    for key in ("order_id", "id", "request_id", "orderCode"):
        if api_resp.get(key):
            external_order_id = str(api_resp[key])
            break
    if not external_order_id and isinstance(api_resp.get("order"), dict):
        order_obj = api_resp["order"]
        for key in ("order_id", "id", "orderCode"):
            if order_obj.get(key):
                external_order_id = str(order_obj[key])
                break

    # Delivered goods — probe common container keys, in priority order
    raw = None
    for key in ("items", "delivered", "delivered_items", "codes", "delivered_codes",
                "accounts", "data", "result", "deliverables"):
        if api_resp.get(key):
            raw = api_resp[key]
            break

    # Some APIs nest the goods under "order"
    if raw is None and isinstance(api_resp.get("order"), dict):
        order_obj = api_resp["order"]
        for key in ("items", "delivered", "codes", "accounts"):
            if order_obj.get(key):
                raw = order_obj[key]
                break

    codes: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                # Pull the meaningful field out of a dict item
                val = (item.get("content") or item.get("code") or item.get("value")
                       or item.get("data") or item.get("text") or json.dumps(item, ensure_ascii=False))
                codes.append(str(val))
            elif item:
                codes.append(str(item))
    elif isinstance(raw, str) and raw.strip():
        codes.append(raw.strip())
    elif isinstance(raw, dict):
        val = raw.get("content") or raw.get("code") or raw.get("value") or json.dumps(raw, ensure_ascii=False)
        codes.append(str(val))

    return external_order_id, codes


def _parse_canboso_response(api_resp: dict) -> tuple[str, list[str]]:
    """
    Extract (order_code, delivered_codes) from a Canboso PurchaseResponse.
    Schema: {orderCode, deliveredAccounts: [{user, password, verifyEmail}]}.
    """
    external_order_id = str(api_resp.get("orderCode") or "")

    codes: list[str] = []
    for acc in api_resp.get("deliveredAccounts") or []:
        if not isinstance(acc, dict):
            if acc:
                codes.append(str(acc))
            continue
        user = acc.get("user", "")
        password = acc.get("password", "")
        verify_email = acc.get("verifyEmail")
        line = f"{user}:{password}"
        if verify_email:
            line += f" (recovery: {verify_email})"
        codes.append(line)

    return external_order_id, codes


async def _place_ggsoma_order(source: ResellerSource, product: ResellerProduct, qty: int, idempotency: str) -> dict:
    """Place order on GGSOMA."""
    client = GGSomaClient(api_key=source.api_key, base_url=source.base_url)
    return await client.place_order(
        product_id=product.external_id,
        quantity=qty,
        external_order_id=idempotency,
    )


def _parse_ggsoma_response(api_resp: dict) -> tuple[str, list[str]]:
    """
    Extract (orderCode, delivered_codes) from a GGSOMA Partner order response.
    """
    external_order_id = str(api_resp.get("orderCode") or api_resp.get("id") or "")
    delivery = api_resp.get("delivery") or {}
    codes: list[str] = []

    if isinstance(delivery, dict):
        if delivery.get("link"):
            codes.append(str(delivery["link"]))
        if delivery.get("code"):
            codes.append(str(delivery["code"]))
        if delivery.get("accounts"):
            accs = delivery["accounts"]
            if isinstance(accs, list):
                for a in accs:
                    if isinstance(a, dict):
                        user = a.get("user") or a.get("email") or ""
                        pwd = a.get("password") or a.get("pass") or ""
                        line = f"{user}:{pwd}" if pwd else str(user)
                        if a.get("instructions"):
                            line += f" (Note: {a['instructions']})"
                        codes.append(line)
                    else:
                        codes.append(str(a))
    elif isinstance(delivery, str) and delivery.strip():
        codes.append(delivery.strip())

    if not codes and api_resp.get("delivered_codes"):
        codes = [str(c) for c in api_resp["delivered_codes"]]

    return external_order_id, codes


async def _notify_admin_pending(
    bot: Bot,
    user_id: int,
    product_name: str,
    external_order_id: str,
    quantity: int,
    source_name: str,
) -> None:
    """Notify the owner (and NOTIFY_BOT if set) about a pending preorder."""
    text = (
        f"📦 <b>New Preorder</b>\n\n"
        f"🔗 Source: <code>{source_name}</code>\n"
        f"📋 Product: <b>{product_name}</b>\n"
        f"🔢 Qty: {quantity}\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"🆔 External Order: <code>{external_order_id}</code>\n\n"
        f"<i>Deliver credentials when available.</i>"
    )
    try:
        await bot.send_message(EnvKeys.OWNER_ID, text, parse_mode="HTML")
    except Exception as exc:
        _log.warning("Could not notify owner about preorder: %s", exc)

    if EnvKeys.NOTIFY_BOT_TOKEN:
        try:
            from aiogram import Bot as _Bot
            nb = _Bot(token=EnvKeys.NOTIFY_BOT_TOKEN)
            await nb.send_message(EnvKeys.OWNER_ID, text, parse_mode="HTML")
            await nb.session.close()
        except Exception as exc:
            _log.warning("Could not notify via NOTIFY_BOT: %s", exc)


async def deliver_preorder_codes(
    *,
    reseller_order_id: int,
    codes: list[str],
    bot: Bot,
) -> bool:
    """
    Admin manually delivers codes for a preorder.
    Sends them to the user and marks the order delivered.
    """
    async with Database().session() as s:
        rec = (await s.execute(
            select(ResellerOrder).where(ResellerOrder.id == reseller_order_id)
        )).scalars().first()
        if not rec:
            return False

        rec.delivered_codes = json.dumps(codes)
        rec.status = "delivered"
        rec.fulfilled_at = datetime.now(timezone.utc)
        user_id = rec.user_id
        await s.commit()

    # Send codes to user
    if user_id:
        codes_text = "\n".join(f"<code>{c}</code>" for c in codes)
        try:
            await bot.send_message(
                user_id,
                f"✅ <b>Your order has been fulfilled!</b>\n\n"
                f"📦 Here are your credentials:\n\n{codes_text}",
                parse_mode="HTML",
            )
        except Exception as exc:
            _log.warning("Could not deliver codes to user %s: %s", user_id, exc)

    return True
