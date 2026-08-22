from typing import Callable, Iterable, Tuple
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apps.telegram_bot.i18n import localize
from apps.telegram_bot.utils.auto_icon import auto_icon
from packages.database.models import Permission
from apps.telegram_bot.utils.paginator import LazyPaginator  # noqa: F401
from packages.config.config import EnvKeys


def _make_btn(
    text: str,
    callback_data: str = None,
    url: str = None,
    icon_custom_emoji_id: str = None,
    style: str = None,
    **kwargs
) -> InlineKeyboardButton:
    """
    Create an InlineKeyboardButton, injecting icon_custom_emoji_id and style
    via __pydantic_extra__ so they are included in the Telegram API payload.
    Aiogram's current Pydantic schema doesn't expose these fields natively.
    Safeguards callback_data to strictly <= 64 bytes to prevent TelegramBadRequest.
    """
    base_kwargs = {}
    if callback_data is not None:
        cb_bytes = callback_data.encode("utf-8")
        if len(cb_bytes) > 64:
            callback_data = cb_bytes[:64].decode("utf-8", errors="ignore")
        base_kwargs["callback_data"] = callback_data
    if url:
        base_kwargs["url"] = url
    base_kwargs.update(kwargs)
    btn = InlineKeyboardButton(text=text, **base_kwargs)
    extra = {}
    if icon_custom_emoji_id and str(icon_custom_emoji_id).strip().isdigit():
        extra["icon_custom_emoji_id"] = str(icon_custom_emoji_id).strip()
    if style:
        extra["style"] = style
    if extra:
        if btn.__pydantic_extra__ is None:
            btn.__pydantic_extra__ = {}
        btn.__pydantic_extra__.update(extra)
    return btn


# ─────────────────────────────────────────────
#  MAIN MENU  (design board layout)
# ─────────────────────────────────────────────

async def main_menu(role: int, channel: str | None = None, helper: str | None = None) -> InlineKeyboardMarkup:
    """
    Main menu layout requested:
    Row 1: ✅ Shop
    Row 2: 🌐 Visit Website
    Row 3: 💰 Top-up Wallet | ⚡ Profile
    Row 4: 🔔 Support       | 🪙 History
    Row 5: 🌟 Earn          | 🔊 Channel ↗
    Row 6: 🔗 Website Login Setup
    Row 7: 🔧 Admin Panel
    """
    kb = InlineKeyboardBuilder()

    from apps.telegram_bot.utils.menu_icons import get_menu_icons
    icons = await get_menu_icons()

    # Row 1 (Green)
    kb.row(InlineKeyboardButton(text="Shop", callback_data="shop", style="success", icon_custom_emoji_id=icons.get("shop")))
    
    # Row 2 (Green)
    kb.row(InlineKeyboardButton(text="Visit Website", url=EnvKeys.WEB_URL or "http://127.0.0.1:3000", style="success", icon_custom_emoji_id=icons.get("visit_website")))
    
    # Row 3 (Primary/Purple)
    kb.row(
        InlineKeyboardButton(text="Top-up Wallet", callback_data="replenish_balance", style="primary", icon_custom_emoji_id=icons.get("top_up_wallet")),
        InlineKeyboardButton(text="Profile", callback_data="profile", style="primary", icon_custom_emoji_id=icons.get("profile")),
    )
    
    # Row 4 (Support Red, History Primary)
    kb.row(
        InlineKeyboardButton(text="Support", callback_data="support", style="danger", icon_custom_emoji_id=icons.get("support")),
        InlineKeyboardButton(text="History", callback_data="bought_items", style="primary", icon_custom_emoji_id=icons.get("history")),
    )
    
    # Row 5 (Green)
    channel_url = f"https://t.me/{channel.lstrip('@')}" if channel else None
    if channel_url:
        kb.row(
            InlineKeyboardButton(text="Earn", callback_data="referral_system", style="success", icon_custom_emoji_id=icons.get("earn")),
            InlineKeyboardButton(text="Channel ↗", url=channel_url, style="success", icon_custom_emoji_id=icons.get("channel")),
        )
    else:
        kb.row(InlineKeyboardButton(text="Earn", callback_data="referral_system", style="success", icon_custom_emoji_id=icons.get("earn")))
        
    # Row 6 (Primary/Purple)
    kb.row(InlineKeyboardButton(text="Website Login Setup", callback_data="web_login", style="primary", icon_custom_emoji_id=icons.get("website_login_setup")))

    # Admin panel (only for admins)
    if Permission.has_any_admin_perm(role):
        kb.row(InlineKeyboardButton(text="Admin Panel", callback_data="console", style="primary", icon_custom_emoji_id=icons.get("admin_panel")))

    return kb.as_markup()



