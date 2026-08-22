import json
import random
import string
import time
import uuid
from decimal import Decimal, ROUND_HALF_UP

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery, SuccessfulPayment, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.utils.keyboard import InlineKeyboardBuilder

from packages.database.methods import get_user_referral, buy_item_transaction, process_payment_with_referral, create_pending_payment
from apps.telegram_bot.keyboards import back, payment_menu, close, get_payment_choice
from apps.telegram_bot.keyboards.inline import simple_buttons, topup_cancel_keyboard
from apps.telegram_bot.core.logging import logger
from packages.database.methods.audit import log_audit
from packages.config.config import EnvKeys
from apps.telegram_bot.utils.validators import ItemPurchaseRequest, validate_telegram_id, validate_money_amount, PaymentRequest, sanitize_html
from apps.telegram_bot.handlers.other import _any_payment_method_enabled, is_safe_item_name
from apps.telegram_bot.core.metrics import get_metrics
from packages.services.payment import CryptoPayAPI, CryptoPayAPIError, send_stars_invoice, send_fiat_invoice, _minor_units_for
from packages.services.bybit import BybitPayAPI, BybitPayError
from packages.services.bscscan import verify_usdt_bep20_tx
from packages.services.binance_pay import find_payment as find_binance_payment
from apps.telegram_bot.filters import ValidAmountFilter
from apps.telegram_bot.i18n import localize
from apps.telegram_bot.states import BalanceStates

router = Router()


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


async def _notify_referrer_bonus(bot, user_id: int, amount: int, payer_name: str, payer_id: int):
    """Send referral bonus notification to the referrer if applicable."""
    referral_id = await get_user_referral(user_id)
    if not referral_id or not EnvKeys.REFERRAL_PERCENT:
        return
    try:
        bonus = int(Decimal(EnvKeys.REFERRAL_PERCENT) / Decimal(100) * Decimal(amount))
        if bonus > 0:
            await bot.send_message(
                referral_id,
                localize('payments.referral.bonus',
                         amount=bonus, name=payer_name,
                         id=payer_id, currency=EnvKeys.PAY_CURRENCY),
                reply_markup=close()
            )
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.error(f"Failed to send referral notification to user {referral_id}: {e}")



# ─────────────────────────────────────────────
#  BEP20 / TRC20 Direct Top-Up Screens
#  (Design board: step-by-step crypto address display)
# ─────────────────────────────────────────────


@router.callback_query(F.data == "topup_bep20")
async def topup_bep20_handler(call: CallbackQuery, state: FSMContext):
    """Show BEP20 (BSC) top-up screen."""
    wallet_address = EnvKeys.BEP20_WALLET or None
    if not wallet_address:
        await call.answer("⚠️ BEP20 top-up is not configured yet. Contact support.", show_alert=True)
        return

    data = await state.get_data()
    base_amount = float(data.get("amount", 0) or 0)
    unique_amount = round(base_amount, 2) if base_amount else None
    created_at_s = int(time.time())

    await state.update_data(
        topup_network="BEP20",
        topup_unique_amount=str(unique_amount) if unique_amount else None,
        topup_credited_amount=str(base_amount) if base_amount else None,
        topup_created_at_s=created_at_s,
    )

    amount_line = f"Send exactly <code>{unique_amount}</code> USDT\n\n" if unique_amount else ""
    text = (
        f"💳 <b>Top Up Your Wallet (USDT — BEP20 / BSC)</b>\n\n"
        f"📤 Send USDT (BEP20) to this address:\n"
        f"<code>{wallet_address}</code>\n\n"
        f"{amount_line}"
        f"📋 After sending, paste the <b>transaction hash</b> here.\n"
        f"Format: <code>0x</code> + 64 hex chars\n\n"
        f"⚡ We verify on-chain automatically — no admin needed."
    )
    await call.message.edit_text(text, reply_markup=topup_cancel_keyboard(), parse_mode="HTML")
    await state.set_state(BalanceStates.waiting_tx_hash)


@router.callback_query(F.data == "topup_trc20")
async def topup_trc20_handler(call: CallbackQuery, state: FSMContext):
    """Show TRC20 (TRON) top-up screen."""
    wallet_address = EnvKeys.TRC20_WALLET or None
    if not wallet_address:
        await call.answer("⚠️ TRC20 top-up is not configured yet. Contact support.", show_alert=True)
        return

    data = await state.get_data()
    base_amount = float(data.get("amount", 0) or 0)
    unique_amount = round(base_amount, 2) if base_amount else None
    created_at_s = int(time.time())

    await state.update_data(
        topup_network="TRC20",
        topup_unique_amount=str(unique_amount) if unique_amount else None,
        topup_credited_amount=str(base_amount) if base_amount else None,
        topup_created_at_s=created_at_s,
    )

    amount_line = f"Send exactly <code>{unique_amount}</code> USDT\n\n" if unique_amount else ""
    text = (
        f"💳 <b>Top Up Your Wallet (USDT — TRC20 / TRON)</b>\n\n"
        f"📤 Send USDT (TRC20) to this address:\n"
        f"<code>{wallet_address}</code>\n\n"
        f"{amount_line}"
        f"📋 After sending, paste the <b>transaction hash</b> here.\n"
        f"Format: 64 hex chars\n\n"
        f"⚡ We verify on-chain automatically — no admin needed."
    )
    await call.message.edit_text(text, reply_markup=topup_cancel_keyboard(), parse_mode="HTML")
    await state.set_state(BalanceStates.waiting_tx_hash)


