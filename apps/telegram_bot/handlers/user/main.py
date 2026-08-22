from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.enums.chat_type import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import datetime
import html
from decimal import Decimal

from packages.database.methods import (
    select_max_role_id, create_user, check_role, check_user,
    select_user_operations, select_user_items, check_user_cached,
    reset_account_discount, credit_signup_referral_bonus,
)
from packages.database.methods.audit import log_audit
from packages.database.methods.read import get_cart_count
from packages.database.methods.lazy_queries import query_user_operations_history
from apps.telegram_bot.handlers.other import check_sub_channel, _parse_channel_username
from apps.telegram_bot.keyboards import main_menu, back, profile_keyboard, check_sub
from apps.telegram_bot.keyboards.inline import simple_buttons
from packages.config.config import EnvKeys
from apps.telegram_bot.core.metrics import get_metrics
from apps.telegram_bot.i18n import localize
from apps.telegram_bot.core.logging import logger
from apps.telegram_bot.utils.notify import notify_group

router = Router()


def _build_welcome_text(first_name: str, balance: float, icons: dict | None = None) -> str:
    from apps.telegram_bot.utils.menu_icons import format_icon_html
    safe_name = html.escape(first_name or "there")
    welcome_icon = format_icon_html("welcome_header", "🔥", icons)
    balance_icon = format_icon_html("welcome_balance", "💵", icons)
    return (
        f"{welcome_icon} <b>Welcome, {safe_name} to KALI DIGITAL STORE!</b>\n\n"
        f"{balance_icon} <b>Your balance: ${balance:.2f}</b>"
    )