# ─────────────────────────────────────────────
#  PROFILE KEYBOARD
# ─────────────────────────────────────────────

def profile_keyboard(referral_percent: int, user_items: int = 0, cart_count: int = 0, discount_percent: float = 0) -> InlineKeyboardMarkup:
    """Profile keyboard with cart, history, subscriptions."""
    kb = InlineKeyboardBuilder()
    kb.button(text=localize("btn.replenish"), callback_data="replenish_balance", style="success")
    if referral_percent != 0:
        kb.button(text=localize("btn.referral"), callback_data="referral_system", style="success")
    if user_items != 0:
        kb.button(text=localize("btn.purchased"), callback_data="bought_items", style="primary")
    cart_text = localize("btn.cart", count=cart_count) if cart_count > 0 else localize("btn.cart_empty")
    kb.button(text=cart_text, callback_data="cart", style="primary")
    kb.button(text=localize("btn.operation_history"), callback_data="operation_history", style="primary")
    if discount_percent and discount_percent > 0:
        kb.button(text=f"🏷 Promo Active ({discount_percent}% off)", callback_data="remove_account_discount", style="danger")
    else:
        kb.button(text=localize("btn.redeem_promo"), callback_data="redeem_promo", style="success")
    kb.button(text=localize("btn.back"), callback_data="back_to_menu", style="primary")
    kb.adjust(1)
    return kb.as_markup()


# ─────────────────────────────────────────────
#  ADMIN CONSOLE KEYBOARD
# ─────────────────────────────────────────────

def admin_console_keyboard(maintenance_mode: bool = False, role: int = 127) -> InlineKeyboardMarkup:
    """Admin panel — shows only buttons the user has permissions for."""
    kb = InlineKeyboardBuilder()
    if role & Permission.CATALOG_MANAGE:
        kb.button(text=localize("admin.menu.shop"), callback_data="shop_management", style="primary")
        kb.button(text=localize("admin.menu.goods"), callback_data="goods_management", style="primary")
        kb.button(text=localize("admin.menu.categories"), callback_data="categories_management", style="primary")
        kb.button(text="🔗 Reseller APIs", callback_data="admin_resellers", style="primary")
        kb.button(text="💲 Price Manager", callback_data="rs_prices:0", style="primary")
    if role & Permission.PROMO_MANAGE:
        kb.button(text=localize("admin.menu.promo"), callback_data="promo_mgmt", style="primary")
    if role & Permission.USERS_MANAGE:
        kb.button(text=localize("admin.menu.users"), callback_data="user_management", style="primary")
    if role & Permission.ADMINS_MANAGE:
        kb.button(text=localize("admin.menu.roles"), callback_data="role_mgmt", style="primary")
    if role & Permission.BROADCAST:
        kb.button(text=localize("admin.menu.broadcast"), callback_data="send_message", style="primary")
        kb.button(text="📢 Auto-Post to Groups", callback_data="manage_discussion_groups", style="primary")
    if role & Permission.STATS_VIEW:
        kb.button(text="📈 Financial Report", callback_data="financial_report", style="primary")
    if role & Permission.SETTINGS_MANAGE:
        maintenance_key = "admin.menu.maintenance_on" if maintenance_mode else "admin.menu.maintenance_off"
        kb.button(text=localize(maintenance_key), callback_data="toggle_maintenance", style="primary")
        kb.button(text="🎨 Edit Menu Icons", callback_data="manage_menu_icons", style="primary")
        kb.button(text="📝 Edit Bot Description", callback_data="edit_bot_desc", style="primary")
    kb.button(text="🏛️ " + localize("btn.back"), callback_data="back_to_menu", style="primary")
    kb.adjust(1)
    return kb.as_markup()


# ─────────────────────────────────────────────
#  UTILITIES
# ─────────────────────────────────────────────