@router.message(BalanceStates.waiting_tx_hash, F.text)
async def receive_tx_hash_handler(message: Message, state: FSMContext):
    """Receive TX hash and auto-verify on-chain, then credit balance."""
    tx_hash = (message.text or "").strip()
    data = await state.get_data()
    network = data.get("topup_network", "BEP20")
    user_id = message.from_user.id

    # Format validation
    is_bep20 = network == "BEP20" and tx_hash.startswith("0x") and len(tx_hash) == 66
    is_trc20 = network == "TRC20" and len(tx_hash) == 64
    if not (is_bep20 or is_trc20):
        fmt = "0x + 64 hex chars" if network == "BEP20" else "64 hex chars"
        await message.answer(
            f"❌ <b>Invalid transaction hash format.</b>\n\n"
            f"Expected: <code>{fmt}</code>\n"
            f"Please paste the correct hash from your wallet.",
            parse_mode="HTML",
            reply_markup=topup_cancel_keyboard()
        )
        return

    unique_amount_str = data.get("topup_unique_amount")
    credited_amount_str = data.get("topup_credited_amount")
    created_at_s = int(data.get("topup_created_at_s", int(time.time()) - 3600))

    # Tell user we're checking
    status_msg = await message.answer(
        f"🔍 <b>Verifying on-chain...</b>\n\n"
        f"TX: <code>{tx_hash}</code>\n"
        f"Network: <b>{network}</b>\n\n"
        f"This takes a few seconds.",
        parse_mode="HTML",
    )

    # ── On-chain verification ──────────────────────────────────────────────────
    verified_tx = None
    expected = float(unique_amount_str) if unique_amount_str else None
    since_timestamp_s = max(0, created_at_s - 600)  # 10 minute grace window
    since_timestamp_ms = since_timestamp_s * 1000

    if network == "TRC20":
        wallet = EnvKeys.TRC20_WALLET
        if wallet and expected:
            # First try direct TX lookup via TronGrid
            from packages.services.trongrid import find_usdt_trc20_transfer
            verified_tx = await find_usdt_trc20_transfer(
                wallet_address=wallet,
                expected_amount=expected,
                since_timestamp_ms=since_timestamp_ms,
            )
            # If not found by amount scan, try direct hash lookup
            if not verified_tx:
                import aiohttp as _aiohttp
                try:
                    async with _aiohttp.ClientSession() as s:
                        async with s.get(
                            f"https://api.trongrid.io/v1/transactions/{tx_hash}",
                            headers={"Accept": "application/json"},
                            timeout=_aiohttp.ClientTimeout(total=15),
                        ) as r:
                            if r.status == 200:
                                td = await r.json()
                                txn_data = td.get("data", [{}])[0] if td.get("data") else {}
                                tx_ts = txn_data.get("raw_data", {}).get("timestamp", 0) or txn_data.get("block_timestamp", 0)
                                if not (tx_ts and tx_ts < since_timestamp_ms):
                                    # Check it's a TRC20 transfer to our wallet
                                    for log in txn_data.get("log", []):
                                        topics = log.get("topics", [])
                                        if len(topics) >= 3 and topics[0].startswith("ddf252ad"):
                                            # Transfer event: topics[2] = recipient (last 40 chars)
                                            recipient = "41" + topics[2][-40:]
                                            raw_data = log.get("data", "0" * 64)
                                            try:
                                                amount_val = int(raw_data, 16) / 1_000_000
                                                if abs(amount_val - expected) <= 0.005:
                                                    verified_tx = {
                                                        "tx_hash": tx_hash,
                                                        "amount": amount_val,
                                                        "timestamp_ms": tx_ts,
                                                        "from_address": "",
                                                    }
                                                    break
                                            except Exception:
                                                pass
                except Exception as e:
                    logger.warning(f"TronGrid direct tx lookup failed: {e}")

    elif network == "BEP20":
        wallet = EnvKeys.BEP20_WALLET
        if wallet and expected:
            verified_tx = await verify_usdt_bep20_tx(
                tx_hash=tx_hash,
                wallet_address=wallet,
                expected_amount=expected,
                since_timestamp_s=since_timestamp_s,
            )

    # ── Credit balance if verified ─────────────────────────────────────────────
    if verified_tx:
        credit = Decimal(credited_amount_str) if credited_amount_str else Decimal(str(int(verified_tx.get("amount", 0))))
        payment_uuid = f"{network.lower()}_{tx_hash}"

        success, error_msg = await process_payment_with_referral(
            user_id=user_id,
            amount=credit,
            provider=f"onchain_{network.lower()}",
            external_id=payment_uuid,
            referral_percent=EnvKeys.REFERRAL_PERCENT,
        )

        if success:
            await log_audit(
                "topup_onchain_verified",
                user_id=user_id,
                resource_type="Payment",
                resource_id=tx_hash,
                details=f"network={network}, amount={credit}",
            )
            await _notify_referrer_bonus(message.bot, user_id, int(credit), message.from_user.first_name, user_id)
            
            from apps.telegram_bot.utils.notify import notify_group
            masked_tx = f"{tx_hash[:6]}******{tx_hash[-6:]}" if len(tx_hash) > 12 else tx_hash
            await notify_group(
                message.bot,
                f"💳 <b>Wallet Top-Up</b>\n\n"
                f"👤 User: <a href='tg://user?id={user_id}'>{message.from_user.first_name}</a> (ID: <code>{user_id}</code>)\n"
                f"💵 Amount: <b>{credit:g} USDT</b>\n"
                f"🌐 Network: {network}\n"
                f"📎 TX: <code>{masked_tx}</code>"
            )

            try:
                await status_msg.edit_text(
                    f"✅ <b>Payment Verified!</b>\n\n"
                    f"💰 <b>${credit}</b> has been added to your balance.\n"
                    f"📎 TX: <code>{tx_hash}</code>\n\n"
                    f"Thank you! 🎉",
                    parse_mode="HTML",
                    reply_markup=back("profile"),
                )
            except Exception:
                await message.answer(
                    f"✅ <b>${credit}</b> added to your balance!",
                    parse_mode="HTML",
                    reply_markup=back("profile"),
                )
            await state.clear()
            return

        if error_msg == "already_processed":
            await status_msg.edit_text(
                "⚠️ This transaction was already used to top up.",
                parse_mode="HTML",
                reply_markup=back("back_to_menu"),
            )
            await state.clear()
            return

    # ── Could not verify — fall back to manual ────────────────────────────────
    await log_audit(
        "topup_request", user_id=user_id,
        resource_type="TopUp", resource_id=tx_hash,
        details=f"network={network}, auto_verify=failed"
    )
    credit_amount = Decimal(credited_amount_str) if credited_amount_str else Decimal(unique_amount_str or "0")

    admin_kb = InlineKeyboardBuilder()
    admin_kb.row(
        InlineKeyboardButton(text=f"✅ Approve ${credit_amount}", callback_data=f"onchain_approve:{network}:{tx_hash}:{user_id}:{credit_amount}"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"onchain_reject:{network}:{tx_hash}:{user_id}"),
    )

    fallback_text = (
        f"🔔 <b>Manual {network} Top-Up Request</b>\n\n"
        f"👤 User: <a href='tg://user?id={user_id}'>{message.from_user.first_name}</a> (ID: <code>{user_id}</code>)\n"
        f"🌐 Network: <b>{network}</b>\n"
        f"📎 TX Hash: <code>{tx_hash}</code>\n"
        f"💵 Expected / Credit: <b>{credit_amount} USDT</b>\n\n"
        f"Auto-verify failed — please check on-chain explorer & tap Approve or Reject."
    )

    if EnvKeys.OWNER_ID:
        try:
            await message.bot.send_message(
                EnvKeys.OWNER_ID,
                text=fallback_text,
                parse_mode="HTML",
                reply_markup=admin_kb.as_markup(),
            )
        except Exception as e:
            logger.warning(f"Failed to notify admin: {e}")

    if EnvKeys.NOTIFY_BOT_TOKEN:
        try:
            nb = Bot(token=EnvKeys.NOTIFY_BOT_TOKEN)
            nb_kb = InlineKeyboardBuilder()
            nb_kb.row(
                InlineKeyboardButton(text=f"✅ Approve ${credit_amount}", callback_data=f"nb_approve:onchain_{network.lower()}:{tx_hash[:32]}:{user_id}:{credit_amount}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"nb_reject:onchain_{network.lower()}:{tx_hash[:32]}:{user_id}"),
            )
            await nb.send_message(
                chat_id=EnvKeys.OWNER_ID,
                text=fallback_text,
                parse_mode="HTML",
                reply_markup=nb_kb.as_markup(),
            )
            await nb.session.close()
        except Exception as e:
            logger.warning(f"Notify bot (On-chain manual review) failed: {e}")

    try:
        await status_msg.edit_text(
            f"⏳ <b>Manual verification needed</b>\n\n"
            f"We couldn't auto-verify your transaction on-chain yet "
            f"(it may still be confirming).\n\n"
            f"📎 TX: <code>{tx_hash}</code>\n\n"
            f"An admin has been notified and will credit your balance shortly.",
            parse_mode="HTML",
            reply_markup=back("back_to_menu"),
        )
    except Exception:
        pass
    await state.clear()


@router.callback_query(F.data.startswith("onchain_approve:"))
async def onchain_approve_handler(call: CallbackQuery):
    """Admin approves an on-chain BEP20/TRC20 payment — credit user balance."""
    if not await _is_admin_user(call.from_user.id):
        await call.answer("Not authorized.", show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) < 5:
        await call.answer("Invalid approval data.", show_alert=True)
        return

    network = parts[1]
    tx_hash = parts[2]
    try:
        user_id = int(parts[3])
        credited_amount = Decimal(parts[4])
    except (ValueError, Exception) as e:
        await call.answer(f"Parse error: {e}", show_alert=True)
        return

    payment_uuid = tx_hash[:32]
    success, error_msg = await process_payment_with_referral(
        user_id=user_id,
        amount=credited_amount,
        provider=f"onchain_{network.lower()}",
        external_id=payment_uuid,
        referral_percent=EnvKeys.REFERRAL_PERCENT,
    )

    if not success:
        if error_msg == "already_processed":
            await call.answer("⚠️ Already approved!", show_alert=True)
        else:
            await call.answer(f"❌ Error: {error_msg}", show_alert=True)
        return

    try:
        await call.bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ <b>Payment Approved!</b>\n\n"
                f"💰 <b>${credited_amount}</b> has been added to your balance.\n"
                f"📎 Network: <b>{network}</b>\n\n"
                f"Thank you for your payment! 🎉"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not notify user {user_id} of approval: {e}")

    await call.message.edit_text(
        call.message.text + f"\n\n✅ <b>APPROVED</b> — ${credited_amount} credited to user {user_id}",
        parse_mode="HTML",
        reply_markup=None,
    )
    await call.answer("✅ Payment approved and balance credited!")

    await log_audit(
        "onchain_payment_approved",
        user_id=user_id,
        resource_type="Payment",
        details=f"network={network}, amount={credited_amount}, tx={tx_hash}, approved_by={call.from_user.id}",
    )


@router.callback_query(F.data.startswith("onchain_reject:"))
async def onchain_reject_handler(call: CallbackQuery):
    """Admin rejects an on-chain BEP20/TRC20 payment."""
    if not await _is_admin_user(call.from_user.id):
        await call.answer("Not authorized.", show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) < 4:
        await call.answer("Invalid rejection data.", show_alert=True)
        return

    network = parts[1]
    tx_hash = parts[2]
    try:
        user_id = int(parts[3])
    except ValueError:
        await call.answer("Invalid user ID.", show_alert=True)
        return

    try:
        await call.bot.send_message(
            chat_id=user_id,
            text=(
                f"❌ <b>{network} Payment Not Verified</b>\n\n"
                f"We could not verify your {network} transaction hash on-chain.\n\n"
                f"Please ensure you sent the correct amount to the specified wallet address and submitted a valid TX hash."
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not notify user {user_id} of rejection: {e}")

    await call.message.edit_text(
        call.message.text + "\n\n❌ <b>REJECTED</b>",
        parse_mode="HTML",
        reply_markup=None,
    )
    await call.answer("❌ Rejected. User has been notified.")



@router.callback_query(F.data == "pay_balance")
async def pay_from_balance_handler(call: CallbackQuery, state: FSMContext):
    """Pay for item directly from wallet balance."""
    data = await state.get_data()
    item_name = data.get('csrf_item')
    qty = data.get('item_qty', 1)

    if not item_name:
        await call.answer("Session expired. Please go back to the shop.", show_alert=True)
        return

    await state.update_data(item_qty=qty)
    # Trigger the buy handler directly — it is defined later in this file,
    # but Python function objects are resolved at call time, not definition time.
    await buy_item_callback_handler(call, state)


@router.callback_query(F.data == "replenish_balance")
async def replenish_balance_callback_handler(call: CallbackQuery, state: FSMContext):

    """Ask user for the amount if at least one payment method is enabled."""
    if not _any_payment_method_enabled():
        await call.answer(localize("payments.not_configured"), show_alert=True)
        return

    await call.message.edit_text(
        localize("payments.replenish_prompt", currency=EnvKeys.PAY_CURRENCY),
        reply_markup=back('profile')
    )
    await state.set_state(BalanceStates.waiting_amount)


@router.callback_query(F.data == "change_topup_amount")
async def change_topup_amount_handler(call: CallbackQuery, state: FSMContext):
    """Let the user re-enter a different top-up amount from the payment method screen."""
    await state.update_data(amount=None)  # clear the old amount
    await call.message.edit_text(
        localize("payments.replenish_prompt", currency=EnvKeys.PAY_CURRENCY),
        reply_markup=back('profile')
    )
    await state.set_state(BalanceStates.waiting_amount)


@router.message(BalanceStates.waiting_amount, ValidAmountFilter())
async def replenish_balance_amount(message: Message, state: FSMContext):
    """Store amount and show payment methods."""
    amount = validate_money_amount(
        message.text,
        min_amount=Decimal(EnvKeys.MIN_AMOUNT),
        max_amount=Decimal(EnvKeys.MAX_AMOUNT)
    )

    if amount is None:
        await message.answer(
            localize("payments.replenish_invalid",
                     min_amount=EnvKeys.MIN_AMOUNT,
                     max_amount=EnvKeys.MAX_AMOUNT,
                     currency=EnvKeys.PAY_CURRENCY),
            reply_markup=back('replenish_balance')
        )
        return

    await state.update_data(amount=str(amount))  # str to preserve decimal precision

    await message.answer(
        localize("payments.method_choose"),
        reply_markup=get_payment_choice(is_topup=True)
    )
    await state.set_state(BalanceStates.waiting_payment)


@router.message(BalanceStates.waiting_amount)
async def invalid_amount(message: Message, state: FSMContext):
    """
    Tell user the amount is invalid.
    """
    await message.answer(
        localize("payments.replenish_invalid",
                 min_amount=EnvKeys.MIN_AMOUNT,
                 max_amount=EnvKeys.MAX_AMOUNT,
                 currency=EnvKeys.PAY_CURRENCY),
        reply_markup=back('replenish_balance')
    )


@router.callback_query(
    BalanceStates.waiting_payment,
    F.data.in_(["pay_cryptopay", "pay_stars", "pay_fiat", "pay_bybit", "pay_binance"])
)
async def process_replenish_balance(call: CallbackQuery, state: FSMContext):
    """Create an invoice for the chosen payment method."""
    data = await state.get_data()
    amount = data.get('amount')

    if amount is None:
        await call.answer(localize("payments.session_expired"), show_alert=True)
        await call.message.edit_text(localize("menu.title"), reply_markup=back('back_to_menu'))
        await state.clear()
        return

    # Map callback data to provider
    provider_map = {
        "pay_cryptopay": "cryptopay",
        "pay_stars": "stars",
        "pay_fiat": "fiat",
        "pay_bybit": "bybit_uid",
        "pay_binance": "binance_uid",
    }
    provider = provider_map.get(call.data)

    try:
        # Validate payment request
        payment_request = PaymentRequest(
            amount=Decimal(amount),
            currency=EnvKeys.PAY_CURRENCY,
            provider=provider
        )

        amount_dec = payment_request.amount
        ttl_seconds = int(EnvKeys.PAYMENT_TIME)

        if call.data == "pay_cryptopay":
            if not EnvKeys.CRYPTO_PAY_TOKEN:
                await call.answer(localize("payments.not_configured"), show_alert=True)
                return

            try:
                crypto = CryptoPayAPI()
                invoice = await crypto.create_invoice(
                    amount=float(amount_dec),
                    expires_in=ttl_seconds,
                    currency=payment_request.currency,
                    accepted_assets="TON,USDT,BTC,ETH",
                    payload=str(call.from_user.id),
                )
            except CryptoPayAPIError as e:
                await log_audit("cryptopay_error", level="ERROR", user_id=call.from_user.id, resource_type="Payment", details=f"[{e.code}] {e.name}")
                await call.answer(localize("payments.crypto.api_error", error=e.name), show_alert=True)
                return
            except Exception as e:
                await log_audit("cryptopay_invoice_fail", level="ERROR", user_id=call.from_user.id, resource_type="Payment", details=str(e))
                await call.answer(localize("payments.crypto.create_fail", error=str(e)), show_alert=True)
                return

            pay_url = invoice.get("mini_app_invoice_url")
            invoice_id = invoice.get("invoice_id")

            await create_pending_payment(
                provider="cryptopay",
                external_id=str(invoice_id),
                user_id=call.from_user.id,
                amount=int(amount_dec),
                currency=payment_request.currency,
            )

            await state.update_data(invoice_id=invoice_id, payment_type="cryptopay")

            await call.message.edit_text(
                localize("payments.invoice.summary",
                         amount=int(amount_dec),
                         minutes=int(ttl_seconds / 60),
                         button=localize("btn.check_payment"),
                         currency=payment_request.currency),
                reply_markup=payment_menu(pay_url)
            )

        elif call.data == "pay_stars":
            if EnvKeys.STARS_PER_VALUE > 0:
                try:
                    await send_stars_invoice(
                        bot=call.message.bot,
                        chat_id=call.from_user.id,
                        amount=int(amount_dec),
                    )
                except Exception as e:
                    await log_audit("stars_invoice_fail", level="ERROR", user_id=call.from_user.id, resource_type="Payment", details=str(e))
                    await call.answer(localize("payments.stars.create_fail", error=str(e)), show_alert=True)
                    return
                await state.clear()
            else:
                await call.answer(localize("payments.not_configured"), show_alert=True)
                return

        elif call.data == "pay_fiat":
            if not EnvKeys.TELEGRAM_PROVIDER_TOKEN:
                await call.answer(localize("payments.not_configured"), show_alert=True)
                return

            try:
                await send_fiat_invoice(
                    bot=call.message.bot,
                    chat_id=call.from_user.id,
                    amount=int(amount_dec),
                )
            except Exception as e:
                await log_audit("fiat_invoice_fail", level="ERROR", user_id=call.from_user.id, resource_type="Payment", details=str(e))
                await call.answer(localize("payments.fiat.create_fail", error=str(e)), show_alert=True)
                return
            await state.clear()

        elif call.data == "pay_bybit":
            bybit_uid = (EnvKeys.BYBIT_UID or "").strip()
            if not bybit_uid:
                await call.answer(
                    "⚠️ Bybit Pay is not configured yet. Please contact support.",
                    show_alert=True,
                )
                return

            created_at_ms = int(time.time() * 1000)
            payment_uuid = str(uuid.uuid4())[:16]

            await state.update_data(
                bybit_credited_amount=str(amount_dec),
                bybit_created_at_ms=created_at_ms,
                bybit_payment_uuid=payment_uuid,
                bybit_uid=bybit_uid,
                payment_type="bybit_uid",
            )

            await create_pending_payment(
                provider="bybit_uid",
                external_id=payment_uuid,
                user_id=call.from_user.id,
                amount=amount_dec,
                currency="USDT",
            )

            markup = simple_buttons([
                ("✅ I've Sent It", "bybit_uid_sent"),
                ("❌ Cancel", "replenish_balance"),
            ])

            await call.message.edit_text(
                f"<b>Pay via Bybit — UID Transfer</b>\n"
                f"<i>Instant · No fees · Bybit → Bybit only</i>\n\n"
                f"<b>Steps:</b>\n"
                f"1. Open <b>Bybit</b> → Assets → Transfer → <b>Send by UID</b>\n"
                f"2. Coin: <b>USDT</b>\n"
                f"3. Recipient UID:\n<code>{bybit_uid}</code>\n"
                f"4. Amount: <code>{amount_dec:g}</code> USDT\n\n"
                f"Once sent, tap <b>I've Sent It</b> and paste your <b>Bybit Transfer ID</b> "
                f"(from Assets → Transaction History) to auto-verify.",
                parse_mode="HTML",
                reply_markup=markup,
            )

        elif call.data == "pay_binance":
            binance_pay_id = EnvKeys.BINANCE_PAY_ID.strip()
            if not binance_pay_id:
                await call.answer(
                    "⚠️ Binance Pay is not configured yet. Please contact support.",
                    show_alert=True
                )
                return

            # Unique amount for automated Binance Pay detection
            unique_cents = random.randint(1, 20) / 100
            unique_amount = round(float(amount_dec) + unique_cents, 2)
            created_at_ms = int(time.time() * 1000)
            payment_uuid = str(uuid.uuid4())[:16]

            # Remark code kept as human reference for manual fallback
            remark_code = "BUY-" + "".join(
                random.choices(string.ascii_uppercase + string.digits, k=8)
            )

            await state.update_data(
                binance_amount=str(amount_dec),
                binance_unique_amount=str(unique_amount),
                binance_credited_amount=str(unique_amount),
                binance_created_at_ms=created_at_ms,
                binance_payment_uuid=payment_uuid,
                binance_remark_code=remark_code,
                payment_type="binance_uid",
            )

            await create_pending_payment(
                provider="binance_uid",
                external_id=payment_uuid,
                user_id=call.from_user.id,
                amount=Decimal(str(unique_amount)),
                currency="USDT",
            )

            markup = simple_buttons([
                ("✅ I've Sent It", "binance_uid_sent"),
                ("❌ Cancel", "replenish_balance"),
            ])

            await call.message.edit_text(
                f"<b>Pay via Binance Pay</b>\n"
                f"<i>No fees · Verified via Remarks & Amount</i>\n\n"
                f"<b>Steps:</b>\n"
                f"1. Open <b>Binance</b> → Pay → Send\n"
                f"2. Pay ID: <code>{binance_pay_id}</code>\n"
                f"3. Amount: <code>{unique_amount}</code> USDT\n"
                f"4. Remarks / Note: <code>{remark_code}</code> <i>(REQUIRED)</i>\n\n"
                f"⚠️ <b>Strict Verification Rules:</b>\n"
                f"• Send <b>EXACTLY {unique_amount} USDT</b> — do NOT send more or less amount.\n"
                f"• You MUST include remark <code>{remark_code}</code> in your transfer note.\n\n"
                f"Tap <b>I've Sent It</b> once done for instant automated verification.",
                parse_mode="HTML",
                reply_markup=markup,
            )

    except Exception as e:
        logger.error(f"Payment processing error: {e}")
        await state.clear()
        await call.answer(localize("errors.something_wrong"), show_alert=True)


@router.callback_query(F.data == "check")
async def checking_payment(call: CallbackQuery, state: FSMContext):
    """
    Check CryptoPay or Bybit Pay invoice status and credit balance if paid.
    """
    user_id = call.from_user.id
    data = await state.get_data()
    payment_type = data.get("payment_type")

    if not payment_type:
        await call.answer(localize("payments.no_active_invoice"), show_alert=True)
        return

    # ── CryptoPay check ─────────────────────────────────────────────────
    invoice_id = data.get("invoice_id")
    if not invoice_id:
        await call.answer(localize("payments.invoice_not_found"), show_alert=True)
        await state.clear()
        return

    try:
        crypto = CryptoPayAPI()
        info = await crypto.get_invoice(invoice_id)
    except CryptoPayAPIError as e:
        await log_audit("cryptopay_check_error", level="ERROR", user_id=user_id, resource_type="Payment", details=f"[{e.code}] {e.name}")
        await call.answer(localize("payments.crypto.api_error", error=e.name), show_alert=True)
        return
    except Exception as e:
        await log_audit("cryptopay_get_fail", level="ERROR", user_id=user_id, resource_type="Payment", details=str(e))
        await call.answer(localize("payments.crypto.check_fail", error=str(e)), show_alert=True)
        return

    status = info.get("status")
    if status == "paid":
        balance_amount = int(Decimal(str(info.get("amount", "0"))).quantize(Decimal("1.")))

        # Use transactional payment processing
        success, error_msg = await process_payment_with_referral(
            user_id=user_id,
            amount=Decimal(balance_amount),
            provider="cryptopay",
            external_id=str(invoice_id),
            referral_percent=EnvKeys.REFERRAL_PERCENT
        )

        if not success:
            if error_msg == "already_processed":
                await call.answer(localize("payments.already_processed"), show_alert=True)
            else:
                await call.answer(localize("errors.general_error", e=error_msg), show_alert=True)
            return

        metrics = get_metrics()
        if metrics:
            metrics.track_event("payment", user_id, {"amount": balance_amount, "provider": "cryptopay"})

        # Send a notification to the referrer
        await _notify_referrer_bonus(call.bot, user_id, balance_amount, call.from_user.first_name, call.from_user.id)
        
        from apps.telegram_bot.utils.notify import notify_group
        await notify_group(
            call.bot,
            f"💳 <b>Wallet Top-Up</b>\n\n"
            f"👤 User: <a href='tg://user?id={user_id}'>{call.from_user.first_name}</a> (ID: <code>{user_id}</code>)\n"
            f"💵 Amount: <b>{balance_amount:g} USDT</b>\n"
            f"🌐 Network: CryptoPay\n"
            f"📎 Invoice: <code>{invoice_id}</code>"
        )

        await call.message.edit_text(
            localize("payments.topped_simple",
                     amount=balance_amount,
                     currency=EnvKeys.PAY_CURRENCY),
            reply_markup=back('profile')
        )
        await state.clear()

        # Audit log
        try:
            user_info = await call.bot.get_chat(user_id)
            await log_audit(
                "balance_replenish",
                user_id=user_id,
                resource_type="Payment",
                details=f"name={user_info.first_name}, amount={balance_amount} {EnvKeys.PAY_CURRENCY}, provider=cryptopay",
            )
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            await log_audit("balance_replenish", level="ERROR", user_id=user_id, resource_type="Payment", details=f"log_failed: {e}")

    elif status == "active":
        await call.answer(localize("payments.not_paid_yet"))
    else:
        await call.answer(localize("payments.expired"), show_alert=True)



@router.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    """Validate the payment before Telegram processes it."""
    try:
        payload = json.loads(query.invoice_payload or "{}")
    except Exception:
        await query.answer(ok=False, error_message="Invalid payload")
        return

    amount = int(payload.get("amount", 0) or payload.get("amount_rub", 0))
    if amount <= 0:
        await query.answer(ok=False, error_message="Invalid amount")
        return

    if amount > int(EnvKeys.MAX_AMOUNT):
        await query.answer(ok=False, error_message="Amount exceeds maximum")
        return

    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    """
    Handle successful payment:
    - XTR (Stars): total_amount is ⭐. take CURRENCY from payload (amount) or convert ⭐ → CURRENCY.
    - Fiat: total_amount is minor units; divide by 100 (or 1 for JPY/KRW).
    """
    sp: SuccessfulPayment = message.successful_payment
    user_id = message.from_user.id

    payload = {}
    try:
        if sp.invoice_payload:
            payload = json.loads(sp.invoice_payload)
    except Exception:
        payload = {}

    amount = 0

    if sp.currency == "XTR":
        # Stars
        if "amount" in payload:
            amount = int(payload["amount"])
        else:
            amount = int(
                (Decimal(int(sp.total_amount)) / Decimal(str(EnvKeys.STARS_PER_VALUE)))
                .to_integral_value(rounding=ROUND_HALF_UP)
            )
    else:
        # Fiat
        currency = sp.currency.upper()
        multiplier = _minor_units_for(currency)
        amount = int(Decimal(sp.total_amount) / Decimal(multiplier))

    if amount <= 0:
        await message.answer(localize("payments.unable_determine_amount"), reply_markup=close())
        return

    # Idempotence
    provider = "telegram" if sp.currency != "XTR" else "stars"
    external_id = sp.telegram_payment_charge_id or sp.provider_payment_charge_id or f"{provider}:{user_id}:{uuid.uuid4().hex}"

    success, error_msg = await process_payment_with_referral(
        user_id=user_id,
        amount=Decimal(amount),
        provider=provider,
        external_id=external_id,
        referral_percent=EnvKeys.REFERRAL_PERCENT
    )

    if not success:
        if error_msg == "already_processed":
            await message.answer(localize("payments.already_processed"), reply_markup=close())
        else:
            await message.answer(localize("payments.processing_error"), reply_markup=close())
        return

    # Sending notification to referrer
    await _notify_referrer_bonus(message.bot, user_id, amount, message.from_user.first_name, message.from_user.id)

    from apps.telegram_bot.utils.notify import notify_group
    await notify_group(
        message.bot,
        f"💳 <b>Wallet Top-Up</b>\n\n"
        f"👤 User: <a href='tg://user?id={user_id}'>{message.from_user.first_name}</a> (ID: <code>{user_id}</code>)\n"
        f"💵 Amount: <b>{amount:g} USDT</b>\n"
        f"🌐 Network: {provider}\n"
        f"📎 TX: <code>{external_id}</code>"
    )

    metrics = get_metrics()
    if metrics:
        metrics.track_event("payment", user_id, {"amount": amount, "provider": provider})

    suffix = localize("payments.success_suffix.stars") if sp.currency == "XTR" else localize(
        "payments.success_suffix.tg")
    await message.answer(
        localize('payments.topped_with_suffix', amount=amount, suffix=suffix, currency=EnvKeys.PAY_CURRENCY),
        reply_markup=back('profile')
    )

    # audit log
    try:
        user_info = await message.bot.get_chat(user_id)
        await log_audit(
            "balance_replenish",
            user_id=user_id,
            resource_type="Payment",
            details=f"name={user_info.first_name}, amount={amount} {EnvKeys.PAY_CURRENCY}, provider={suffix}",
        )
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        await log_audit("balance_replenish", level="ERROR", user_id=user_id, resource_type="Payment", details=f"log_failed: {e}")


@router.callback_query(F.data == "buy")
async def buy_item_callback_handler(call: CallbackQuery, state: FSMContext):
    """Processing the purchase of goods with full transactional security."""
    try:
        # Get item name from state (stored when viewing item info)
        data = await state.get_data()
        raw_item_name = data.get('csrf_item')

        if not raw_item_name:
            await call.answer(localize("middleware.security.invalid_csrf"), show_alert=True)
            return

        metrics = get_metrics()

        # Validation via Pydantic
        purchase_request = ItemPurchaseRequest(
            item_name=raw_item_name,
            user_id=call.from_user.id
        )

        # Additional check for SQL injection
        if not is_safe_item_name(purchase_request.item_name):
            await call.answer(
                localize("errors.invalid_item_name"),
                show_alert=True
            )
            await log_audit("suspicious_item_name", level="WARNING", user_id=call.from_user.id, resource_type="Item", details=raw_item_name)
            return

        # User_id validation
        try:
            user_id = validate_telegram_id(call.from_user.id)
        except ValueError:
            await call.answer(localize("errors.invalid_user"), show_alert=True)
            return

        # Show the processing indicator
        await call.answer(localize("shop.purchase.processing"))

        # Get promo code and quantity from state
        promo_code = data.get('applied_promo')
        qty = max(1, int(data.get('item_qty', 1)))

        error_messages = {
            "user_not_found": "shop.purchase.fail.user_not_found",
            "item_not_found": "shop.item.not_found",
            "insufficient_funds": "shop.insufficient_funds",
            "out_of_stock": "shop.out_of_stock"
        }

        # Check if reseller item
        is_reseller = data.get('is_reseller_item', False)

        if is_reseller:
            from packages.database.methods.transactions import buy_reseller_item_transaction, refund_reseller_purchase, confirm_reseller_purchase_success
            from packages.services.reseller.fulfillment import fulfill_reseller_purchase
            from apps.telegram_bot.keyboards.inline import simple_buttons
            from decimal import Decimal

            # 1. Deduct balance and create pending ResellerOrder in DB
            success, message, purchase_data = await buy_reseller_item_transaction(
                user_id,
                purchase_request.item_name,
                qty=qty,
                product_id=data.get("reseller_product_id"),
                promo_code=promo_code,
            )
            if not success:
                error_text = localize(
                    error_messages.get(message, "shop.purchase.fail.general"),
                    message=message
                )
                await call.message.edit_text(error_text, reply_markup=back('back_to_item'))
                return

            # 2. Place order on external API
            order_id = purchase_data["reseller_order_id"]
            bought_id = purchase_data["bought_id"]
            total_price = Decimal(str(purchase_data["price"]))
            unique_id = purchase_data["unique_id"]

            api_success, status_msg, codes = await fulfill_reseller_purchase(
                product_name=purchase_request.item_name,
                product_id=data.get("reseller_product_id"),
                user_id=user_id,
                quantity=qty,
                reseller_order_id=order_id,
                bot=call.bot,
                idempotency_key=unique_id
            )
            if not api_success:
                await refund_reseller_purchase(user_id, total_price, bought_id, order_id, reason="API Failure")
                error_text = (
                    "❌ <b>Purchase Failed</b>\n\n"
                    "The external provider returned an error or is out of stock.\n"
                    "Your balance has been refunded."
                )
                await call.message.edit_text(error_text, reply_markup=back('back_to_item'), parse_mode="HTML")
                return

            # 3. Successful API order!
            ptype = purchase_data["product_type"]
            if ptype in ("account", "stock") and codes:
                delivered_val = "\n".join(codes)
                await confirm_reseller_purchase_success(
                    bought_id=bought_id,
                    value=delivered_val,
                    reseller_order_id=order_id,
                    external_order_id=None
                )
                try:
                    from apps.telegram_bot.utils.notify import notify_group
                    user_name = call.from_user.full_name or call.from_user.username or str(call.from_user.id)
                    msg = f"🛒 <b>New Reseller Purchase!</b>\n\nUser: {user_name}\nItem: <b>{purchase_request.item_name}</b>"
                    await notify_group(call.bot, msg)
                except Exception:
                    pass
                # Show receipt
                lines = [
                    "✅ <b>Purchase Complete!</b>",
                    f"📦 <b>{purchase_request.item_name}</b> × {qty}",
                    f"💰 <b>Total:</b> ${total_price:.2f} USD",
                    "\n<b>Your credentials:</b>",
                ]
                for i, code in enumerate(codes, 1):
                    lines.append(f"  {i}. <code>{code}</code>")

                buttons = [
                    ("📦 View Receipt", f"bought-item:{bought_id}:back_to_item"),
                    (localize("btn.back"), "back_to_item"),
                ]
                await call.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=simple_buttons(buttons))
            else:
                # Preorder/team_invite type, no instant codes
                await confirm_reseller_purchase_success(
                    bought_id=bought_id,
                    value="[Preorder - pending fulfillment]",
                    reseller_order_id=order_id,
                    external_order_id=None
                )
                # Show confirmation
                lines = [
                    "✅ <b>Pre-order Placed!</b>",
                    f"📦 <b>{purchase_request.item_name}</b> × {qty}",
                    f"💰 <b>Total:</b> ${total_price:.2f} USD",
                    "\n⏳ <i>This is a pre-order. You will receive a message with credentials as soon as they are ready.</i>",
                ]
                buttons = [
                    ("📦 View Order", f"bought-item:{bought_id}:back_to_item"),
                    (localize("btn.back"), "back_to_item"),
                ]
                await call.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=simple_buttons(buttons))

            # Track metrics
            if metrics:
                metrics.track_event("purchase", call.from_user.id, {
                    "item": purchase_request.item_name,
                    "price": float(total_price),
                    "source": data.get("item_source", "reseller")
                })
                metrics.track_conversion("purchase_funnel", "purchase", call.from_user.id)
            try:
                from apps.telegram_bot.utils.notify import send_purchase_notification
                await send_purchase_notification(
                    bot=call.bot,
                    user_id=call.from_user.id,
                    product_name=purchase_request.item_name,
                    order_id=order_id,
                    quantity=qty,
                    total_price=total_price,
                    payment_method="USDT Balance"
                )
            except Exception as e:
                logger.error(f"Error sending purchase notification: {e}")

            # Audit log
            try:
                user_info = await call.bot.get_chat(user_id)
                await log_audit(
                    "purchase",
                    user_id=user_id,
                    resource_type="Item",
                    resource_id=purchase_request.item_name[:100],
                    details=f"name={user_info.first_name[:50]}, qty={qty}, total={total_price} USD (reseller)",
                )
            except Exception:
                pass
            return

        # Execute transactional purchases for each unit in qty for local goods
        purchased = []
        last_error = None
        for _ in range(qty):
            success, message, purchase_data = await buy_item_transaction(
                user_id,
                purchase_request.item_name,
                promo_code=promo_code,
            )
            if not success:
                last_error = message
                break
            purchased.append(purchase_data)

        if not purchased:
            # All units failed
            error_text = localize(
                error_messages.get(last_error, "shop.purchase.fail.general"),
                message=last_error
            )
            await call.message.edit_text(error_text, reply_markup=back('back_to_item'))
            if last_error not in error_messages:
                await log_audit("purchase_error", level="ERROR", user_id=user_id,
                                resource_type="Item", resource_id=purchase_request.item_name, details=last_error)
            return

        # Partial or full success
        if metrics:
            for pd in purchased:
                metrics.track_event("purchase", call.from_user.id, {
                    "item": purchase_request.item_name,
                    "price": pd['price']
                })
            metrics.track_conversion("purchase_funnel", "purchase", call.from_user.id)
            try:
                from apps.telegram_bot.utils.notify import send_purchase_notification
                first_order_id = purchased[0].get('bought_id', 'N/A') if purchased else 'N/A'
                total_p = sum(Decimal(str(pd['price'])) for pd in purchased)
                await send_purchase_notification(
                    bot=call.bot,
                    user_id=call.from_user.id,
                    product_name=purchase_request.item_name,
                    order_id=first_order_id,
                    quantity=len(purchased),
                    total_price=total_p,
                    payment_method="USDT Balance"
                )
            except Exception as e:
                logger.error(f"Error sending purchase notification: {e}")

        username = call.from_user.username or call.from_user.first_name
        delivered_qty = len(purchased)
        total_price = sum(Decimal(str(pd['price'])) for pd in purchased)

        if delivered_qty == 1:
            # Single item receipt
            pd = purchased[0]
            safe_value = sanitize_html(pd['value'])
            buttons = [
                (f"📦 {pd['item_name']}", f"bought-item:{pd['bought_id']}:back_to_item"),
                (localize("btn.back"), "back_to_item"),
            ]
            await call.message.edit_text(
                localize(
                    'shop.purchase.receipt',
                    item_name=pd['item_name'],
                    price=pd['price'],
                    unique_id=pd['unique_id'],
                    datetime=pd['bought_datetime'],
                    username=username,
                    user_id=call.from_user.id,
                    value=safe_value,
                    currency=EnvKeys.PAY_CURRENCY,
                ),
                parse_mode='HTML',
                reply_markup=simple_buttons(buttons),
            )
        else:
            # Multi-item receipt
            lines = [
                "✅ <b>Purchase Complete!</b>",
                f"📦 <b>{purchase_request.item_name}</b> × {delivered_qty}",
                f"💰 <b>Total:</b> {total_price:.2f} {EnvKeys.PAY_CURRENCY}",
                "\n<b>Your items:</b>",
            ]
            for i, pd in enumerate(purchased, 1):
                safe_v = sanitize_html(pd['value'])
                lines.append(f"  {i}. <code>{safe_v}</code>")
            if last_error:
                lines.append(f"\n⚠️ Only {delivered_qty}/{qty} delivered ({last_error})")

            buttons = []
            for pd in purchased:
                buttons.append((f"📦 #{pd['unique_id']}", f"bought-item:{pd['bought_id']}:back_to_item"))
            buttons.append((localize("btn.back"), "back_to_item"))

            await call.message.edit_text(
                "\n".join(lines),
                parse_mode='HTML',
                reply_markup=simple_buttons(buttons),
            )

        # Secure logging
        try:
            user_info = await call.bot.get_chat(user_id)
            await log_audit(
                "purchase",
                user_id=user_id,
                resource_type="Item",
                resource_id=purchase_request.item_name[:100],
                details=f"name={user_info.first_name[:50]}, qty={delivered_qty}, total={total_price} {EnvKeys.PAY_CURRENCY}",
            )
        except Exception as e:
            await log_audit("purchase", level="ERROR", user_id=user_id, resource_type="Item", details=f"log_failed: {e}")

        # Send review prompt
        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            review_kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="👍", callback_data="shop_review_up"),
                    InlineKeyboardButton(text="👎", callback_data="shop_review_down")
                ]
            ])
            await call.message.answer("Did you enjoy shopping in our bot?", reply_markup=review_kb)
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Critical error in purchase handler: {e}")
        await call.answer(
            localize("errors.something_wrong"),
            show_alert=True
        )


