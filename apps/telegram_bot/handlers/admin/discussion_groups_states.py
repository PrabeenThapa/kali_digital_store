import html
import re
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.telegram_bot.filters import HasPermissionFilter
from packages.database.models.main import Permission
from apps.telegram_bot.utils.discussion_groups import (
    get_discussion_config, set_broadcaster_enabled, set_broadcaster_interval,
    update_auto_message, add_discussion_group, toggle_discussion_group,
    delete_discussion_group
)

router = Router()

class DiscussionGroupFSM(StatesGroup):
    waiting_for_group_link = State()
    waiting_for_message_text = State()
    waiting_for_interval = State()


@router.callback_query(F.data == "manage_discussion_groups", HasPermissionFilter(permission=Permission.BROADCAST))
async def manage_discussion_groups_handler(call: CallbackQuery, state: FSMContext):
    """Main dashboard for auto-posting to discussion groups."""
    await state.clear()
    config = await get_discussion_config()
    
    is_enabled = config.get("is_enabled", False)
    interval = config.get("interval_minutes", 1)
    groups = config.get("groups", [])
    active_count = sum(1 for g in groups if g.get("enabled", True))
    total_count = len(groups)
    
    status_str = "🟢 Active (Auto-Posting)" if is_enabled else "🔴 Disabled"
    
    kb = InlineKeyboardBuilder()
    
    # Toggle Broadcaster Button
    toggle_text = "🔴 Turn OFF Broadcaster" if is_enabled else "🟢 Turn ON Broadcaster"
    kb.row(InlineKeyboardButton(text=toggle_text, callback_data="dg_toggle_broadcaster"))
    
    # Add Group & List Groups
    kb.row(
        InlineKeyboardButton(text="➕ Add Group Link", callback_data="dg_add_group"),
        InlineKeyboardButton(text=f"📋 Manage Groups ({active_count}/{total_count})", callback_data="dg_list_groups")
    )
    
    # Edit Message & Interval
    kb.row(
        InlineKeyboardButton(text="📝 Edit Message Text", callback_data="dg_edit_message"),
        InlineKeyboardButton(text=f"⏱ Interval ({interval}m)", callback_data="dg_edit_interval")
    )
    
    # Test Send Now
    kb.row(InlineKeyboardButton(text="🚀 Send Test Post Now", callback_data="dg_test_send"))
    
    # Back to Console
    kb.row(InlineKeyboardButton(text="⬅️ Back to Console", callback_data="console"))
    
    msg_preview = config.get("auto_message_text", "")
    if len(msg_preview) > 200:
        msg_preview = msg_preview[:197] + "..."
        
    await call.message.edit_text(
        f"📢 <b>Auto-Post to Discussion Groups</b>\n\n"
        f"Status: <b>{status_str}</b>\n"
        f"Post Interval: <b>Every {interval} minute(s)</b>\n"
        f"Active Groups: <b>{active_count} of {total_count} enabled</b>\n\n"
        f"<b>Current Auto-Message Preview:</b>\n"
        f"----------------------------------------\n"
        f"{msg_preview}\n"
        f"----------------------------------------\n\n"
        f"Use the buttons below to manage groups, message content, and post schedule:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "dg_toggle_broadcaster", HasPermissionFilter(permission=Permission.BROADCAST))
async def dg_toggle_broadcaster_handler(call: CallbackQuery, state: FSMContext):
    config = await get_discussion_config()
    new_state = not config.get("is_enabled", False)
    await set_broadcaster_enabled(new_state)
    
    status_label = "enabled 🟢" if new_state else "disabled 🔴"
    await call.answer(f"Auto-broadcaster is now {status_label}!", show_alert=True)
    await manage_discussion_groups_handler(call, state)


@router.callback_query(F.data == "dg_add_group", HasPermissionFilter(permission=Permission.BROADCAST))
async def dg_add_group_prompt(call: CallbackQuery, state: FSMContext):
    await state.set_state(DiscussionGroupFSM.waiting_for_group_link)
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="❌ Cancel", callback_data="manage_discussion_groups"))
    
    await call.message.edit_text(
        "➕ <b>Add New Discussion Group</b>\n\n"
        "Please send the Telegram group link or username.\n\n"
        "<b>Supported formats:</b>\n"
        "• <code>https://t.me/your_group_name</code>\n"
        "• <code>@your_group_name</code>\n"
        "• Chat ID: <code>-100XXXXXXXXXX</code>\n\n"
        "<i>Make sure the bot has been added as a member to the group!</i>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.message(DiscussionGroupFSM.waiting_for_group_link)
async def dg_receive_group_link(message: Message, state: FSMContext):
    input_text = (message.text or "").strip()
    
    # Extract username or chat ID from link / text
    target = input_text
    match = re.search(r"t\.me/([a-zA-Z0-9_]+)", input_text)
    if match:
        target = "@" + match.group(1)
    elif not target.startswith("@") and not target.startswith("-100") and not target.lstrip("-").isdigit():
        target = "@" + target.lstrip("@")
        
    chat_title = target
    chat_id = None
    
    # Try fetching chat info from Telegram
    try:
        chat = await message.bot.get_chat(target)
        chat_title = chat.title or chat.username or target
        chat_id = chat.id
    except Exception as e:
        # If lookup fails, fallback to raw input
        pass

    group = await add_discussion_group(target=target, name=chat_title, chat_id=chat_id)
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="➕ Add Another Group", callback_data="dg_add_group"))
    kb.row(InlineKeyboardButton(text="📋 Manage Groups", callback_data="dg_list_groups"))
    kb.row(InlineKeyboardButton(text="⬅️ Main Dashboard", callback_data="manage_discussion_groups"))
    
    await message.answer(
        f"✅ <b>Group Added Successfully!</b>\n\n"
        f"<b>Title:</b> {html.escape(chat_title)}\n"
        f"<b>Target:</b> <code>{target}</code>\n\n"
        f"The bot will now auto-post to this group according to your schedule.",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data == "dg_list_groups", HasPermissionFilter(permission=Permission.BROADCAST))