def simple_buttons(buttons: Iterable[Tuple[str, str]], per_row: int = 1) -> InlineKeyboardMarkup:
    """Universal button assembly from (text, callback_data)"""
    kb = InlineKeyboardBuilder()
    for text, cb in buttons:
        kb.button(text=text, callback_data=cb, style="primary")
    kb.adjust(per_row)
    return kb.as_markup()


def back(cb: str = "menu", text: str | None = None) -> InlineKeyboardMarkup:
    """One 'Back' button."""
    return simple_buttons([(text or localize("btn.back"), cb)])


def close() -> InlineKeyboardMarkup:
    """One button 'Close'."""
    return simple_buttons([(localize("btn.close"), "close")])


# ─────────────────────────────────────────────
#  ADMIN CATEGORY PICKER  (used when adding a product)
# ─────────────────────────────────────────────

def admin_category_picker_keyboard(
        categories: list[str],
        page: int,
        total_pages: int,
        back_cb: str = "goods_management",
) -> InlineKeyboardMarkup:
    """
    Inline category selector for the "add product" flow.
    Each button carries callback_data = 'pick_cat:<category_name>'.
    Includes ◀/▶ navigation and a Back button.
    """
    from apps.telegram_bot.utils.auto_icon import auto_icon  # local import to avoid circular
    kb = InlineKeyboardBuilder()

    for cat_name in categories:
        icon = auto_icon(cat_name)
        kb.button(text=f"{icon} {cat_name}", callback_data=f"pick_cat:{cat_name}", style="primary")
    kb.adjust(1)

    # Navigation row
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"pick_cat_page:{page - 1}", style="primary"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page + 1} / {total_pages}", callback_data="noop", style="danger"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="Next ▶", callback_data=f"pick_cat_page:{page + 1}", style="primary"))
        kb.row(*nav_buttons)

    kb.row(InlineKeyboardButton(text=localize("btn.back"), callback_data=back_cb, style="primary"))
    return kb.as_markup()


# ─────────────────────────────────────────────
#  LAZY PAGINATED KEYBOARD
# ─────────────────────────────────────────────

async def lazy_paginated_keyboard(
        paginator: 'LazyPaginator',
        item_text: Callable[[object], str],
        item_callback: Callable[[object], str],
        page: int = 0,
        back_cb: str | None = None,
        nav_cb_prefix: str = "",
        back_text: str | None = None,
) -> InlineKeyboardMarkup:
    """Lazy pagination keyboard with data loading on demand"""
    kb = InlineKeyboardBuilder()

    items = await paginator.get_page(page)
    for item in items:
        kb.button(text=item_text(item), callback_data=item_callback(item))
    kb.adjust(1)

    total_pages = await paginator.get_total_pages()
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"{nav_cb_prefix}{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"{nav_cb_prefix}{page + 1}"))
        kb.row(*nav_buttons)

    if back_cb:
        kb.row(InlineKeyboardButton(text=back_text or localize("btn.back"), callback_data=back_cb))

    return kb.as_markup()


# ─────────────────────────────────────────────
#  CATEGORIES KEYBOARD  (design board style)
# ─────────────────────────────────────────────

def categories_keyboard(
        categories: list,
        page: int,
        total_pages: int,
        nav_cb_prefix: str = "categories-page_",
) -> InlineKeyboardMarkup:
    """
    Design-board categories list with auto icons + stock counts
    """
    kb = InlineKeyboardBuilder()

    for i, cat in enumerate(categories):
        if isinstance(cat, dict):
            name = cat["name"]
            products = cat.get("product_count", 0)
            stock = cat.get("stock_codes", 0)
            label = f"{name}  •  {products} product{'s' if products != 1 else ''}  •  {stock} in stock"
        else:
            name = cat
            label = str(name)
        kb.add(InlineKeyboardButton(text=label, callback_data=f"cat:{i}:{page}", style="primary"))
    kb.adjust(1)

    # Navigation row
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"{nav_cb_prefix}{page - 1}", style="primary"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page + 1} / {total_pages}", callback_data="noop", style="danger"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="Next ▶", callback_data=f"{nav_cb_prefix}{page + 1}", style="primary"))
        kb.row(*nav_buttons)

    kb.row(InlineKeyboardButton(text=localize("btn.back"), callback_data="back_to_menu", style="primary"))
    return kb.as_markup()