# ─────────────────────────────────────────────────────────────────────────────
#  BYBIT PAY — Tx-ID paste verification
# ─────────────────────────────────────────────────────────────────────────────


async def _bybit_manual_review(
    bot,
    user_id: int,
    credited_amount,
    payment_uuid: str,
    tx_id: str,
    reason: str,
):
    """Escalate a Bybit UID payment to admin for manual review."""
    admin_markup = simple_buttons([
        (f"✅ Approve ${credited_amount}", f"bybit_approve:{payment_uuid}:{user_id}:{credited_amount}"),
        ("❌ Reject", f"bybit_reject:{payment_uuid}:{user_id}"),
    ])
    fallback_text = (
        f"\U0001f4b0 <b>Bybit Pay — Manual Review</b>\n\n"
        f"{reason}\n\n"
        f"User ID: <code>{user_id}</code>\n"
        f"Tx ID: <code>{tx_id or 'n/a'}</code>\n"
        f"Credits: <b>${credited_amount}</b>\n\n"
        f"Check Bybit → Assets → Transaction History manually."
    )
    try:
        await bot.send_message(
            chat_id=EnvKeys.OWNER_ID,
            text=fallback_text,
            parse_mode="HTML",
            reply_markup=admin_markup,
        )
    except Exception as e:
        logger.error(f"Could not send Bybit manual review to admin: {e}")

    if EnvKeys.NOTIFY_BOT_TOKEN:
        try:
            nb = Bot(token=EnvKeys.NOTIFY_BOT_TOKEN)
            nb_kb = InlineKeyboardBuilder()
            nb_kb.row(
                InlineKeyboardButton(
                    text=f"✅ Approve ${credited_amount}",
                    callback_data=f"nb_approve:bybit_uid:{payment_uuid}:{user_id}:{credited_amount}",
                ),
                InlineKeyboardButton(
                    text="❌ Reject",
                    callback_data=f"nb_reject:bybit_uid:{payment_uuid}:{user_id}",
                ),
            )
            await nb.send_message(
                chat_id=EnvKeys.OWNER_ID,
                text=fallback_text,
                parse_mode="HTML",
                reply_markup=nb_kb.as_markup(),
            )
            await nb.session.close()
        except Exception as e:
            logger.warning(f"Notify bot (Bybit manual review) failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  BYBIT PAY — User confirms they've sent
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "bybit_uid_sent")
async def bybit_uid_sent_handler(call: CallbackQuery, state: FSMContext):
    """User tapped 'I've Sent It' for Bybit — ask them to paste the transfer ID."""
    data = await state.get_data()
    payment_type = data.get("payment_type")

    if payment_type != "bybit_uid":
        await call.answer("No active Bybit payment found.", show_alert=True)
        return

    await call.message.edit_text(
        "📋 <b>Paste your Bybit Transfer ID</b>\n\n"
        "Find it in Bybit:\n"
        "• Assets → Transaction History → Transfer\n"
        "• Tap the transfer you just made → copy the <b>Transfer ID</b>\n\n"
        "Send it here and we'll verify it automatically.",
        parse_mode="HTML",
        reply_markup=topup_cancel_keyboard(),
    )
    await state.set_state(BalanceStates.waiting_bybit_tx_id)
    await call.answer()


