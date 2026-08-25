from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from apps.telegram_bot.i18n import localize
from apps.telegram_bot.keyboards import admin_console_keyboard
from packages.database.methods import check_role_cached
from apps.telegram_bot.filters import HasPermissionFilter
from packages.database.models import Permission
from packages.database.methods.audit import log_audit

router = Router()


@router.message(Command("groupid"))
async def groupid_command(message: Message):
    """Send this command inside any group to get its chat ID. Useful for SUPPORT_GROUP_ID config."""
    chat = message.chat
    thread = message.message_thread_id
    text = (
        f"📋 <b>Chat Info</b>\n\n"
        f"🆔 <b>Chat ID:</b> <code>{chat.id}</code>\n"
        f"📌 <b>Type:</b> {chat.type}\n"
        f"📝 <b>Title:</b> {chat.title or 'N/A'}\n"
    )
    if thread:
        text += f"🧵 <b>Thread ID:</b> <code>{thread}</code>\n"
    text += f"\n➡️ Set <code>SUPPORT_GROUP_ID={chat.id}</code> in your .env for Live Support"
    text += f"\n➡️ Set <code>ALERT_GROUP_ID={chat.id}</code> in your .env for General Bot Alerts"

    await message.reply(text, parse_mode="HTML")


from sqlalchemy import select
from packages.database.engine import Database
from packages.database.models.main import BotSettings, Payments, PaymentStatus, ResellerSource, ResellerProduct, Goods

async def _get_auto_delivery_status() -> bool:
    async with Database().session() as s:
        res = (await s.execute(select(BotSettings).where(BotSettings.key == "global_auto_delivery_enabled"))).scalar_one_or_none()
        return True if not res else (res.value.lower() != "false" and res.value != "0")


@router.message(Command("admin"))
async def admin_command_handler(message: Message, state: FSMContext):
    """Direct /admin command for authorized bot administrators."""
    user_id = message.from_user.id
    role = await check_role_cached(user_id)
    if Permission.has_any_admin_perm(role):
        mw = _get_auth_middleware()
        maintenance = mw.maintenance_mode if mw else False
        auto_delivery = await _get_auto_delivery_status()
        await message.answer(
            f"👑 <b>KDS Administrator Console</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <b>Auto-Delivery:</b> {'🟢 ENABLED' if auto_delivery else '🔴 DISABLED'}\n"
            f"🛠 <b>Maintenance Mode:</b> {'🔴 ON' if maintenance else '🟢 OFF'}\n"
            f"👤 <b>Admin:</b> @{message.from_user.username or message.from_user.id}\n\n"
            f"Select an operation below:",
            reply_markup=admin_console_keyboard(maintenance_mode=maintenance, role=role, auto_delivery=auto_delivery),
            parse_mode="HTML"
        )
    else:
        await message.reply("⛔ You do not have administrator permissions for this store.")
    await state.clear()


@router.callback_query(F.data == 'console')
async def console_callback_handler(call: CallbackQuery, state: FSMContext):
    """
    Admin menu (only for admins and above).
    """
    user_id = call.from_user.id
    role = await check_role_cached(user_id)
    if Permission.has_any_admin_perm(role):
        mw = _get_auth_middleware()
        maintenance = mw.maintenance_mode if mw else False
        auto_delivery = await _get_auto_delivery_status()
        await call.message.edit_text(
            f"👑 <b>KDS Administrator Console</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <b>Auto-Delivery:</b> {'🟢 ENABLED' if auto_delivery else '🔴 DISABLED'}\n"
            f"🛠 <b>Maintenance Mode:</b> {'🔴 ON' if maintenance else '🟢 OFF'}\n\n"
            f"Select an administrative action:",
            reply_markup=admin_console_keyboard(maintenance_mode=maintenance, role=role, auto_delivery=auto_delivery),
            parse_mode="HTML"
        )
    else:
        await call.answer(localize("admin.menu.rights"))

    await state.clear()


@router.callback_query(F.data == 'toggle_auto_delivery', HasPermissionFilter(permission=Permission.SETTINGS_MANAGE))
async def toggle_auto_delivery_handler(call: CallbackQuery):
    """Toggle global auto-delivery on/off from Telegram bot with 1 tap."""
    async with Database().session() as s:
        res = (await s.execute(select(BotSettings).where(BotSettings.key == "global_auto_delivery_enabled"))).scalar_one_or_none()
        current_val = True if not res else (res.value.lower() != "false" and res.value != "0")
        new_val = not current_val
        if res:
            res.value = "true" if new_val else "false"
        else:
            s.add(BotSettings(key="global_auto_delivery_enabled", value="true" if new_val else "false"))
        await s.commit()

    status_msg = "⚡ Auto-Delivery ENABLED! (Orders will auto-purchase from API & email customers)" if new_val else "⏸️ Auto-Delivery DISABLED (Orders will queue for manual approval)"
    await call.answer(status_msg, show_alert=True)

    mw = _get_auth_middleware()
    maintenance = mw.maintenance_mode if mw else False
    role = await check_role_cached(call.from_user.id)
    await call.message.edit_text(
        f"👑 <b>KDS Administrator Console</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>Auto-Delivery:</b> {'🟢 ENABLED' if new_val else '🔴 DISABLED'}\n"
        f"🛠 <b>Maintenance Mode:</b> {'🔴 ON' if maintenance else '🟢 OFF'}\n\n"
        f"Select an administrative action:",
        reply_markup=admin_console_keyboard(maintenance_mode=maintenance, role=role, auto_delivery=new_val),
        parse_mode="HTML"
    )


