from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from packages.database.engine import Database
from packages.database.models import User
from sqlalchemy import update, select
import bcrypt

router = Router()


class WebAuthStates(StatesGroup):
    waiting_for_new_password    = State()
    waiting_for_change_password = State()


# ─── Helper: build the web-login menu keyboard ────────────────────────────────

def web_login_keyboard(has_password: bool):
    kb = InlineKeyboardBuilder()
    if has_password:
        kb.button(text="🔑 Change Password",  callback_data="web_change_password")
    else:
        kb.button(text="🔐 Set Password",     callback_data="web_set_password")
    kb.button(text="🏠 Back to Menu", callback_data="back_to_menu")
    kb.adjust(1)
    return kb.as_markup()


# ─── Entry point: show the Web Login menu ─────────────────────────────────────

@router.callback_query(F.data == "web_login")
async def show_web_login_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()

    user_id = call.from_user.id
    async with Database().session() as s:
        result = await s.execute(select(User).where(User.telegram_id == user_id))
        user = result.scalars().first()

    has_password = bool(user and user.password_hash)
    password_status = "✅ Password is set" if has_password else "❌ No password set yet"

    text = (
        "🌐 <b>Website Login</b>\n\n"
        f"Your <b>Telegram User ID</b>:\n"
        f"<code>{user_id}</code>\n\n"
        f"<i>(Tap the ID above to copy it)</i>\n\n"
        f"Password status: {password_status}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Use your Telegram User ID + password on the website's "
        "<b>🤖 Telegram Login</b> tab to access your wallet."
    )

    await call.message.edit_text(text, reply_markup=web_login_keyboard(has_password), parse_mode="HTML")


# ─── Set Password (first time) ────────────────────────────────────────────────

@router.callback_query(F.data == "web_set_password")
async def prompt_set_password(call: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Cancel", callback_data="web_login")
    await call.message.edit_text(
        "🔐 <b>Set a Website Password</b>\n\n"
        "Send me the password you want to use on the website.\n\n"
        "<i>⚠️ Minimum 6 characters. Your message will be deleted immediately for security.</i>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(WebAuthStates.waiting_for_new_password)


@router.message(WebAuthStates.waiting_for_new_password, F.text)
async def save_new_password(message: Message, state: FSMContext):
    password = message.text.strip()

    # Delete the password message immediately for security
    try:
        await message.delete()
    except Exception:
        pass

    if len(password) < 6:
        kb = InlineKeyboardBuilder()
        kb.button(text="↩️ Try Again", callback_data="web_set_password")
        kb.button(text="🏠 Back to Menu", callback_data="back_to_menu")
        kb.adjust(1)
        await message.answer(
            "⚠️ Password must be at least <b>6 characters</b>. Please try again.",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
        await state.clear()
        return

    # Hash and save
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    async with Database().session() as s:
        await s.execute(
            update(User)
            .where(User.telegram_id == message.from_user.id)
            .values(password_hash=hashed)
        )
        await s.commit()

    await state.clear()

    kb = InlineKeyboardBuilder()
    kb.button(text="🌐 Back to Web Login", callback_data="web_login")
    kb.button(text="🏠 Main Menu",         callback_data="back_to_menu")
    kb.adjust(1)

    await message.answer(
        "✅ <b>Password set successfully!</b>\n\n"
        f"You can now log into the website using:\n"
        f"• <b>Telegram User ID:</b> <code>{message.from_user.id}</code>\n"
        f"• <b>Password:</b> the one you just set\n\n"
        f"Go to the website → <b>🤖 Telegram Login</b> tab.",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


# ─── Change Password ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "web_change_password")
async def prompt_change_password(call: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Cancel", callback_data="web_login")
    await call.message.edit_text(
        "🔑 <b>Change Website Password</b>\n\n"
        "Send me your <b>new password</b>.\n\n"
        "<i>⚠️ Minimum 6 characters. Your message will be deleted immediately for security.</i>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(WebAuthStates.waiting_for_change_password)


@router.message(WebAuthStates.waiting_for_change_password, F.text)
async def save_changed_password(message: Message, state: FSMContext):
    password = message.text.strip()

    # Delete the password message immediately for security
    try:
        await message.delete()
    except Exception:
        pass

    if len(password) < 6:
        kb = InlineKeyboardBuilder()
        kb.button(text="↩️ Try Again", callback_data="web_change_password")
        kb.button(text="🏠 Back to Menu", callback_data="back_to_menu")
        kb.adjust(1)
        await message.answer(
            "⚠️ Password must be at least <b>6 characters</b>. Please try again.",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
        await state.clear()
        return

    # Hash and save
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    async with Database().session() as s:
        await s.execute(
            update(User)
            .where(User.telegram_id == message.from_user.id)
            .values(password_hash=hashed)
        )
        await s.commit()

    await state.clear()

    kb = InlineKeyboardBuilder()
    kb.button(text="🌐 Back to Web Login", callback_data="web_login")
    kb.button(text="🏠 Main Menu",         callback_data="back_to_menu")
    kb.adjust(1)

    await message.answer(
        "✅ <b>Password changed successfully!</b>\n\n"
        "Your new password is now active for website login.",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