# ─────────────────────────────────────────────
#  SHOP CATEGORY MENU  (flat product categories)
# ─────────────────────────────────────────────

def shop_category_menu_keyboard(
        categories: list[tuple],
        featured_items: list[dict] = None,
        icons: dict = None,
) -> InlineKeyboardMarkup:
    """
    Category menu for the shop: 3-column grid of icon + name buttons matching reference image.
    If featured_items provided, they are shown as individual clickable rows below the grid.
    Bottom rows: All Products, Sync Now, Back.
    """
    kb = InlineKeyboardBuilder()
    for cat_data in categories:
        label = cat_data[0]
        emoji_id = cat_data[3] if len(cat_data) > 3 else None
        emoji_id_str = str(emoji_id).strip() if emoji_id else None
        
        btn = _make_btn(
            text=label,
            callback_data=f"shopcat:{label}",
            style="primary",
            icon_custom_emoji_id=emoji_id_str,
        )
        kb.add(btn)
    kb.adjust(3)  # 3 columns matching the reference image

    # ⭐ Featured items below the grid
    if featured_items:
        for item in featured_items:
            name = item["name"]
            price = item["price"]
            is_inf = item.get("is_infinity")
            stock = item.get("stock")
            stock_str = "∞" if is_inf else str(stock) if stock is not None else "0"
            
            style = "success"
            if not is_inf and (not stock or stock == 0):
                style = "danger"
            elif not is_inf and stock <= 5:
                style = "primary"
            else:
                style = "success"
                
            custom_emoji = item.get("icon_custom_emoji_id")
            custom_emoji_str = str(custom_emoji).strip() if custom_emoji else None
            kb.row(_make_btn(
                text=f"{name} | {price:g}$ | {stock_str}".strip(),
                callback_data=f"shopcat_featured:{name}",
                style=style,
                icon_custom_emoji_id=custom_emoji_str,
            ))

    kb.row(_make_btn(text="🔎 All Products", callback_data="shop_all", style="primary", icon_custom_emoji_id=icons.get("all_products") if icons else None))
    kb.row(_make_btn(text="↻ Sync Now", callback_data="user_sync_now", style="primary", icon_custom_emoji_id=icons.get("sync_now") if icons else None))
    kb.row(_make_btn(text=localize("btn.back"), callback_data="back_to_menu", style="primary", icon_custom_emoji_id=icons.get("back_button") if icons else None))
    return kb.as_markup()


# ─────────────────────────────────────────────
#  SHOP ITEMS KEYBOARD  (design board style)
# ─────────────────────────────────────────────

def shop_items_keyboard(
        items: list[dict],
        page: int,
        total_pages: int,
        back_cb: str,
        sort: str = "name",
        nav_cb_prefix: str = "gp_",
) -> InlineKeyboardMarkup:
    """
    Design-board product list matching reference:
    ChatGPT Plus - 1.5 USDT (Stock: 4)
    EA Play Pro - 8.99 USDT (Stock: 0)
    In-stock items appear before sold-out ones.
    """
    kb = InlineKeyboardBuilder()

    def _has_stock(it: dict) -> bool:
        if it.get("is_infinity"):
            return True
        s = it.get("stock")
        return s is not None and s > 0

    items = sorted(items, key=lambda it: (0 if _has_stock(it) else 1))

    for i, item in enumerate(items):
        name = item["name"]
        price = item["price"]
        stock = item["stock"]
        is_inf = item["is_infinity"]

        if is_inf:
            stock_str = "∞"
            style = "success"
        else:
            stock_str = str(stock)
            if not stock or stock == 0:
                style = "danger"
            elif stock <= 5:
                style = "primary"
            else:
                style = "success"
                
        custom_emoji_str = str(db_icon).strip() if db_icon and str(db_icon).strip().isdigit() else None
        btn_text = f"{name} | {price:g}$ | {stock_str}"
        kb.add(_make_btn(
            text=btn_text,
            callback_data=f"itm:{i}:{page}",
            style=style,
            icon_custom_emoji_id=custom_emoji_str,
        ))

    kb.adjust(1)

    # Navigation row
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"{nav_cb_prefix}{page - 1}", style="primary"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page + 1} / {total_pages}", callback_data="noop", style="primary"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Next ▶", callback_data=f"{nav_cb_prefix}{page + 1}", style="primary"))
    if nav_buttons:
        kb.row(*nav_buttons)

    # Sort row
    sort_label = "🧮 Sort: Price" if sort == "name" else "🔠 Sort: Name"
    next_sort = "price" if sort == "name" else "name"
    kb.row(
        InlineKeyboardButton(text="↻ Refresh", callback_data=f"shop_refresh:{sort}", style="primary"),
        InlineKeyboardButton(text=sort_label, callback_data=f"shop_sort:{next_sort}", style="primary"),
    )
    kb.row(InlineKeyboardButton(text="🏛️ " + localize("btn.back"), callback_data=back_cb, style="primary"))
    return kb.as_markup()


