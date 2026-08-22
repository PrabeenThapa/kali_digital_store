import json
import os
import aiofiles

_MENU_ICONS_FILE = "data/menu_icons.json"
_DEFAULT_ICONS = {
    # Main Menu
    "welcome_header": None,
    "welcome_balance": None,
    "shop": None,
    "visit_website": None,
    "top_up_wallet": None,
    "profile": None,
    "support": None,
    "history": None,
    "earn": None,
    "channel": None,
    "website_login_setup": None,
    "admin_panel": None,
    # Payment Methods
    "pay_balance": None,
    "pay_cryptopay": None,
    "pay_bybit": None,
    "pay_binance": None,
    "topup_bep20": None,
    "topup_trc20": None,
    "pay_stars": None,
    # Navigation & Controls
    "all_products": None,
    "sync_now": None,
    "back_button": None,
    "change_amount": None,
    # Notifications
    "notify_header": None,
    "notify_added": None,
    "notify_stock": None,
    "notify_price": None,
    "notify_buy_btn": None,
    # Purchase Alerts
    "purchase_header": None,
    "purchase_by": None,
    "purchase_product": None,
    "purchase_order_id": None,
    "purchase_qty": None,
    "purchase_total": None,
    "purchase_method": None,
    "purchase_view_btn": None,
    # System
    "loading_emoji": None,
}

_cached_icons = None

async def get_menu_icons() -> dict:
    """Read the menu icons configuration."""
    global _cached_icons
    if _cached_icons is not None:
        return _cached_icons

    if not os.path.exists(_MENU_ICONS_FILE):
        _cached_icons = _DEFAULT_ICONS.copy()
        return _cached_icons

    try:
        async with aiofiles.open(_MENU_ICONS_FILE, "r", encoding="utf-8") as f:
            data = json.loads(await f.read())
            _cached_icons = {**_DEFAULT_ICONS, **data}
            return _cached_icons
    except Exception:
        return _DEFAULT_ICONS.copy()

async def set_menu_icon(button_key: str, custom_emoji_id: str | None) -> None:
    """Set the custom emoji ID for a specific button."""
    global _cached_icons
    icons = await get_menu_icons()
    icons[button_key] = custom_emoji_id
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(_MENU_ICONS_FILE), exist_ok=True)
    
    async with aiofiles.open(_MENU_ICONS_FILE, "w", encoding="utf-8") as f:
        await f.write(json.dumps(icons, indent=4))
        
    _cached_icons = icons

def format_icon_html(button_key: str, default_emoji: str, icons: dict | None = None) -> str:
    """Format an emoji for HTML text messages with custom animated emoji if available."""
    custom_id = (icons or {}).get(button_key)
    if custom_id:
        return f'<tg-emoji emoji-id="{custom_id}">{default_emoji}</tg-emoji>'
    return default_emoji