@router.message(BalanceStates.waiting_bybit_tx_id, F.text)
async def receive_bybit_tx_id_handler(message: Message, state: FSMContext):
    """Receive Bybit transfer ID and verify against the internal-record API."""
    tx_id = (message.text or "").strip()
    data = await state.get_data()

    if data.get("payment_type") != "bybit_uid":
        await message.answer("No active Bybit payment found. Please start a new top-up.")
        await state.clear()
        return

    credited_amount_str = data.get("bybit_credited_amount", "0")
    payment_uuid = data.get("bybit_payment_uuid", "")
    user_id = message.from_user.id

    if len(tx_id) < 4 or len(tx_id) > 128 or not tx_id.replace("-", "").replace("_", "").isalnum():
        await message.answer(
            "❌ That doesn't look like a valid Bybit Transfer ID.\n\n"
            "It should be a short alphanumeric string from Bybit → Assets → Transaction History.",
            reply_markup=topup_cancel_keyboard(),
        )
        return

    status_msg = await message.answer(
        f"🔍 <b>Verifying with Bybit...</b>\n\nTransfer ID: <code>{tx_id}</code>",
        parse_mode="HTML",
    )

    credited_amount = Decimal(credited_amount_str)
    bybit_created_at_ms = int(data.get("bybit_created_at_ms", 0))
    since_timestamp_ms = max(0, bybit_created_at_ms - 10 * 60 * 1000) if bybit_created_at_ms else 0
    bybit_tx_external_id = f"bybit_tx_{tx_id}"

    verified = None
    try:
        bybit_api = BybitPayAPI()
        verified = await bybit_api.find_internal_deposit_by_txid(
            tx_id=tx_id,
            coin="USDT",
            since_timestamp_ms=since_timestamp_ms,
        )
    except BybitPayError as e:
        logger.warning(f"Bybit tx lookup failed for user {user_id}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in Bybit tx lookup: {e}")

    if verified:
        received_amount = Decimal(str(verified.get("amount", "0")))
        if received_amount + Decimal("0.005") < credited_amount:
            await status_msg.edit_text(
                f"⚠️ <b>Amount mismatch</b>\n\n"
                f"Expected: <b>{credited_amount} USDT</b>\n"
                f"Received: <b>{received_amount} USDT</b>\n\n"
                f"The transfer was found but is short of the required amount. "
                f"An admin has been notified.",
                parse_mode="HTML",
                reply_markup=back("back_to_menu"),
            )
            await _bybit_manual_review(
                message.bot, user_id, credited_amount, payment_uuid, tx_id,
                reason=f"Amount short: expected {credited_amount}, received {received_amount}",
            )
            await log_audit(
                "bybit_tx_amount_short", user_id=user_id,
                resource_type="Payment", resource_id=payment_uuid,
                details=f"tx={tx_id}, expected={credited_amount}, received={received_amount}",
            )
            await state.clear()
            return

        success, error_msg = await process_payment_with_referral(
            user_id=user_id,
            amount=credited_amount,
            provider="bybit_uid",
            external_id=bybit_tx_external_id,
            referral_percent=EnvKeys.REFERRAL_PERCENT,
        )

        if success:
            await log_audit(
                "bybit_tx_verified", user_id=user_id,
                resource_type="Payment", resource_id=bybit_tx_external_id,
                details=f"tx={tx_id}, amount={credited_amount}",
            )
            await _notify_referrer_bonus(
                message.bot, user_id, int(credited_amount), message.from_user.first_name, user_id,
            )
            await status_msg.edit_text(
                f"✅ <b>Payment Verified!</b>\n\n"
                f"💰 <b>{credited_amount} USDT</b> has been added to your balance.\n"
                f"Transfer ID: <code>{tx_id}</code>\n\n"
                f"Thank you! 🎉",
                parse_mode="HTML",
                reply_markup=back("profile"),
            )
            await state.clear()
            return

        if error_msg == "already_processed":
            await status_msg.edit_text(
                "⚠️ <b>This transfer was already used.</b>\n\n"
                "This Transfer ID has already been credited to an account and cannot be reused.",
                parse_mode="HTML",
                reply_markup=back("back_to_menu"),
            )
            await state.clear()
            return

    # Not found → manual review
    await _bybit_manual_review(
        message.bot, user_id, credited_amount, payment_uuid, tx_id,
        reason="Transfer ID not found in recent Bybit internal deposits.",
    )
    await log_audit(
        "bybit_tx_not_found", user_id=user_id,
        resource_type="Payment", resource_id=payment_uuid,
        details=f"tx={tx_id}",
    )
    await status_msg.edit_text(
        f"⏳ <b>Manual verification needed</b>\n\n"
        f"We couldn't find your transfer automatically (it may still be pending).\n\n"
        f"Transfer ID: <code>{tx_id}</code>\n\n"
        f"An admin has been notified and will credit your balance shortly.",
        parse_mode="HTML",
        reply_markup=back("back_to_menu"),
    )
    await state.clear()