@router.message(F.text.startswith('/start'))
async def start(message: Message, state: FSMContext):
    """
    Handle /start:
    - Ensure user exists (register if new)
    - (Optional) Check channel subscription
    - Show the main menu
    """
    if message.chat.type != ChatType.PRIVATE:
        return

    user_id = message.from_user.id
    await state.clear()

    owner_max_role = await select_max_role_id()
    raw_arg = message.text[7:].strip() if len(message.text) > 7 else ""

    # ── GGBuilder-style Web Login Challenge Deep Link ────────────────────────
    if raw_arg.startswith("login_"):
        code_or_token = raw_arg[6:].strip()
        from packages.services.challenge_auth import get_challenge
        challenge = get_challenge(code_or_token)
        if challenge and challenge.get("status") == "waiting":
            code = challenge.get("code", code_or_token)
            kb = simple_buttons([
                ("✅ Confirm Login", f"confirm_login_ch:{code_or_token}"),
                ("❌ Deny", f"deny_login_ch:{code_or_token}"),
            ])
            await message.answer(
                f"🔐 <b>Web Login Confirmation</b>\n\n"
                f"A web browser is requesting access to your account.\n\n"
                f"Verification Code: <code>{code}</code>\n\n"
                f"Tap <b>Confirm Login</b> below to approve instant sign-in.",
                parse_mode="HTML",
                reply_markup=kb,
            )
            return
        elif challenge and challenge.get("status") == "approved":
            await message.answer("✅ This login request has already been approved.", parse_mode="HTML")
            return
        else:
            await message.answer("⚠️ This login request has expired or is invalid. Please request a new code on the website.", parse_mode="HTML")
            return

    referral_id = int(raw_arg) if raw_arg.isdigit() and raw_arg != str(user_id) else None
    user_role = owner_max_role if user_id == EnvKeys.OWNER_ID else 1

    # registration_date is DateTime
    is_new_user, valid_referrer_id = await create_user(
        telegram_id=int(user_id),
        registration_date=datetime.datetime.now(datetime.timezone.utc),
        referral_id=referral_id,
        role=user_role
    )

    if is_new_user:
        metrics = get_metrics()
        if metrics:
            metrics.track_event("registration", user_id)

        if valid_referrer_id:
            try:
                bonus = Decimal(str(EnvKeys.REFERRAL_SIGNUP_BONUS or "0"))
            except Exception:
                bonus = Decimal("0")
            if bonus > 0:
                credited = await credit_signup_referral_bonus(
                    referrer_id=valid_referrer_id,
                    referral_id=int(user_id),
                    bonus=bonus,
                )
                if credited:
                    await log_audit(
                        "referral_signup_bonus",
                        user_id=valid_referrer_id,
                        resource_type="User",
                        resource_id=str(user_id),
                        details=f"bonus={bonus}",
                    )
                    try:
                        await message.bot.send_message(
                            chat_id=valid_referrer_id,
                            text=(
                                f"🎉 <b>New referral joined!</b>\n\n"
                                f"💰 <b>+{bonus:g} USDT</b> credited to your balance.\n"
                                f"Keep sharing your link to earn more."
                            ),
                            parse_mode="HTML",
                        )
                    except (TelegramBadRequest, TelegramForbiddenError) as e:
                        logger.warning(f"Failed to notify referrer {valid_referrer_id}: {e}")

    channel_username = _parse_channel_username()
    role_data = await check_role(user_id)

    # Optional subscription check
    try:
        if channel_username:
            chat_id = int(EnvKeys.CHANNEL_ID) if EnvKeys.CHANNEL_ID else f"@{channel_username}"
            chat_member = await message.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if not await check_sub_channel(chat_member):
                markup = check_sub(channel_username)
                await message.answer(localize("subscribe.prompt"), reply_markup=markup)
                await message.delete()
                return
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.warning(f"Channel subscription check failed for user {user_id}: {e}")

    # Deep-link: /start item_ProductName → open product page directly
    start_param = message.text[7:] if len(message.text) > 7 else ""
    if start_param.startswith("item_"):
        item_name = start_param[5:].replace("_", " ")
        from packages.database.methods import get_item_info_cached
        item = await get_item_info_cached(item_name)
        if item:
            await state.update_data(csrf_item=item_name)
            from apps.telegram_bot.handlers.user.shop_and_goods import _render_item_page
            try:
                await message.delete()
            except Exception:
                pass
            await _render_item_page(message, state, item_name, back_data="back_to_menu")
            return

    user_info = await check_user(user_id) or {}
    balance = float(user_info.get('balance', 0))
    first_name = message.from_user.first_name or "there"

    from apps.telegram_bot.utils.menu_icons import get_menu_icons
    icons = await get_menu_icons()
    welcome_text = _build_welcome_text(first_name, balance, icons)

    markup = await main_menu(role=role_data, channel=channel_username, helper=EnvKeys.HELPER_ID)
    await message.answer(
        welcome_text, 
        reply_markup=markup, 
        parse_mode="HTML",
        message_effect_id="5046509860389126442" # 🎉 Confetti effect
    )
    await message.delete()
    await state.clear()

    if is_new_user:
        # Notify alert group about new user
        try:
            from apps.telegram_bot.utils.notify import notify_group
            username = message.from_user.username
            user_link = f"@{username}" if username else f"<a href='tg://user?id={user_id}'>{first_name}</a>"
            alert_msg = (
                f"👤 <b>New User Registered!</b>\n\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"👤 Name: {first_name}\n"
                f"🔗 User: {user_link}"
            )
            await notify_group(message.bot, alert_msg)
        except Exception as e:
            logger.error(f"Failed to send new user notification: {e}")

        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            review_kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="👍", callback_data="shop_review_up"),
                    InlineKeyboardButton(text="👎", callback_data="shop_review_down")
                ]
            ])
            await message.answer("Did you enjoy shopping in our bot?", reply_markup=review_kb)
        except Exception:
            pass


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_callback_handler(call: CallbackQuery, state: FSMContext):
    """
    Return user to the main menu.
    """
    user_id = call.from_user.id
    user = await check_user_cached(user_id)
    if not user:
        await create_user(
            telegram_id=user_id,
            registration_date=datetime.datetime.now(datetime.timezone.utc),
            referral_id=None,
            role=1,
        )
        user = await check_user_cached(user_id)

    role_id = user.get('role_id')
    balance = float(user.get('balance', 0))
    channel_username = _parse_channel_username()

    first_name = call.from_user.first_name or "there"
    from apps.telegram_bot.utils.menu_icons import get_menu_icons
    icons = await get_menu_icons()
    welcome_text = _build_welcome_text(first_name, balance, icons)

    markup = await main_menu(role=role_id, channel=channel_username, helper=EnvKeys.HELPER_ID)
    try:
        await call.message.edit_text(welcome_text, reply_markup=markup, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await state.clear()


@router.callback_query(F.data == "rules")
async def rules_callback_handler(call: CallbackQuery, state: FSMContext):
    """
    Show rules text if provided in ENV.
    """
    rules_data = EnvKeys.RULES
    if rules_data:
        await call.message.edit_text(rules_data, reply_markup=back("back_to_menu"))
    else:
        await call.answer(localize("rules.not_set"))
    await state.clear()


@router.callback_query(F.data == "profile")
async def profile_callback_handler(call: CallbackQuery, state: FSMContext):
    """
    Send profile info (balance, purchases count, id, etc.).
    """
    user_id = call.from_user.id
    tg_user = call.from_user
    user_info = await check_user_cached(user_id)

    balance = user_info.get('balance')
    discount_pct = float(user_info.get('discount_percent') or 0)
    operations = await select_user_operations(user_id)
    overall_balance = sum(operations) if operations else 0
    items = await select_user_items(user_id)
    referral = EnvKeys.REFERRAL_PERCENT
    cart_count = await get_cart_count(user_id)

    markup = profile_keyboard(referral, items, cart_count=cart_count, discount_percent=discount_pct)
    disc_line = f"\n🏷 Account discount: <b>{discount_pct}% off all purchases</b>" if discount_pct > 0 else ""
    text = (
        f"{localize('profile.caption', name=tg_user.first_name, id=user_id)}\n"
        f"{localize('profile.id', id=user_id)}\n"
        f"{localize('profile.balance', amount=balance, currency=EnvKeys.PAY_CURRENCY)}\n"
        f"{localize('profile.total_topup', amount=overall_balance, currency=EnvKeys.PAY_CURRENCY)}\n"
        f"{localize('profile.purchased_count', count=items)}"
        f"{disc_line}"
    )
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode='HTML')
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await state.clear()