# ─────────────────────────────────────────────
#  ITEM DETAIL KEYBOARD
# ─────────────────────────────────────────────

def item_info(
        item_name: str, back_data: str, avg_rating: float = None,
        review_count: int = 0, has_purchased: bool = False,
        applied_promo: str = None, reviews_enabled: bool = True,
        has_stock: bool = True,
        price: float = None,
        stock_label: str = None,
) -> InlineKeyboardMarkup:
    """
    Product card — design board style:
    [🛒 Buy Now]  [🛍 Add to Cart]
    [🎟 Apply/Remove Promo]
    [⭐ N Reviews]  [✏️ Leave Review]
    [🔙 Back]
    """
    kb = InlineKeyboardBuilder()
    if has_stock:
        if price is not None and stock_label is not None:
            buy_text = f"🛍️ BUY NOW | {price:g} USDT | 📦 {stock_label}"
            kb.button(text=buy_text, callback_data="buy_now", style="primary")
        else:
            kb.button(text="🛍️ " + localize("btn.buy"), callback_data="buy_now", style="primary")
            
        # Optional add to cart
        # kb.button(text="🛍️ " + localize("btn.add_to_cart"), callback_data="add_to_cart", style="success")
        kb.adjust(1)

    if applied_promo:
        kb.row(InlineKeyboardButton(text="🚫 " + localize("btn.remove_promo"), callback_data="remove_promo", style="danger"))
    else:
        kb.row(InlineKeyboardButton(text="🎫 " + localize("btn.apply_promo"), callback_data="apply_promo", style="primary"))

    if reviews_enabled:
        review_btns = []
        if review_count > 0:
            review_btns.append(InlineKeyboardButton(
                text=localize("btn.view_reviews", count=review_count),
                callback_data=f"reviews:{item_name}:0"
            ))
        if has_purchased:
            review_btns.append(InlineKeyboardButton(
                text=localize("btn.leave_review"),
                callback_data=f"review:{item_name}", style="primary"
            ))
        if review_btns:
            kb.row(*review_btns)

    kb.row(InlineKeyboardButton(text="🔄 Refresh", callback_data="shop_refresh:name", style="success"))
    kb.row(InlineKeyboardButton(text="✖ Back to Store", callback_data=back_data, style="danger"))
    return kb.as_markup()


# ─────────────────────────────────────────────
#  QUANTITY SELECTOR  (design board grid)
# ─────────────────────────────────────────────

def quantity_selector_keyboard(back_cb: str, max_stock: int = 999) -> InlineKeyboardMarkup:
    """
    Design board quantity grid:
    [1] [2] [3] [4]
    [5] [10] [25] [50]
    [✅ Confirm & Pay]
    [🔙 Back]  [🏠 Home]
    """
    kb = InlineKeyboardBuilder()

    # Row 1: small quantities
    row1 = [1, 2, 3, 4]
    # Row 2: bulk quantities
    row2 = [5, 10, 25, 50]

    for qty in row1:
        if qty <= max_stock or max_stock == 999:
            kb.button(text=str(qty), callback_data=f"set_qty:{qty}", style="primary")
    kb.adjust(4)

    for qty in row2:
        if qty <= max_stock or max_stock == 999:
            kb.button(text=str(qty), callback_data=f"set_qty:{qty}", style="primary")
    kb.adjust(4)

    kb.row(InlineKeyboardButton(text="✅ Confirm & Pay", callback_data="confirm_qty", style="success"))
    kb.row(
        InlineKeyboardButton(text="🔙 Back", callback_data=back_cb, style="primary"),
        InlineKeyboardButton(text="🏛️ Home", callback_data="back_to_menu", style="primary"),
    )
    return kb.as_markup()


