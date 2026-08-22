from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
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


def _get_auth_middleware():
    from apps.telegram_bot.main import auth_middleware
    return auth_middleware


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
        await call.message.edit_text(
            localize("admin.menu.main"),
            reply_markup=admin_console_keyboard(maintenance_mode=maintenance, role=role),
        )
    else:
        await call.answer(localize("admin.menu.rights"))

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
    await call.message.edit_text(
        localize("admin.menu.main"),
        reply_markup=admin_console_keyboard(maintenance_mode=mw.maintenance_mode, role=role),
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