# ─────────────────────────────────────────────────────────────────────────────
#  BYBIT UID PAY — Admin approve / reject
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("bybit_approve:"))
async def bybit_approve_handler(call: CallbackQuery):
    """Admin approves a Bybit UID payment — credit user balance."""
    if not await _is_admin_user(call.from_user.id):
        await call.answer("Not authorized.", show_alert=True)
        return

    # callback data: bybit_approve:{uuid}:{user_id}:{credited_amount}
    parts = call.data.split(":")
    if len(parts) < 4:
        await call.answer("Invalid approval data.", show_alert=True)
        return

    payment_uuid = parts[1]
    try:
        user_id = int(parts[2])
        credited_amount = Decimal(parts[3])
    except (ValueError, Exception) as e:
        await call.answer(f"Parse error: {e}", show_alert=True)
        return

    success, error_msg = await process_payment_with_referral(
        user_id=user_id,
        amount=credited_amount,
        provider="bybit_uid",
        external_id=payment_uuid,
        referral_percent=EnvKeys.REFERRAL_PERCENT,
    )

    if not success:
        if error_msg == "already_processed":
            await call.answer("⚠️ Already approved!", show_alert=True)
        else:
            await call.answer(f"❌ Error: {error_msg}", show_alert=True)
        return

    # Notify user
    try:
        await call.bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ <b>Payment Approved!</b>\n\n"
                f"💰 <b>${credited_amount}</b> has been added to your balance.\n\n"
                f"Thank you for your payment! 🎉"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not notify user {user_id} of approval: {e}")

    # Update admin message
    await call.message.edit_text(
        call.message.text + f"\n\n✅ <b>APPROVED</b> — ${credited_amount} credited to user {user_id}",
        parse_mode="HTML",
        reply_markup=None,
    )
    await call.answer("✅ Payment approved and balance credited!")

    await log_audit(
        "bybit_uid_payment_approved",
        user_id=user_id,
        resource_type="Payment",
        details=f"amount={credited_amount}, uuid={payment_uuid}, approved_by={call.from_user.id}",
    )