@router.callback_query(F.data == "remove_account_discount")
async def remove_account_discount_handler(call: CallbackQuery, state: FSMContext):
    """Show confirmation before clearing the user's account discount."""
    buttons = [
        ("Yes, remove discount", "remove_discount_confirm"),
        ("Cancel", "profile"),
    ]
    await call.message.edit_text(
        "<b>Remove Account Discount</b>\n\n"
        "This will clear your active % discount. You'll need to redeem a new promo code to get it back.\n\n"
        "Are you sure?",
        parse_mode="HTML",
        reply_markup=simple_buttons(buttons),
    )


@router.callback_query(F.data == "remove_discount_confirm")
async def remove_discount_confirmed_handler(call: CallbackQuery, state: FSMContext):
    """Clear the user's account discount and return to profile."""
    success = await reset_account_discount(call.from_user.id)
    if success:
        await call.answer("Discount removed.", show_alert=False)
        await log_audit(
            "account_discount_removed",
            user_id=call.from_user.id,
            resource_type="User",
            resource_id=str(call.from_user.id),
        )
    else:
        await call.answer("Could not remove discount.", show_alert=True)
    # Redirect back to profile
    await profile_callback_handler(call, state)


@router.callback_query(F.data == "sub_channel_done")
async def check_sub_to_channel(call: CallbackQuery, state: FSMContext):
    """
    Re-check channel subscription after user clicks "Check".
    """
    user_id = call.from_user.id
    channel_username = _parse_channel_username()
    helper = EnvKeys.HELPER_ID

    if channel_username:
        chat_id = int(EnvKeys.CHANNEL_ID) if EnvKeys.CHANNEL_ID else f"@{channel_username}"
        chat_member = await call.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        if await check_sub_channel(chat_member):
            user = await check_user_cached(user_id)
            role_id = user.get('role_id')
            markup = await main_menu(role_id, channel_username, helper)
            await call.message.edit_text(localize("menu.title"), reply_markup=markup)
            await state.clear()
            return

    await call.answer(localize("errors.not_subscribed"))


# --- Operation History ---

@router.callback_query(F.data == "operation_history")
async def operation_history_handler(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    await _show_operations_page(call, state, user_id, 0)


@router.callback_query(F.data.startswith("ops-page_"))
async def navigate_operations(call: CallbackQuery, state: FSMContext):
    page = int(call.data.split("_")[1])
    await _show_operations_page(call, state, call.from_user.id, page)


async def _show_operations_page(call: CallbackQuery, state: FSMContext, user_id: int, page: int):
    from functools import partial
    from apps.telegram_bot.utils.paginator import LazyPaginator

    paginator = LazyPaginator(partial(query_user_operations_history, user_id), per_page=10)
    items = await paginator.get_page(page)
    total_pages = await paginator.get_total_pages()

    if not items:
        await call.message.edit_text(
            localize("history.title") + "\n\n" + localize("history.empty"),
            reply_markup=back("profile"),
        )
        return

    lines = [localize("history.title"), ""]
    for op in items:
        op_type = op['type']
        amount = op['amount']
        date = op['date']
        date_str = str(date)[:19] if date else ""

        if op_type == 'topup':
            lines.append(localize("history.topup", amount=amount, currency=EnvKeys.PAY_CURRENCY))
        elif op_type == 'purchase':
            lines.append(localize("history.purchase", amount=amount, currency=EnvKeys.PAY_CURRENCY))
        elif op_type == 'referral':
            lines.append(localize("history.referral", amount=amount, currency=EnvKeys.PAY_CURRENCY))
        lines.append(localize("history.date", date=date_str))
        lines.append("")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    kb = InlineKeyboardBuilder()
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"ops-page_{page - 1}"))
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"ops-page_{page + 1}"))
    if nav_buttons:
        kb.row(*nav_buttons)
    kb.row(InlineKeyboardButton(text=localize("btn.back"), callback_data="profile"))

    await call.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())