async def dg_list_groups_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    config = await get_discussion_config()
    groups = config.get("groups", [])
    
    if not groups:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="➕ Add First Group", callback_data="dg_add_group"))
        kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="manage_discussion_groups"))
        await call.message.edit_text(
            "📋 <b>Discussion Groups List</b>\n\n"
            "No discussion groups registered yet.",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
        return
        
    kb = InlineKeyboardBuilder()
    for g in groups:
        gid = str(g.get("id"))
        gname = g.get("name") or g.get("target")
        enabled = g.get("enabled", True)
        status_icon = "🟢" if enabled else "🔴"
        
        kb.row(
            InlineKeyboardButton(text=f"{status_icon} {gname[:25]}", callback_data=f"dg_toggle_group:{gid}"),
            InlineKeyboardButton(text="🗑 Remove", callback_data=f"dg_delete_group:{gid}")
        )
        
    kb.row(InlineKeyboardButton(text="➕ Add Group Link", callback_data="dg_add_group"))
    kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="manage_discussion_groups"))
    
    await call.message.edit_text(
        "📋 <b>Manage Discussion Groups</b>\n\n"
        "Tap a group button to toggle it <b>🟢 ON / 🔴 OFF</b> or <b>🗑 Remove</b> it:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("dg_toggle_group:"), HasPermissionFilter(permission=Permission.BROADCAST))
async def dg_toggle_group_handler(call: CallbackQuery, state: FSMContext):
    group_id = call.data.split(":", 1)[1]
    new_state = await toggle_discussion_group(group_id)
    status_label = "enabled 🟢" if new_state else "disabled 🔴"
    await call.answer(f"Group is now {status_label}!", show_alert=False)
    await dg_list_groups_handler(call, state)


@router.callback_query(F.data.startswith("dg_delete_group:"), HasPermissionFilter(permission=Permission.BROADCAST))
async def dg_delete_group_handler(call: CallbackQuery, state: FSMContext):
    group_id = call.data.split(":", 1)[1]
    await delete_discussion_group(group_id)
    await call.answer("Group removed!", show_alert=True)
    await dg_list_groups_handler(call, state)


@router.callback_query(F.data == "dg_edit_message", HasPermissionFilter(permission=Permission.BROADCAST))
async def dg_edit_message_prompt(call: CallbackQuery, state: FSMContext):
    await state.set_state(DiscussionGroupFSM.waiting_for_message_text)
    
    config = await get_discussion_config()
    curr_msg = config.get("auto_message_text", "")
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="❌ Cancel", callback_data="manage_discussion_groups"))
    
    await call.message.edit_text(
        "📝 <b>Edit Auto-Post Message Text</b>\n\n"
        "Send the new message text you want to auto-post to discussion groups.\n\n"
        "<i>You can use HTML tags (<b>bold</b>, <i>italic</i>, <code>code</code>, links, custom emojis, etc.).</i>\n\n"
        "<b>Current Text:</b>\n"
        f"----------------------------------------\n"
        f"{curr_msg}\n"
        f"----------------------------------------",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.message(DiscussionGroupFSM.waiting_for_message_text)
async def dg_receive_message_text(message: Message, state: FSMContext):
    new_text = message.text or message.caption or ""
    if not new_text:
        await message.answer("⚠️ Message text cannot be empty! Please send text.")
        return
        
    await update_auto_message(new_text)
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="⬅️ Back to Dashboard", callback_data="manage_discussion_groups"))
    
    await message.answer(
        "✅ <b>Auto-Message Text Updated!</b>\n\n"
        "<b>Preview:</b>\n"
        "----------------------------------------\n"
        f"{new_text}\n"
        "----------------------------------------",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data == "dg_edit_interval", HasPermissionFilter(permission=Permission.BROADCAST))