# ─────────────────────────────────────────────
#  ORDER SUMMARY KEYBOARD
# ─────────────────────────────────────────────

def order_summary_keyboard() -> InlineKeyboardMarkup:
    """
    Design board order summary:
    [💸 Pay from Wallet]
    [🔄 Change Qty]  [🏠 Home]
    """
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💸 Pay from Wallet", callback_data="select_payment", style="success"))
    kb.row(
        InlineKeyboardButton(text="↻ Change Qty", callback_data="change_qty", style="primary"),
        InlineKeyboardButton(text="🏛️ Home", callback_data="back_to_menu", style="primary"),
    )
    return kb.as_markup()


def insufficient_balance_keyboard() -> InlineKeyboardMarkup:
    """Shown when the user's wallet can't cover the order total."""
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🪙 Top Up Wallet", callback_data="replenish_balance", style="success"))
    kb.row(
        InlineKeyboardButton(text="🔙 Back to Order", callback_data="change_qty", style="primary"),
        InlineKeyboardButton(text="🏛️ Home", callback_data="back_to_menu", style="primary"),
    )
    return kb.as_markup()


# ─────────────────────────────────────────────
#  NUMPAD (legacy — kept for admin use)
# ─────────────────────────────────────────────

def numpad_keyboard(qty: int, back_cb: str, has_wallet_topup: bool = True) -> InlineKeyboardMarkup:
    """Numpad quantity selector (kept for compatibility)."""
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text=f"Qty: {qty}", callback_data="noop", style="danger"),
        InlineKeyboardButton(text="Del ⌫", callback_data="qty_del", style="danger"),
    )
    for row_start in [1, 6]:
        row_btns = []
        for d in range(row_start, min(row_start + 5, 11)):
            digit = d % 10
            row_btns.append(InlineKeyboardButton(text=str(digit), callback_data=f"qty_digit:{digit}", style="primary"))
        kb.row(*row_btns)
    if has_wallet_topup:
        kb.row(InlineKeyboardButton(text="🪙 Top Up Wallet", callback_data="replenish_balance", style="success"))
    kb.row(InlineKeyboardButton(text="🛍️ Buy Now", callback_data="buy", style="success"))
    kb.row(
        InlineKeyboardButton(text="🔗 Share", callback_data="share_item", style="primary"),
        InlineKeyboardButton(text="📋 Note", callback_data="view_note", style="danger"),
    )
    kb.row(InlineKeyboardButton(text="🔙 " + localize("btn.back"), callback_data=back_cb, style="primary"))
    return kb.as_markup()


# ─────────────────────────────────────────────
#  PAYMENT METHOD KEYBOARD  (design board)
# ─────────────────────────────────────────────