@router.callback_query(F.data == "user_sync_now")
async def user_sync_now_handler(call: CallbackQuery):
    await call.answer("🔄 Syncing with APIs... please wait.", show_alert=True)
    from packages.services.reseller import sync_all_sources
    from apps.telegram_bot.utils.notify import notify_group
    import logging
    try:
        results = await sync_all_sources()
        new_products = []
        for src, res in results.items():
            if res and "new_products" in res and res["new_products"]:
                new_products.extend(res["new_products"])
                
        if new_products:
            lines = [f"📦 <b>{p['name']}</b> - ${p['price']}" for p in new_products]
            msg = "🎉 <b>New Products Arrived!</b>\n\n" + "\n".join(lines) + "\n\n<i>Check them out in the shop!</i>"
            await notify_group(call.bot, msg)
            from apps.telegram_bot.utils.notify import broadcast_to_all_users
            await broadcast_to_all_users(call.bot, msg)
            
        added_stock = []
        for src, res in results.items():
            if res and "added_stock" in res and res["added_stock"]:
                added_stock.extend(res["added_stock"])
                
        if added_stock:
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            from apps.telegram_bot.utils.menu_icons import get_menu_icons, format_icon_html
            icons = await get_menu_icons()
            header_icon = format_icon_html("notify_header", "💥", icons)
            added_icon = format_icon_html("notify_added", "➕", icons)
            stock_icon = format_icon_html("notify_stock", "📦", icons)
            price_icon = format_icon_html("notify_price", "💸", icons)
            buy_custom_id = icons.get("notify_buy_btn")

            me = await call.bot.get_me()
            for p in added_stock:
                kb = InlineKeyboardBuilder()
                safe_name = p['name'].replace(' ', '_')[:50]
                if buy_custom_id:
                    kb.button(
                        text="Buy now",
                        url=f"https://t.me/{me.username}?start=item_{safe_name}",
                        icon_custom_emoji_id=str(buy_custom_id)
                    )
                else:
                    kb.button(
                        text="🛒 Buy now",
                        url=f"https://t.me/{me.username}?start=item_{safe_name}"
                    )
                
                msg = (
                    f"{header_icon} <b>{p['name']}</b>\n"
                    f"{added_icon} Added: {p['added']}\n"
                    f"{stock_icon} Current stock: {p['current_stock']}\n"
                    f"{price_icon} Price: ${p['price']:.2f}"
                )
                await notify_group(call.bot, msg, reply_markup=kb.as_markup())
                
                from apps.telegram_bot.utils.notify import broadcast_to_all_users
                await broadcast_to_all_users(call.bot, msg, reply_markup=kb.as_markup())
            
        await call.message.answer("✅ Sync completed successfully!")
    except Exception as e:
        logging.error(f"Error in user sync: {e}")
        await call.message.answer("❌ Sync failed. Please try again later.")


# ─────────────────────────────────────────────────────────────────────────────
# Web Login Challenge Callbacks
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("confirm_login_ch:"))
async def confirm_login_challenge_callback(call: CallbackQuery):
    code_or_token = call.data.split(":", 1)[1]
    from packages.services.challenge_auth import approve_challenge
    success = approve_challenge(code_or_token, call.from_user.id)
    if success:
        await call.message.edit_text(
            "✅ <b>Login Approved!</b>\n\n"
            "You are now logged in on your web browser. Your page will redirect automatically.",
            parse_mode="HTML",
        )
    else:
        await call.message.edit_text(
            "⚠️ <b>Login Request Expired</b>\n\n"
            "This request has expired or is no longer valid. Please start a new login on the website.",
            parse_mode="HTML",
        )
    await call.answer()


@router.callback_query(F.data.startswith("deny_login_ch:"))
async def deny_login_challenge_callback(call: CallbackQuery):
    code_or_token = call.data.split(":", 1)[1]
    from packages.services.challenge_auth import deny_challenge
    deny_challenge(code_or_token)
    await call.message.edit_text(
        "❌ <b>Login Request Denied</b>\n\n"
        "Access has been denied for this web session.",
        parse_mode="HTML",
    )
    await call.answer()