async def dg_edit_interval_prompt(call: CallbackQuery, state: FSMContext):
    await state.set_state(DiscussionGroupFSM.waiting_for_interval)
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="❌ Cancel", callback_data="manage_discussion_groups"))
    
    await call.message.edit_text(
        "⏱ <b>Set Auto-Post Interval</b>\n\n"
        "Enter the post frequency interval in <b>minutes</b> (e.g. <code>1</code> for every 1 minute):",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.message(DiscussionGroupFSM.waiting_for_interval)
async def dg_receive_interval(message: Message, state: FSMContext):
    try:
        minutes = int((message.text or "").strip())
        if minutes < 1:
            raise ValueError()
    except Exception:
        await message.answer("⚠️ Please enter a valid positive integer number of minutes (e.g. 1, 2, 5).")
        return
        
    await set_broadcaster_interval(minutes)
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="⬅️ Back to Dashboard", callback_data="manage_discussion_groups"))
    
    await message.answer(
        f"✅ <b>Post interval updated to every {minutes} minute(s)!</b>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data == "dg_test_send", HasPermissionFilter(permission=Permission.BROADCAST))
async def dg_test_send_handler(call: CallbackQuery, state: FSMContext):
    """Manually trigger one auto-post test batch to all active discussion groups."""
    config = await get_discussion_config()
    groups = [g for g in config.get("groups", []) if g.get("enabled", True)]
    text = config.get("auto_message_text", "")
    
    if not groups:
        await call.answer("⚠️ No active discussion groups configured!", show_alert=True)
        return
        
    if not text:
        await call.answer("⚠️ Auto-message text is empty!", show_alert=True)
        return
        
    await call.answer("🚀 Sending test post to discussion groups...", show_alert=False)
    
    me = await call.bot.get_me()
    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Visit Shop Bot", url=f"https://t.me/{me.username}")
    
    sent_count = 0
    fail_count = 0
    
    for g in groups:
        target = g.get("target") or g.get("chat_id")
        try:
            await call.bot.send_message(
                chat_id=target,
                text=text,
                parse_mode="HTML",
                reply_markup=kb.as_markup()
            )
            sent_count += 1
        except Exception as e:
            fail_count += 1
            
    await call.message.answer(
        f"📊 <b>Test Post Completed</b>\n\n"
        f"✅ Successfully sent: <b>{sent_count} groups</b>\n"
        f"⚠️ Failed / Restricted: <b>{fail_count} groups</b>",
        parse_mode="HTML"
    )
