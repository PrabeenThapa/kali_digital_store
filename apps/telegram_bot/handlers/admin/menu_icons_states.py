from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.telegram_bot.utils.menu_icons import get_menu_icons, set_menu_icon

router = Router()

class MenuIconFSM(StatesGroup):
    waiting_for_icon = State()

BUTTON_CATEGORIES = {
    "main_menu": {
        "title": "📌 Main Menu & Header",
        "buttons": {
            "welcome_header": "Welcome Header Icon (🔥)",
            "welcome_balance": "Balance Line Icon (💵)",
            "shop": "Shop",
            "visit_website": "Visit Website",
            "top_up_wallet": "Top-up Wallet",
            "profile": "Profile",
            "support": "Support",
            "history": "History",
            "earn": "Earn",
            "channel": "Channel",
            "website_login_setup": "Website Login Setup",
            "admin_panel": "Admin Panel",
        }
    },
    "payments": {
        "title": "💳 Payment Method Buttons",
        "buttons": {
            "pay_balance": "Pay from Balance",
            "pay_cryptopay": "CryptoPay",
            "pay_bybit": "Bybit Pay",
            "pay_binance": "Binance Pay",
            "topup_bep20": "BEP20 USDT",
            "topup_trc20": "TRC20 USDT",
            "pay_stars": "Telegram Stars",
        }
    },
    "controls": {
        "title": "⚙️ Controls & Navigation Buttons",
        "buttons": {
            "all_products": "All Products",
            "sync_now": "Sync Now",
            "back_button": "Back Button",
            "change_amount": "Change Amount",
        }
    },
    "notifications": {
        "title": "🔔 Channel & Restock Notifications",
        "buttons": {
            "notify_header": "Header Icon (💥)",
            "notify_added": "Stock Added Line (➕)",
            "notify_stock": "Current Stock Line (📦)",
            "notify_price": "Price Line (💸)",
            "notify_buy_btn": "Buy Now Button (🛒)",
        }
    },
    "purchase_notify": {
        "title": "🛒 Purchase Alerts & Notifications",
        "buttons": {
            "purchase_header": "Header Banner (🎉)",
            "purchase_by": "User / By Line (👨)",
            "purchase_product": "Product Line (📱)",
            "purchase_order_id": "Order ID Line (🟦)",
            "purchase_qty": "Quantity Line (✏️)",
            "purchase_total": "Total Purchase Line (📊)",
            "purchase_method": "Payment Method Line (💳)",
            "purchase_view_btn": "View Product Button Icon",
        }
    },
    "system": {
        "title": "⚡ System & Animations",
        "buttons": {
            "loading_emoji": "Loading Animation",
        }
    }
}

ALL_BUTTON_NAMES = {}
for cat_data in BUTTON_CATEGORIES.values():
    ALL_BUTTON_NAMES.update(cat_data["buttons"])


@router.callback_query(F.data == "manage_menu_icons")
async def manage_menu_icons_handler(call: CallbackQuery, state: FSMContext):
    """Main category selector for menu icons manager."""
    await state.clear()
    
    icons = await get_menu_icons()
    
    kb = InlineKeyboardBuilder()
    for cat_key, cat_info in BUTTON_CATEGORIES.items():
        custom_count = sum(1 for b_key in cat_info["buttons"] if icons.get(b_key))
        total_count = len(cat_info["buttons"])
        badge = f" ({custom_count}/{total_count} set)" if custom_count > 0 else ""
        kb.row(InlineKeyboardButton(text=f"{cat_info['title']}{badge}", callback_data=f"icon_cat:{cat_key}"))
        
    kb.row(InlineKeyboardButton(text="⬅️ Back to Console", callback_data="console"))
    
    await call.message.edit_text(
        "🎨 <b>Menu Icons & Emojis Manager</b>\n\n"
        "Select a section below to customize animated premium custom emojis for any button in the bot:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("icon_cat:"))
async def icon_category_handler(call: CallbackQuery, state: FSMContext):
    """Show list of buttons within a specific category."""
    cat_key = call.data.split(":", 1)[1]
    cat_info = BUTTON_CATEGORIES.get(cat_key)
    if not cat_info:
        await call.answer("Category not found.", show_alert=True)
        return
        
    icons = await get_menu_icons()
    
    kb = InlineKeyboardBuilder()
    for b_key, b_name in cat_info["buttons"].items():
        status = "✨ Customized" if icons.get(b_key) else "⚪ Default"
        kb.row(InlineKeyboardButton(text=f"{b_name} ({status})", callback_data=f"edit_icon:{b_key}:{cat_key}"))
        
    kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="manage_menu_icons"))
    
    await call.message.edit_text(
        f"{cat_info['title']}\n\n"
        "Select a button below to update its animated custom emoji:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("edit_icon:"))
async def edit_icon_handler(call: CallbackQuery, state: FSMContext):
    """Prompt the admin to send a custom emoji."""
    parts = call.data.split(":")
    button_key = parts[1]
    cat_key = parts[2] if len(parts) > 2 else "main_menu"
    
    await state.update_data(editing_button=button_key, parent_cat=cat_key)
    await state.set_state(MenuIconFSM.waiting_for_icon)
    
    display_name = ALL_BUTTON_NAMES.get(button_key, button_key)
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🗑 Remove Custom Icon", callback_data=f"remove_icon:{button_key}:{cat_key}"))
    kb.row(InlineKeyboardButton(text="❌ Cancel", callback_data=f"icon_cat:{cat_key}"))
    
    await call.message.edit_text(
        f"Send me the animated custom emoji you want to use for <b>{display_name}</b>.\n\n"
        "<i>Just pick a premium emoji from your keyboard and send it as a message!</i>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("remove_icon:"))
async def remove_icon_handler(call: CallbackQuery, state: FSMContext):
    """Remove the custom icon for a button."""
    parts = call.data.split(":")
    button_key = parts[1]
    cat_key = parts[2] if len(parts) > 2 else "main_menu"
    
    await set_menu_icon(button_key, None)
    
    await call.answer("Custom icon removed!", show_alert=True)
    call.data = f"icon_cat:{cat_key}"
    await icon_category_handler(call, state)


@router.message(MenuIconFSM.waiting_for_icon)
async def receive_icon_handler(message: Message, state: FSMContext):
    """Receive the custom emoji and save it."""
    data = await state.get_data()
    button_key = data.get("editing_button")
    cat_key = data.get("parent_cat", "main_menu")
    
    if not button_key:
        await state.clear()
        return
        
    custom_emoji_id = None
    if message.entities:
        for ent in message.entities:
            if ent.type == "custom_emoji":
                custom_emoji_id = ent.custom_emoji_id
                break
                
    if not custom_emoji_id:
        await message.answer("⚠️ That doesn't look like a Premium custom emoji! Please try again or cancel.")
        return
        
    await set_menu_icon(button_key, custom_emoji_id)
    
    display_name = ALL_BUTTON_NAMES.get(button_key, button_key)
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="⬅️ Back to Icons List", callback_data=f"icon_cat:{cat_key}"))
    
    await message.answer(
        f"✅ Successfully updated the custom icon for <b>{display_name}</b>!",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.clear()