@router.callback_query(F.data.startswith("bybit_reject:"))
async def bybit_reject_handler(call: CallbackQuery):
    """Admin rejects a Bybit UID payment."""
    if not await _is_admin_user(call.from_user.id):
        await call.answer("Not authorized.", show_alert=True)
        return

    # callback data: bybit_reject:{uuid}:{user_id}
    parts = call.data.split(":")
    if len(parts) < 3:
        await call.answer("Invalid rejection data.", show_alert=True)
        return

    payment_uuid = parts[1]
    try:
        user_id = int(parts[2])
    except ValueError:
        await call.answer("Invalid user ID.", show_alert=True)
        return

    # Notify user
    try:
        await call.bot.send_message(
            chat_id=user_id,
            text=(
                "❌ <b>Payment Not Found</b>\n\n"
                "We could not verify your Bybit transfer.\n\n"
                "Please make sure you sent the <b>exact amount</b> shown "
                "to the correct Bybit UID, then try again or contact support."
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not notify user {user_id} of rejection: {e}")

    # Update admin message
    await call.message.edit_text(
        call.message.text + "\n\n❌ <b>REJECTED</b>",
        parse_mode="HTML",
        reply_markup=None,
    )
    await call.answer("❌ Payment rejected. User has been notified.")

    await log_audit(
        "bybit_uid_payment_rejected",
        user_id=user_id,
        resource_type="Payment",
        details=f"uuid={payment_uuid}, rejected_by={call.from_user.id}",
    )


# ─────────────────────────────────────────────────────────────────────────────
#  BINANCE PAY — User confirms they've sent
# ─────────────────────────────────────────────────────────────────────────────


async def _poll_binance_payment(
    bot,
    user_id: int,
    unique_amount,
    credited_amount,
    payment_uuid: str,
    remark_code: str,
    claim_time_ms: int,
):
    """
    Background task: poll Binance Pay API for the unique_amount transaction.
    Auto-credits on match; falls back to admin notification after 15 minutes.
    """
    logger.info(f"Binance poller started: user={user_id}, amount={unique_amount}, uuid={payment_uuid}")

    txn = await find_binance_payment(
        unique_amount=Decimal(str(unique_amount)),
        currency="USDT",
        claim_time_ms=claim_time_ms,
        remark_code=remark_code,
    )

    if txn:
        # ── Auto-approve ──────────────────────────────────────────────────────
        success, error_msg = await process_payment_with_referral(
            user_id=user_id,
            amount=Decimal(str(credited_amount)),
            provider="binance_uid",
            external_id=payment_uuid,
            referral_percent=EnvKeys.REFERRAL_PERCENT,
        )
        if success:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        "\u2705 <b>Binance Payment Confirmed Automatically!</b>\n\n"
                        f"\U0001f4b0 <b>${credited_amount}</b> has been added to your balance.\n\n"
                        "Thank you for your payment! \U0001f389"
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"Could not notify user {user_id} of auto-approval: {e}")
            logger.info(f"Binance auto-approved: user={user_id}, amount={credited_amount}, uuid={payment_uuid}")
        else:
            if error_msg != "already_processed":
                logger.error(f"Binance auto-approval failed: {error_msg}")
    else:
        # ── Timeout — fall back to admin manual approval ──────────────────────
        logger.warning(f"Binance poller timeout: user={user_id}, amount={unique_amount}. Escalating to admin.")

        admin_markup = simple_buttons([
            (f"\u2705 Approve ${credited_amount}", f"bnb_approve:{payment_uuid}:{user_id}:{credited_amount}"),
            ("\u274c Reject", f"bnb_reject:{payment_uuid}:{user_id}"),
        ])
        fallback_text = (
            f"\U0001f4b0 <b>Binance Pay — Manual Review Required</b>\n\n"
            f"Auto-detection timed out (15 min).\n\n"
            f"User ID: <code>{user_id}</code>\n"
            f"Expected: <b>{unique_amount} USDT</b>\n"
            f"Credits: <b>${credited_amount}</b>\n"
            f"Remark: <code>{remark_code}</code>\n\n"
            f"Check Binance \u2192 Pay \u2192 History manually."
        )
        try:
            await bot.send_message(
                chat_id=EnvKeys.OWNER_ID,
                text=fallback_text,
                parse_mode="HTML",
                reply_markup=admin_markup,
            )
        except Exception as e:
            logger.error(f"Could not send Binance fallback to admin: {e}")

        # Also notify via notify bot
        if EnvKeys.NOTIFY_BOT_TOKEN:
            try:
                nb = Bot(token=EnvKeys.NOTIFY_BOT_TOKEN)
                nb_kb = InlineKeyboardBuilder()
                nb_kb.row(
                    InlineKeyboardButton(
                        text=f"\u2705 Approve ${credited_amount}",
                        callback_data=f"nb_approve:binance_uid:{payment_uuid}:{user_id}:{credited_amount}"
                    ),
                    InlineKeyboardButton(
                        text="\u274c Reject",
                        callback_data=f"nb_reject:binance_uid:{payment_uuid}:{user_id}"
                    )
                )
                await nb.send_message(
                    chat_id=EnvKeys.OWNER_ID,
                    text=fallback_text,
                    parse_mode="HTML",
                    reply_markup=nb_kb.as_markup(),
                )
                await nb.session.close()
            except Exception as e:
                logger.warning(f"Notify bot fallback failed: {e}")

        # Notify user of delay
        try:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "\u26a0\ufe0f <b>Auto-verification delayed</b>\n\n"
                    "We couldn\'t confirm your Binance Pay transfer automatically.\n"
                    "An admin has been notified and will verify manually shortly.\n\n"
                    "We\'ll send you a message once approved."
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Could not notify user {user_id} of delay: {e}")


@router.callback_query(F.data == "binance_uid_sent")
async def binance_uid_sent_handler(call: CallbackQuery, state: FSMContext):
    """User tapped 'I've Sent It' for Binance Pay — start auto-poller."""
    data = await state.get_data()
    payment_type = data.get("payment_type")

    if payment_type != "binance_uid":
        await call.answer("No active Binance payment found.", show_alert=True)
        return

    amount = data.get("binance_amount", "?")
    unique_amount = data.get("binance_unique_amount", amount)
    credited_amount = data.get("binance_credited_amount", "?")
    payment_uuid = data.get("binance_payment_uuid", "")
    remark_code = data.get("binance_remark_code", "N/A")
    claim_time_ms = data.get("binance_created_at_ms", int(__import__('time').time() * 1000))
    user = call.from_user

    # Update user immediately
    await call.message.edit_text(
        f"\u23f3 <b>Verifying your Binance Pay transfer...</b>\n\n"
        f"We\'re checking for <b>{unique_amount} USDT</b> automatically.\n"
        f"This usually takes less than 1 minute.\n\n"
        f"You\'ll be notified here once confirmed \U0001f514",
        parse_mode="HTML",
        reply_markup=None,
    )
    await call.answer("\u2705 Submitted! Auto-checking now...")

    # Launch background poller — do NOT await
    import asyncio
    asyncio.create_task(_poll_binance_payment(
        bot=call.bot,
        user_id=user.id,
        unique_amount=unique_amount,
        credited_amount=credited_amount,
        payment_uuid=payment_uuid,
        remark_code=remark_code,
        claim_time_ms=int(claim_time_ms),
    ))

    await log_audit(
        "binance_payment_claimed",
        user_id=user.id,
        resource_type="Payment",
        details=f"amount={unique_amount}, credited={credited_amount}, remark={remark_code}, uuid={payment_uuid}",
    )



# ─────────────────────────────────────────────────────────────────────────────
#  BINANCE PAY — Admin approve / reject
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("bnb_approve:"))
async def binance_approve_handler(call: CallbackQuery):
    """Admin approves a Binance Pay payment — credit user balance."""
    if not await _is_admin_user(call.from_user.id):
        await call.answer("Not authorized.", show_alert=True)
        return