@router.callback_query(F.data == 'adm_budget_view', HasPermissionFilter(permission=Permission.STATS_VIEW))
async def admin_budget_view_handler(call: CallbackQuery):
    """Query live balances of all external provider APIs."""
    await call.answer("Querying live provider APIs...", show_alert=False)
    from packages.services.reseller.sync import get_reseller_balances
    
    balances = await get_reseller_balances()
    lines = []
    total_usd = 0.0
    for b in balances:
        name = b.get("provider", "").upper()
        active = b.get("active", False)
        status = b.get("status", "unknown")
        bal = b.get("balance_usd")
        if bal is not None:
            total_usd += float(bal)
            lines.append(f"• <b>{name}</b>: <code>${float(bal):,.2f} USD</code> ({status})")
        else:
            lines.append(f"• <b>{name}</b>: <i>{status}</i> {'🟢' if active else '🔴'}")

    msg = (
        f"💰 <b>RESELLER APIS BUDGET & BALANCES</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 <b>Total Active Float:</b> <code>${total_usd:,.2f} USD</code> (≈ NPR {int(total_usd * 135):,})\n\n"
        + "\n".join(lines) +
        f"\n\n⏱ <i>Live Sync Time: {call.message.date.strftime('%H:%M:%S')}</i>"
    )

    from apps.telegram_bot.keyboards.inline import simple_buttons
    await call.message.edit_text(msg, parse_mode="HTML", reply_markup=simple_buttons([
        ("🔄 Refresh Balances", "adm_budget_view"),
        ("⬅️ Back to Console", "console")
    ]))