def payment_menu(pay_url: str) -> InlineKeyboardMarkup:
    """Buttons under the CryptoPay invoice."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🪙 " + localize("btn.pay"), url=pay_url, style="success")
    kb.button(text="🔍 " + localize("btn.check_payment"), callback_data="check", style="primary")
    kb.button(text="🔙 " + localize("btn.back"), callback_data="profile", style="primary")
    kb.adjust(1)
    return kb.as_markup()


def get_payment_choice(is_topup: bool = False, icons: dict = None) -> InlineKeyboardMarkup:
    """
    Payment method selection keyboard.

    Args:
        is_topup: When True (balance top-up flow), hides 'Pay from Balance'
                  and 'Change Qty' since they don't apply.
        icons: Optional dictionary of menu icons from get_menu_icons().
    """
    from packages.config.config import EnvKeys
    kb = InlineKeyboardBuilder()
    icons = icons or {}

    # Balance pay — only shown in item purchase flow, not top-up
    if not is_topup:
        kb.row(_make_btn(text="💳 Pay from Balance", callback_data="pay_balance", style="success", icon_custom_emoji_id=icons.get("pay_balance")))

    if EnvKeys.CRYPTO_PAY_TOKEN:
        kb.row(_make_btn(text="💎 CryptoPay", callback_data="pay_cryptopay", style="success", icon_custom_emoji_id=icons.get("pay_cryptopay")))

    # Bybit Pay
    if EnvKeys.BYBIT_UID:
        kb.row(_make_btn(text="⚡ Bybit Pay", callback_data="pay_bybit", style="success", icon_custom_emoji_id=icons.get("pay_bybit")))

    # Binance Pay
    if EnvKeys.BINANCE_PAY_ID:
        kb.row(_make_btn(text="🪙 Binance Pay", callback_data="pay_binance", style="success", icon_custom_emoji_id=icons.get("pay_binance")))

    # Crypto top-up flows
    kb.row(_make_btn(text="🔷 BEP20 USDT (Top-up first)", callback_data="topup_bep20", style="success", icon_custom_emoji_id=icons.get("topup_bep20")))
    kb.row(_make_btn(text="🌐 TRC20 USDT (Top-up first)", callback_data="topup_trc20", style="success", icon_custom_emoji_id=icons.get("topup_trc20")))

    # Telegram Stars
    if EnvKeys.STARS_PER_VALUE > 0:
        kb.row(_make_btn(text="🌟 " + localize("btn.pay.stars"), callback_data="pay_stars", style="success", icon_custom_emoji_id=icons.get("pay_stars")))

    # Bottom row: qty change only in purchase flow; just Home in top-up flow
    if is_topup:
        kb.row(
            _make_btn(text="✏️ Change Amount", callback_data="change_topup_amount", style="success", icon_custom_emoji_id=icons.get("change_amount")),
            _make_btn(text=localize("btn.back"), callback_data="back_to_menu", style="primary", icon_custom_emoji_id=icons.get("back_button")),
        )
    else:
        kb.row(
            _make_btn(text="↻ Change Qty", callback_data="change_qty", style="primary", icon_custom_emoji_id=icons.get("change_amount")),
            _make_btn(text=localize("btn.back"), callback_data="back_to_menu", style="primary", icon_custom_emoji_id=icons.get("back_button")),
        )
    return kb.as_markup()


# ─────────────────────────────────────────────
#  TOP-UP CANCEL KEYBOARD
# ─────────────────────────────────────────────

def topup_cancel_keyboard() -> InlineKeyboardMarkup:
    """Cancel button for top-up screens."""
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🚫 Cancel", callback_data="back_to_menu", style="primary"))
    return kb.as_markup()


# ─────────────────────────────────────────────
#  OTHER KEYBOARDS
# ─────────────────────────────────────────────

def question_buttons(question: str, back_data: str) -> InlineKeyboardMarkup:
    """Universal yes/no + Back."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ " + localize("btn.yes"), callback_data=f"{question}_yes", style="success")
    kb.button(text="🚫 " + localize("btn.no"), callback_data=f"{question}_no", style="danger")
    kb.button(text="🔙 " + localize("btn.back"), callback_data=back_data, style="primary")
    kb.adjust(2)
    return kb.as_markup()


def check_sub(channel_username: str) -> InlineKeyboardMarkup:
    """Channel subscription check."""
    kb = InlineKeyboardBuilder()
    kb.button(text=localize("btn.channel"), url=f"https://t.me/{channel_username}", style="primary")
    kb.button(text=localize("btn.check_subscription"), callback_data="sub_channel_done", style="primary")
    kb.adjust(1)
    return kb.as_markup()


def rating_keyboard(item_name: str) -> InlineKeyboardMarkup:
    """Rating selection keyboard (1-5 stars)."""
    kb = InlineKeyboardBuilder()
    for i in range(1, 6):
        kb.button(text="⭐" * i, callback_data=f"rating:{i}", style="primary")
    kb.button(text="🔙 " + localize("btn.back"), callback_data="back_to_menu", style="primary")
    kb.adjust(5)
    return kb.as_markup()


def referral_system_keyboard(has_referrals: bool = False, has_earnings: bool = False) -> InlineKeyboardMarkup:
    """Referral system keyboard."""
    kb = InlineKeyboardBuilder()
    if has_referrals:
        kb.button(text=localize("btn.view_referrals"), callback_data="view_referrals", style="success")
    if has_earnings:
        kb.button(text=localize("btn.view_earnings"), callback_data="view_all_earnings", style="primary")
    kb.button(text="🏛️ " + localize("btn.back"), callback_data="profile", style="primary")
    kb.adjust(1)
    return kb.as_markup()