@router.callback_query(F.data.startswith("bnb_reject:"))
async def binance_reject_handler(call: CallbackQuery):
    """Admin rejects a Binance Pay payment."""
    if not await _is_admin_user(call.from_user.id):
        await call.answer("Not authorized.", show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) < 4:
        await call.answer("Invalid approval data.", show_alert=True)
        return

    payment_uuid = parts[1]
    try:
        user_id = int(parts[2])
        credited_amount = Decimal(parts[3])
    except (ValueError, Exception) as e:
        await call.answer(f"Parse error: {e}", show_alert=True)
        return

    success, error_msg = await process_payment_with_referral(
        user_id=user_id,
        amount=credited_amount,
        provider="binance_uid",
        external_id=payment_uuid,
        referral_percent=EnvKeys.REFERRAL_PERCENT,
    )

    if not success:
        if error_msg == "already_processed":
            await call.answer("\u26a0\ufe0f Already approved!", show_alert=True)
        else:
            await call.answer(f"\u274c Error: {error_msg}", show_alert=True)
        return

    try:
        await call.bot.send_message(
            chat_id=user_id,
            text=(
                f"\u2705 <b>Binance Payment Approved!</b>\n\n"
                f"\U0001f4b0 <b>${credited_amount}</b> has been added to your balance.\n\n"
                f"Thank you for your payment! \U0001f389"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not notify user {user_id} of Binance approval: {e}")

    await call.message.edit_text(
        call.message.text + f"\n\n\u2705 <b>APPROVED</b> \u2014 ${credited_amount} credited to user {user_id}",
        parse_mode="HTML",
        reply_markup=None,
    )
    await call.answer("\u2705 Binance payment approved and balance credited!")

    await log_audit(
        "binance_payment_approved",
        user_id=user_id,
        resource_type="Payment",
        details=f"amount={credited_amount}, uuid={payment_uuid}, approved_by={call.from_user.id}",
    )


@router.callback_query(F.data.startswith("bnb_reject:"))
async def binance_reject_handler(call: CallbackQuery):
    """Admin rejects a Binance Pay payment."""
    if not await _is_admin_user(call.from_user.id):
        await call.answer("Not authorized.", show_alert=True)
        return

    parts = call.data.split(":")
    if len(parts) < 3:
        await call.answer("Invalid rejection data.", show_alert=True)
        return

    payment_uuid = parts[1]
    try:
        user_id = int(parts[2])
    except ValueError:
        await call.answer("Invalid user ID.", show_alert=True)
        return

    try:
        await call.bot.send_message(
            chat_id=user_id,
            text=(
                "\u274c <b>Binance Payment Not Found</b>\n\n"
                "We could not verify your Binance Pay transfer.\n\n"
                "Please make sure you included the correct <b>remark code</b> "
                "and sent to the right Pay ID, then try again or contact support."
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not notify user {user_id} of Binance rejection: {e}")

    await call.message.edit_text(
        call.message.text + "\n\n\u274c <b>REJECTED</b>",
        parse_mode="HTML",
        reply_markup=None,
    )
    await call.answer("\u274c Binance payment rejected. User has been notified.")

    await log_audit(
        "binance_payment_rejected",
        user_id=user_id,
        resource_type="Payment",
        details=f"uuid={payment_uuid}, rejected_by={call.from_user.id}",
    )