@router.callback_query(F.data == 'adm_pending_orders', HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_pending_orders_handler(call: CallbackQuery):
    """List pending QR payments and manual fulfillment items with 1-tap actions."""
    async with Database().session() as s:
        res = (await s.execute(
            select(Payments)
            .where(Payments.status == PaymentStatus.PENDING)
            .order_by(Payments.id.desc())
            .limit(10)
        )).scalars().all()

    if not res:
        from apps.telegram_bot.keyboards.inline import simple_buttons
        await call.message.edit_text(
            "✅ <b>No Pending Orders!</b>\n\nAll orders and Nepal QR payments have been fulfilled and processed.",
            parse_mode="HTML",
            reply_markup=simple_buttons([("⬅️ Back to Console", "console")])
        )
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    text_lines = ["📋 <b>PENDING WEB & NEPAL ORDERS</b>\n━━━━━━━━━━━━━━━━━━━━"]

    for pmt in res:
        safe_tx = pmt.external_id[:16]
        text_lines.append(
            f"🆔 <b>Order #{pmt.id}</b> | <code>${float(pmt.amount):.2f}</code> | {pmt.provider}\n"
            f"Ref: <code>{safe_tx}</code> | User: <code>{pmt.user_id or 'Guest'}</code>\n"
        )
        kb.button(text=f"⚡ Auto-Approve #{pmt.id}", callback_data=f"adm_appr_pmt_{pmt.id}")

    kb.button(text="⬅️ Back to Console", callback_data="console")
    kb.adjust(1)

    await call.message.edit_text("\n".join(text_lines), parse_mode="HTML", reply_markup=kb.as_markup())


@router.callback_query(F.data == 'adm_toggle_nepal_cs', HasPermissionFilter(permission=Permission.SETTINGS_MANAGE))
async def admin_toggle_nepal_cs_handler(call: CallbackQuery):
    """Toggle Nepal Store Coming Soon banner."""
    async with Database().session() as s:
        res = (await s.execute(select(BotSettings).where(BotSettings.key == "nepal_coming_soon"))).scalar_one_or_none()
        current_cs = True if not res else (res.value.lower() == "true")
        new_cs = not current_cs
        if res:
            res.value = "true" if new_cs else "false"
        else:
            s.add(BotSettings(key="nepal_coming_soon", value="true" if new_cs else "false"))
        await s.commit()

    alert_text = "🇳🇵 Nepal Coming Soon Banner ENABLED" if new_cs else "🇳🇵 Nepal Store is now LIVE (Coming Soon Banner HIDDEN)"
    await call.answer(alert_text, show_alert=True)


class AdminEditTemplate(StatesGroup):
    waiting_for_template = State()


@router.callback_query(F.data == 'adm_delivery_tpl', HasPermissionFilter(permission=Permission.SETTINGS_MANAGE))
async def admin_delivery_tpl_view(call: CallbackQuery, state: FSMContext):
    """View and edit global email & message delivery template."""
    async with Database().session() as s:
        res = (await s.execute(select(BotSettings).where(BotSettings.key == "global_delivery_template"))).scalar_one_or_none()
        current_tpl = res.value if res else (
            "Hello {customer_email},\n\n"
            "Thank you for your order! Here are your digital credentials:\n\n"
            "{credentials}\n\n"
            "Product: {product_name} (x{quantity})\n"
            "Warranty: {warranty}\n"
            "Support Contact: {support_contact}"
        )

    msg = (
        f"✉️ <b>GLOBAL DELIVERY MESSAGE TEMPLATE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Available placeholders:\n"
        f"<code>{{customer_email}}</code>, <code>{{product_name}}</code>, <code>{{quantity}}</code>, <code>{{credentials}}</code>, <code>{{warranty}}</code>, <code>{{support_contact}}</code>\n\n"
        f"<b>Current Template:</b>\n"
        f"<pre>{current_tpl}</pre>"
    )

    from apps.telegram_bot.keyboards.inline import simple_buttons
    await call.message.edit_text(
        msg,
        parse_mode="HTML",
        reply_markup=simple_buttons([
            ("✏️ Edit Template", "adm_edit_tpl_start"),
            ("⬅️ Back to Console", "console")
        ])
    )


@router.callback_query(F.data == 'adm_edit_tpl_start', HasPermissionFilter(permission=Permission.SETTINGS_MANAGE))
async def admin_edit_tpl_start(call: CallbackQuery, state: FSMContext):
    from apps.telegram_bot.keyboards.inline import simple_buttons
    await call.message.edit_text(
        "Send the new Delivery Template text with placeholders (e.g. <code>{credentials}</code>, <code>{product_name}</code>):",
        parse_mode="HTML",
        reply_markup=simple_buttons([("⬅️ Cancel", "console")])
    )
    await state.set_state(AdminEditTemplate.waiting_for_template)


@router.message(AdminEditTemplate.waiting_for_template, F.text)
async def admin_edit_tpl_finish(message: Message, state: FSMContext):
    new_tpl = message.text.strip()
    async with Database().session() as s:
        res = (await s.execute(select(BotSettings).where(BotSettings.key == "global_delivery_template"))).scalar_one_or_none()
        if res:
            res.value = new_tpl
        else:
            s.add(BotSettings(key="global_delivery_template", value=new_tpl))
        await s.commit()

    from apps.telegram_bot.keyboards.inline import simple_buttons
    await message.answer("✅ Global delivery template updated successfully!", reply_markup=simple_buttons([("🏛️ Admin Console", "console")]))
    await state.clear()


@router.callback_query(F.data == 'toggle_maintenance', HasPermissionFilter(permission=Permission.SETTINGS_MANAGE))
async def toggle_maintenance_handler(call: CallbackQuery):
    """
    Toggle maintenance mode on/off.
    """
    mw = _get_auth_middleware()
    if not mw:
        return

    mw.maintenance_mode = not mw.maintenance_mode
    state_str = "ON" if mw.maintenance_mode else "OFF"
    await log_audit(
        "toggle_maintenance",
        user_id=call.from_user.id,
        details=f"admin={call.from_user.username}, state={state_str}",
    )

    if mw.maintenance_mode:
        await call.answer(localize("admin.maintenance.enabled"), show_alert=True)
    else:
        await call.answer(localize("admin.maintenance.disabled"), show_alert=True)

    role = await check_role_cached(call.from_user.id)
    auto_delivery = await _get_auto_delivery_status()
    await call.message.edit_text(
        f"👑 <b>KDS Administrator Console</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>Auto-Delivery:</b> {'🟢 ENABLED' if auto_delivery else '🔴 DISABLED'}\n"
        f"🛠 <b>Maintenance Mode:</b> {'🔴 ON' if mw.maintenance_mode else '🟢 OFF'}\n\n"
        f"Select an administrative action:",
        reply_markup=admin_console_keyboard(maintenance_mode=mw.maintenance_mode, role=role, auto_delivery=auto_delivery),
        parse_mode="HTML"
    )

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from apps.telegram_bot.keyboards.inline import simple_buttons
import aiogram

class AdminEditDesc(StatesGroup):
    waiting_for_desc = State()

@router.callback_query(F.data == 'edit_bot_desc', HasPermissionFilter(permission=Permission.SETTINGS_MANAGE))
async def edit_bot_desc_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Send the new description for the bot (this is the text shown before the user clicks 'Start' on the bot profile):", reply_markup=simple_buttons([("⬅️ Back", "console")]))
    await state.set_state(AdminEditDesc.waiting_for_desc)

@router.message(AdminEditDesc.waiting_for_desc, F.text)
async def edit_bot_desc_finish(message: Message, state: FSMContext, bot: aiogram.Bot):
    try:
        await bot.set_my_description(description=message.text)
        await message.answer("✅ Bot description updated successfully!", reply_markup=simple_buttons([("🏛️ Admin Console", "console")]))
    except Exception as e:
        await message.answer(f"❌ Failed to update description: {e}", reply_markup=simple_buttons([("🏛️ Admin Console", "console")]))
    await state.clear()

