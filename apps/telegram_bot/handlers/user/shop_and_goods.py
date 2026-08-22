from decimal import Decimal
from functools import partial
from html import escape

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from packages.database.methods import (
    get_bought_item_info, check_value, query_user_bought_items, get_item_info_cached,
    select_item_values_amount_cached
)
from packages.database.methods.read import (
    get_item_avg_rating, has_purchased_item, validate_promo_for_item,
    get_user_review, invalidate_rating_cache, get_item_info, check_user,
)
from packages.database.methods.create import create_review
from packages.database.methods.lazy_queries import query_item_reviews
from packages.database.methods.transactions import redeem_balance_promo
from packages.database.methods.audit import log_audit
from apps.telegram_bot.keyboards import item_info, back, lazy_paginated_keyboard
from apps.telegram_bot.keyboards.inline import (
    simple_buttons, rating_keyboard,
    quantity_selector_keyboard, order_summary_keyboard,
)
from packages.services.pricing import apply_promo_discount
from apps.telegram_bot.i18n import localize
from packages.config.config import EnvKeys
from apps.telegram_bot.utils.paginator import LazyPaginator
from apps.telegram_bot.utils.auto_icon import auto_icon
from apps.telegram_bot.utils.category_resolver import resolve_category
from apps.telegram_bot.core.metrics import get_metrics
from apps.telegram_bot.states import ShopStates
from apps.telegram_bot.states.review import ReviewFSM
from apps.telegram_bot.states.promo import PromoFSM

router = Router()

_CAPTION_LIMIT = 1024


async def _get_current_reseller_product(item_name: str, state_data: dict):
    """Resolve by stable local product ID, with a name fallback for old sessions."""
    from packages.services.reseller.fulfillment import (
        get_reseller_product_by_id, get_reseller_product_by_name,
    )
    product_id = state_data.get("reseller_product_id")
    if product_id:
        product = await get_reseller_product_by_id(int(product_id))
        if product is not None:
            return product
    return await get_reseller_product_by_name(item_name)


async def _edit_or_resend(target, text: str, markup):
    """
    Render a text view. Handles the case where the current message is a photo
    (from a logo detail page) -> edit_text fails on photo messages, so we delete
    and send a fresh text message instead.
    """
    if hasattr(target, "message") and hasattr(target.message, "edit_text"):
        msg = target.message
        # If the current message is a photo/media, it has no editable text
        is_photo = isinstance(getattr(msg, "photo", None), list) and len(msg.photo) > 0
        is_doc = getattr(msg, "document", None) is not None and type(msg.document).__name__ == "Document"
        if is_photo or is_doc:
            try:
                await msg.delete()
            except TelegramBadRequest:
                pass
            await msg.answer(text, reply_markup=markup, parse_mode="HTML")
            return
        try:
            await msg.edit_text(text, reply_markup=markup, parse_mode="HTML")
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                return
            # Fallback: message wasn\'t editable as text -> send new
            await msg.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=markup, parse_mode="HTML")


async def _send_detail(target, text: str, markup, item_name: str):
    """
    Send a product detail view. Prefers a native Telegram file_id brand icon
    (instant, no network fetch); falls back to the unavatar.io logo fetch for
    brands not covered there; falls back to plain text if neither resolves or
    the photo send fails for any reason, so the page always renders.

    Telegram cannot convert an existing text message into a photo via edit_text,
    so when a photo is shown we delete the source message and send a fresh one.
    """
    from apps.telegram_bot.utils.brand_icons import icon_file_id_for
    from apps.telegram_bot.utils.logo_resolver import logo_url_for
    from aiogram.types import URLInputFile

    file_id = icon_file_id_for(item_name)
    photo = file_id if file_id else logo_url_for(item_name)
    if photo and not file_id:
        photo = URLInputFile(photo)

    is_callback = hasattr(target, 'message') and hasattr(target.message, 'edit_text')
    msg_obj = target.message if is_callback else target

    if photo:
        caption = text if len(text) <= _CAPTION_LIMIT else (text[:_CAPTION_LIMIT - 1] + "...")
        try:
            if is_callback:
                try:
                    await target.message.delete()
                except TelegramBadRequest:
                    pass
            await msg_obj.answer_photo(
                photo, caption=caption, reply_markup=markup, parse_mode="HTML"
            )
            return
        except Exception:
            # Any failure (bad image, network, Telegram reject) -> text fallback below
            pass

    # Text path (no logo, or photo failed)
    try:
        if is_callback:
            await target.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        else:
            await target.answer(text, reply_markup=markup, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            # edit_text can fail if the previous message was a photo -> send new
            try:
                await msg_obj.answer(text, reply_markup=markup, parse_mode="HTML")
            except TelegramBadRequest:
                raise


# --- Shared helper: price calculation with account & promo discount ---

async def get_effective_user_unit_price(user_id: int, base_price: Decimal, data: dict) -> tuple[Decimal, str | None]:
    """
    Calculate effective unit price considering both promo code and user profile account discount.
    Returns (effective_unit_price, discount_label_html).
    """
    from packages.database.methods import check_user_cached
    applied_promo = data.get('applied_promo')
    unit_price = base_price
    discount_label = None

    if applied_promo:
        promo_data = data.get('applied_promo_data', {})
        unit_price = apply_promo_discount(base_price, promo_data)
        saved = base_price - unit_price
        discount_label = f"🎁 <b>Coupon ({applied_promo}):</b> -{saved:g} USDT"
    else:
        user = await check_user_cached(user_id)
        discount_pct = float(user.get('discount_percent', 0)) if user else 0
        if discount_pct > 0:
            account_disc = Decimal(str(discount_pct)) / 100
            unit_price = (base_price * (1 - account_disc)).quantize(Decimal("0.01"))
            saved = base_price - unit_price
            discount_label = f"🏷️ <b>Account Discount ({discount_pct:g}% off):</b> <s>${base_price:g}</s> → <b>${unit_price:g} USDT</b> (Saved ${saved:g})"

    return unit_price, discount_label


# --- Shared helper: render item page ---

async def _render_item_page(
    target, state: FSMContext, item_name: str, back_data: str = None,
    user_id: int = None, reseller_product_id: int = None,
):
    """
    Render item detail page - supports both local DB items and reseller products.
    `target` can be CallbackQuery or Message.
    """
    data = await state.get_data()
    if not back_data:
        back_data = data.get('item_back_data', 'gp_0')

    user_id = user_id or target.from_user.id
    user_data = await check_user(user_id) or {}

    # --- Check if this is a reseller product -----------------------------------------------------------------------------------------
    reseller_product = await _get_current_reseller_product(
        item_name,
        {**data, "reseller_product_id": reseller_product_id or data.get("reseller_product_id")},
    )

    if reseller_product is not None:
        # Reseller product - price from external API
        price = Decimal(str(reseller_product.effective_sell_price))
        stock = reseller_product.stock
        ptype = reseller_product.product_type
        description = reseller_product.description or ""

        if stock is None or stock == -1:
            stock_label = "8"
            has_stock = True
        elif stock > 0:
            stock_label = str(stock)
            has_stock = True
        else:
            stock_label = "0"
            has_stock = False

        lines = [f"<b>{escape(item_name)}</b>\n"]
        if description:
            lines += [
                "<blockquote expandable>",
                "✅ <b>Description</b>",
                escape(description),
                "</blockquote>\n"
            ]
        
        if ptype in ("preorder", "team_invite"):
            lines.append("⚠️ <i>This is a pre-order. Credentials delivered within 24h of payment.</i>")
        else:
            lines.append("⚡ <i>Delivery is automatic after payment confirmation.</i>")
            
        unit_price, disc_label = await get_effective_user_unit_price(user_id, price, data)
        if disc_label:
            lines.append(f"\n{disc_label}")

        if not has_stock:
            lines.append("\n❌ <b>Out of Stock</b>")

        text = "\n".join(lines)

        markup = item_info(
            item_name=item_name,
            back_data=back_data,
            has_purchased=False,
            reviews_enabled=False,
            has_stock=has_stock,
            price=unit_price,
            stock_label=stock_label,
            applied_promo=data.get('applied_promo'),
        )

        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        else:
            await target.answer(text, reply_markup=markup, disable_web_page_preview=True)
        return

    # --- Local DB product ------------------------------------------------------------------
    item_info_data = await get_item_info_cached(item_name)
    if not item_info_data:
        if isinstance(target, CallbackQuery):
            await target.answer(localize("shop.item.not_found"), show_alert=True)
        else:
            await target.answer(localize("shop.item.not_found"))
        return

    is_unlimited = await check_value(item_name)
    quantity = await select_item_values_amount_cached(item_name)
    stock_label = "8" if is_unlimited else str(quantity)
    has_stock = is_unlimited or quantity > 0

    price = Decimal(str(item_info_data["price"]))
    unit_price, disc_label = await get_effective_user_unit_price(user_id, price, data)

    warranty = item_info_data.get("warranty") or "No warranty"
    description = item_info_data.get("description") or ""

    # --- Design board item detail format ---
    # Check if custom emoji is set for product or its category
    prod_emoji_id = item_info_data.get("icon_custom_emoji_id") or item_info_data.get("cat_icon_custom_emoji_id")
    if prod_emoji_id:
        icon_html = f'<tg-emoji emoji-id="{prod_emoji_id}">📦</tg-emoji> '
    else:
        icon_html = ""
        
    lines = [f"{icon_html}<b>{escape(item_name)}</b>\n"]
    if disc_label:
        lines.append(f"{disc_label}\n")

    # Bulk pricing tiers
    if not data.get('applied_promo'):
        lines += [
            "<blockquote expandable>",
            "🔥 <b>Special Offers</b>",
            f"🔹 Buy 1 for {unit_price:g} USDT each",
            f"🔹 Buy 5 for {unit_price * Decimal('0.95'):.2f} USDT each",
            f"🔹 Buy 10 for {unit_price * Decimal('0.90'):.2f} USDT each",
            "</blockquote>\n"
        ]

    if description:
        lines += [
            "<blockquote expandable>",
            "✅ <b>Description</b>",
            escape(description),
            "</blockquote>\n"
        ]

    if warranty and warranty != "No warranty":
        lines += [
            "<blockquote expandable>",
            "⚠️ <b>Instructions / Warranty</b>",
            escape(warranty),
            "</blockquote>\n"
        ]

    lines += [
        "⚡ <i>Delivery is automatic after payment confirmation.</i>",
    ]

    if not has_stock:
        lines.append("\n❌ <b>Out of Stock</b>")

    # Get review info
    avg_rating = await get_item_avg_rating(item_name)
    has_purchased_flag = await has_purchased_item(user_id, item_name)
    existing_review = await get_user_review(user_id, item_name)
    review_count = 0

    text = "\n".join(lines)
    markup = item_info(
        item_name=item_name,
        back_data=back_data,
        avg_rating=avg_rating,
        review_count=review_count,
        has_purchased=has_purchased_flag and not existing_review,
        applied_promo=data.get('applied_promo'),
        reviews_enabled=(EnvKeys.REVIEWS_ENABLED == "1"),
        has_stock=has_stock,
        price=unit_price,
        stock_label=stock_label,
    )

    await _send_detail(target, text, markup, item_name)


# --- Shop flat product view (no categories) ---



async def _render_flat_shop_page(
    target, state: FSMContext, page: int = 0, sort: str = "price",
    category: str = None, search_name: str = None
):
    """Render products (local + reseller) in a flat paginated list, optionally by category or name."""
    from packages.database.methods.lazy_queries import query_all_products_flat
    from apps.telegram_bot.utils.auto_icon import auto_icon

    # Build paginator over flat list
    async def _query(offset=0, limit=10, count_only=False):
        return await query_all_products_flat(
            offset=offset, limit=limit, count_only=count_only, sort=sort,
            category=category, search_name=search_name
        )

    paginator = LazyPaginator(_query, per_page=10)
    page_items = await paginator.get_page(page)
    total_pages = max(await paginator.get_total_pages(), 1)

    # Build keyboard
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    kb = InlineKeyboardBuilder()

    # Sort: in-stock items first, sold-out at the bottom (matches design board)
    def _has_stock(it: dict) -> bool:
        pt = it.get("product_type", "account")
        if pt in ("preorder", "team_invite"):
            return True
        if it.get("is_infinity"):
            return True
        s = it.get("stock")
        return s is None or s > 0

    page_items = sorted(page_items, key=lambda it: (0 if _has_stock(it) else 1))

    for i, item in enumerate(page_items):
        name = item["name"]
        price = item["price"]
        stock = item.get("stock")
        is_inf = item.get("is_infinity", False)
        ptype = item.get("product_type", "account")

        # Stock label matches design board: "(Stock: N)" or "(Stock: ∞)" or "(Stock: 0)"
        style = "success"
        if ptype in ("preorder", "team_invite"):
            stock_str = "Pre-order"
        elif is_inf:
            stock_str = "∞"
        elif stock is None:
            stock_str = "∞"
        else:
            stock_str = str(stock)
            if stock == 0:
                style = "danger"
            elif stock <= 5:
                style = "primary"

        db_icon = item.get("icon_custom_emoji_id")
        kwargs = {"style": style}
        if db_icon and str(db_icon).strip().isdigit():
            icon = ""
            kwargs["icon_custom_emoji_id"] = str(db_icon).strip()
        elif db_icon:
            icon = f"{db_icon} "
        else:
            icon = ""

        btn_text = f"{icon}{name} - {price:g} USDT (Stock: {stock_str})".strip()
        kb.button(text=btn_text, callback_data=f"itm:{i}:{page}", **kwargs)

    kb.adjust(1)

    # Pagination nav
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"gp_{page - 1}", style="primary"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page + 1} / {total_pages}", callback_data="noop", style="primary"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"gp_{page + 1}", style="primary"))
    if nav_buttons:
        kb.row(*nav_buttons)

    # Sort + Refresh row
    sort_label = "↕️ Sort: Price" if sort == "name" else "🔤 Sort: Name"
    next_sort = "price" if sort == "name" else "name"
    kb.row(
        InlineKeyboardButton(text="🔄 Refresh", callback_data=f"shop_refresh:{sort}", style="primary"),
        InlineKeyboardButton(text=sort_label, callback_data=f"shop_sort:{next_sort}", style="primary"),
    )
    # Back goes to the category menu when browsing a category, else to main menu
    if category:
        kb.row(InlineKeyboardButton(text="🗂️ Categories", callback_data="shop", style="primary"))
    else:
        kb.row(InlineKeyboardButton(text="🔙 " + localize("btn.back"), callback_data="back_to_menu", style="primary"))

    total_items = await query_all_products_flat(count_only=True, sort=sort, category=category, search_name=search_name)
    in_stock_count = sum(1 for it in page_items if _has_stock(it))
    
    # Try to find custom emoji for the category header
    cat_emoji_html = "🗂️"
    if category and page_items:
        for it in page_items:
            if it.get("category") == category and it.get("icon_custom_emoji_id"):
                cat_emoji_html = f'<tg-emoji emoji-id="{it["icon_custom_emoji_id"]}">🗂️</tg-emoji>'
                break
                
    title = f"{cat_emoji_html} <b>{escape(category)}</b>" if category else "🛍️ <b>Available Products:</b>"
    header = (
        f"{title}\n"
        f"<i>Showing {len(page_items)} of {total_items} products ({in_stock_count} in stock on this page)</i>"
    )

    await _edit_or_resend(target, header, kb.as_markup())

    await state.update_data(
        goods_page_items=list(page_items),
        goods_sort=sort,
        goods_category=category,
    )
    await state.set_state(ShopStates.viewing_goods)


@router.callback_query(F.data == "shop")
async def shop_callback_handler(call: CallbackQuery, state: FSMContext):
    """Show the category menu for the shop."""
    metrics = get_metrics()
    if metrics:
        metrics.track_conversion("purchase_funnel", "view_shop", call.from_user.id)

    from packages.database.methods.lazy_queries import query_product_categories, query_featured_items
    from apps.telegram_bot.keyboards.inline import shop_category_menu_keyboard
    from apps.telegram_bot.utils.loading import show_loading

    await show_loading(call, "Loading shop…")

    categories = await query_product_categories()
    featured_items = await query_featured_items()
    if not categories:
        await state.update_data(shop_flat_sort="price")
        await _render_flat_shop_page(call, state, page=0, sort="price")
        return

    total = sum(c[1] for c in categories)
    featured_note = " featured items are listed below." if featured_items else ""
    header = (
        f"🏪 <b>Choose a category</b> to browse products.{featured_note}\n"
        f"<i>{total} products across {len(categories)} categories 👉 pick one:</i>"
    )
    from apps.telegram_bot.utils.menu_icons import get_menu_icons
    icons = await get_menu_icons()
    await _edit_or_resend(call, header, shop_category_menu_keyboard(categories, featured_items, icons=icons))
    await state.update_data(goods_category=None)





@router.callback_query(F.data == "shop_all")
async def shop_all_handler(call: CallbackQuery, state: FSMContext):
    """Show the full flat product list (no category filter)."""
    data = await state.get_data()
    sort = data.get("goods_sort", "price")
    await _render_flat_shop_page(call, state, page=0, sort=sort, category=None)


@router.callback_query(F.data.startswith("shopcat:"))
async def shop_category_handler(call: CallbackQuery, state: FSMContext):
    """Show products within a single category."""
    category = call.data.split(":", 1)[1]
    data = await state.get_data()
    sort = data.get("goods_sort", "price")
    await _render_flat_shop_page(call, state, page=0, sort=sort, category=category)


@router.callback_query(F.data.startswith("shopcat_featured:") | F.data.startswith("sc_f:"))
async def shop_featured_item_handler(call: CallbackQuery, state: FSMContext):
    """Tapping a featured item — show the shop filtered to just that item name."""
    item_name = call.data.split(":", 1)[1]
    await state.update_data(shop_flat_sort="price")
    await _render_flat_shop_page(call, state, page=0, sort="price", search_name=item_name)


@router.callback_query(F.data.startswith("gp_"))
async def navigate_goods(call: CallbackQuery, state: FSMContext):
    """Flat product list pagination."""
    try:
        page = int(call.data[3:])
    except ValueError:
        page = 0
    data = await state.get_data()
    sort = data.get("goods_sort", "name")
    category = data.get("goods_category")
    await _render_flat_shop_page(call, state, page=page, sort=sort, category=category)


@router.callback_query(F.data.startswith("shop_sort:"))
async def shop_sort_handler(call: CallbackQuery, state: FSMContext):
    """Toggle sort between name and price."""
    new_sort = call.data.split(":")[1]
    data = await state.get_data()
    category = data.get("goods_category")
    await _render_flat_shop_page(call, state, page=0, sort=new_sort, category=category)


@router.callback_query(F.data.startswith("shop_refresh:"))
async def shop_refresh_handler(call: CallbackQuery, state: FSMContext):
    """Refresh the current product list."""
    data = await state.get_data()
    sort = data.get("goods_sort", "name")
    category = data.get("goods_category")
    await _render_flat_shop_page(call, state, page=0, sort=sort, category=category)
    await call.answer("✅ Refreshed!")



@router.callback_query(F.data.startswith('itm:'))
async def item_info_callback_handler(call: CallbackQuery, state: FSMContext):
    """
    Show item detail page. Format: itm:{index}:{page}
    """
    parts = call.data.split(':')
    idx = int(parts[1])
    goods_page = int(parts[2]) if len(parts) > 2 else 0

    data = await state.get_data()
    goods_page_items = data.get('goods_page_items', [])

    if idx < 0 or idx >= len(goods_page_items):
        await call.answer(localize("shop.item.not_found"), show_alert=True)
        return

    raw = goods_page_items[idx]
    item_name = raw["name"] if isinstance(raw, dict) else raw
    item_source = raw.get("source", "local") if isinstance(raw, dict) else "local"
    reseller_product_id = raw.get("reseller_product_id") if isinstance(raw, dict) else None
    back_data = f"gp_{goods_page}"

    metrics = get_metrics()
    if metrics:
        metrics.track_conversion("purchase_funnel", "view_item", call.from_user.id)

    await state.update_data(
        csrf_item=item_name, item_back_data=back_data, item_qty=1,
        item_source=item_source, reseller_product_id=reseller_product_id,
    )
    await _render_item_page(
        call, state, item_name, back_data, user_id=call.from_user.id,
        reseller_product_id=reseller_product_id,
    )


# --- Quantity selection (design board grid) ---

@router.callback_query(F.data == "buy_now")
async def buy_callback_handler(call: CallbackQuery, state: FSMContext):
    """
    Show quantity selector grid.
    Triggered by 🛒 Buy Now on the item detail page - works for both local and reseller items.
    """
    data = await state.get_data()
    item_name = data.get('csrf_item')
    if not item_name:
        await call.answer(localize("shop.item.not_found"), show_alert=True)
        return

    # Check reseller product first
    reseller_product = await _get_current_reseller_product(item_name, data)

    if reseller_product is not None:
        # Reseller item
        price = Decimal(str(reseller_product.effective_sell_price))
        unit_price, disc_label = await get_effective_user_unit_price(call.from_user.id, price, data)
        stock = reseller_product.stock
        max_stock = stock if (stock is not None and stock > 0) else 999
        markup = quantity_selector_keyboard(back_cb="back_to_item", max_stock=max_stock)
        disc_str = f"\n{disc_label}" if disc_label else ""
        text = (
            f"📦 <b>{escape(item_name)}</b>\n"
            f"💰 <b>Price:</b> {unit_price:g} USDT / item{disc_str}\n\n"
            f"🔢 <b>Select Quantity:</b>"
        )
        await _edit_or_resend(call, text, markup)
        await state.update_data(item_qty=1, is_reseller_item=True)
        return

    # Local DB item
    item_info_data = await get_item_info_cached(item_name)
    if not item_info_data:
        await call.answer(localize("shop.item.not_found"), show_alert=True)
        return

    is_unlimited = await check_value(item_name)
    stock = await select_item_values_amount_cached(item_name)
    max_stock = 999 if is_unlimited else stock

    markup = quantity_selector_keyboard(back_cb="back_to_item", max_stock=max_stock)
    price = Decimal(str(item_info_data["price"]))
    unit_price, disc_label = await get_effective_user_unit_price(call.from_user.id, price, data)
    disc_str = f"\n{disc_label}" if disc_label else ""
    text = (
        f"📦 <b>{escape(item_name)}</b>\n"
        f"💰 <b>Price:</b> {unit_price:g} USDT / code{disc_str}\n\n"
        f"🔢 <b>Select Quantity:</b>"
    )
    await _edit_or_resend(call, text, markup)
    await state.update_data(item_qty=1, is_reseller_item=False)


@router.callback_query(F.data.startswith("set_qty:"))
async def set_qty_handler(call: CallbackQuery, state: FSMContext):
    """Set quantity from grid button."""
    qty = int(call.data.split(":")[1])
    await state.update_data(item_qty=qty)
    data = await state.get_data()
    item_name = data.get('csrf_item', '')

    reseller_product = await _get_current_reseller_product(item_name, data)

    if reseller_product is not None:
        price = Decimal(str(reseller_product.effective_sell_price))
        stock = reseller_product.stock
        max_stock = stock if (stock is not None and stock > 0) else 999
    else:
        item_info_data = await get_item_info_cached(item_name)
        if not item_info_data:
            return
        is_unlimited = await check_value(item_name)
        stock = await select_item_values_amount_cached(item_name)
        max_stock = 999 if is_unlimited else stock
        price = Decimal(str(item_info_data["price"]))

    unit_price, disc_label = await get_effective_user_unit_price(call.from_user.id, price, data)
    total = (unit_price * qty).quantize(Decimal("0.01"))
    disc_str = f"\n{disc_label}" if disc_label else ""

    text = (
        f"📦 <b>{escape(item_name)}</b>\n"
        f"💰 <b>Unit Price:</b> ${unit_price:g} USDT\n"
        f"🔢 <b>Selected Qty:</b> {qty} (Total: <b>${total:g} USDT</b>){disc_str}\n\n"
        f"🔢 <b>Select Quantity:</b>"
    )

    markup = quantity_selector_keyboard(back_cb="back_to_item", max_stock=max_stock)
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == "confirm_qty")
async def confirm_qty_handler(call: CallbackQuery, state: FSMContext):
    """Show order summary after quantity is confirmed."""
    data = await state.get_data()
    item_name = data.get('csrf_item')
    qty = data.get('item_qty', 1)

    if not item_name or qty < 1:
        await call.answer("Please select a quantity first.", show_alert=True)
        return

    # Resolve price -> reseller or local
    reseller_product = await _get_current_reseller_product(item_name, data)

    if reseller_product is not None:
        price = Decimal(str(reseller_product.effective_sell_price))
    else:
        item_info_data = await get_item_info_cached(item_name)
        if not item_info_data:
            await call.answer(localize("shop.item.not_found"), show_alert=True)
            return
        price = Decimal(str(item_info_data["price"]))

    unit_price, disc_label = await get_effective_user_unit_price(call.from_user.id, price, data)
    total = (unit_price * qty).quantize(Decimal("0.01"))

    text = (
        f"🧾 <b>Order Summary</b>\n\n"
        f"🛍️ <b>Product:</b> {escape(item_name)}\n"
        f"🔢 <b>Quantity:</b> {qty}\n"
        f"💲 <b>Unit Price:</b> ${unit_price:g} USDT\n"
        f"💰 <b>Total:</b> ${total:g} USDT\n"
    )
    if disc_label:
        text += f"{disc_label}\n"
    text += "\n<i>Delivery is automatic after payment confirmation.</i>"

    markup = order_summary_keyboard()
    await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await state.update_data(order_total=str(total), order_qty=qty)


@router.callback_query(F.data == "select_payment")
async def select_payment_handler(call: CallbackQuery, state: FSMContext):
    """
    Wallet-first checkout: if the user has enough balance, run the purchase
    straight from the wallet. Otherwise show an 'insufficient -> top up first'
    screen with a Top Up button.
    """
    from apps.telegram_bot.keyboards.inline import insufficient_balance_keyboard
    from apps.telegram_bot.handlers.user.balance_and_payment import buy_item_callback_handler

    data = await state.get_data()
    item_name = data.get('csrf_item', 'Unknown')
    total_str = data.get('order_total', '0')
    try:
        total = Decimal(str(total_str))
    except Exception:
        total = Decimal('0')

    user_data = await check_user(call.from_user.id) or {}
    balance = Decimal(str(user_data.get('balance', 0)))

    if balance >= total:
        # Enough funds -> buy directly from the wallet.
        await state.update_data(amount=str(total))
        await buy_item_callback_handler(call, state)
        return

    # Insufficient -> nudge to top up first.
    shortfall = (total - balance).quantize(Decimal('0.01'))
    text = (
        f"❌ <b>Insufficient Wallet Balance</b>\n\n"
        f"📦 <b>{escape(item_name)}</b>\n"
        f"🧾 <b>Order Total:</b> {total:g} USDT\n"
        f"💳 <b>Your Wallet:</b> {balance:g} USDT\n"
        f"⚠️ <b>Need to top up:</b> {shortfall:g} USDT\n\n"
        f"<i>Please top up your wallet first, then come back and complete the purchase.</i>"
    )
    try:
        await call.message.edit_text(text, reply_markup=insufficient_balance_keyboard(), parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.callback_query(F.data == "change_qty")
async def change_qty_handler(call: CallbackQuery, state: FSMContext):
    """Go back to quantity selector from order summary or payment screen."""
    data = await state.get_data()
    item_name = data.get('csrf_item')
    if not item_name:
        await call.answer("Session expired. Please go back to the shop.", show_alert=True)
        return

    qty = data.get('item_qty', 1)

    # Resolve for reseller or local
    reseller_product = await _get_current_reseller_product(item_name, data)

    if reseller_product is not None:
        price = Decimal(str(reseller_product.effective_sell_price))
        stock = reseller_product.stock
        max_stock = stock if (stock is not None and stock > 0) else 999
    else:
        item_info_data = await get_item_info_cached(item_name)
        if not item_info_data:
            await call.answer(localize("shop.item.not_found"), show_alert=True)
            return
        is_unlimited = await check_value(item_name)
        stock = await select_item_values_amount_cached(item_name)
        max_stock = 999 if is_unlimited else stock
        price = Decimal(str(item_info_data["price"]))

    text = (
        f"📦 <b>{escape(item_name)}</b>\n"
        f"💰 <b>Price:</b> {price:g} USDT / item\n\n"
        f"🔢 <b>Current Qty: {qty}</b>\n"
        f"🔢 <b>Select Quantity:</b>"
    )
    markup = quantity_selector_keyboard(back_cb="back_to_item", max_stock=max_stock)
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == 'view_note')
async def view_note_handler(call: CallbackQuery, state: FSMContext):
    """Show admin note for the product."""
    data = await state.get_data()
    item_name = data.get('csrf_item', '')
    item_data = await get_item_info(item_name)
    note = item_data.get('note') if item_data else None
    if not note:
        await call.answer("\U0001f4cb No note from admin for this product.", show_alert=True)
        return
    await _edit_or_resend(
        call,
        f"\U0001f4dd <b>Note from Admin:</b>\n\n{note}",
        back(data.get('item_back_data', 'back_to_item')),
    )


@router.callback_query(F.data == 'share_item')
async def share_item_handler(call: CallbackQuery, state: FSMContext):
    """Generate a shareable deep link for the product."""
    data = await state.get_data()
    item_name = data.get('csrf_item', '')
    bot_info = await call.bot.get_me()
    bot_username = bot_info.username
    # encode item name for deep link
    import urllib.parse
    encoded = urllib.parse.quote(item_name)
    link = f"https://t.me/{bot_username}?start=item_{encoded}"
    await call.answer(f"\U0001f517 Share: {link}", show_alert=True)



# --- Promo Code Application ---

@router.callback_query(F.data == "apply_promo")
async def apply_promo_handler(call: CallbackQuery, state: FSMContext):
    await _edit_or_resend(call, localize("promo.enter_code"), back("back_to_item"))
    await state.update_data(awaiting_promo=True)


@router.callback_query(F.data == "remove_promo")
async def remove_promo_handler(call: CallbackQuery, state: FSMContext):
    await state.update_data(applied_promo=None, applied_promo_data=None)
    data = await state.get_data()
    item_name = data.get('csrf_item')
    if item_name:
        await _render_item_page(
            call, state, item_name, user_id=call.from_user.id,
            reseller_product_id=data.get("reseller_product_id"),
        )
    else:
        await call.answer(localize("promo.removed"))


@router.callback_query(F.data == "back_to_item")
async def back_to_item_handler(call: CallbackQuery, state: FSMContext):
    """Return to item page, preserving promo state."""
    data = await state.get_data()
    item_name = data.get('csrf_item')
    if not item_name:
        # Fallback
        await call.message.edit_text(
            localize("shop.item.not_found"),
            reply_markup=back("back_to_menu"),
        )
        return
    await state.update_data(awaiting_promo=False)
    await _render_item_page(
        call, state, item_name, user_id=call.from_user.id,
        reseller_product_id=data.get("reseller_product_id"),
    )


# --- Balance Promo Redemption (from profile) ---

@router.callback_query(F.data == "redeem_promo")
async def redeem_promo_handler(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(localize("promo.enter_redeem_code"), reply_markup=back("profile"))
    await state.set_state(PromoFSM.waiting_redeem_code)


@router.message(PromoFSM.waiting_redeem_code, F.text)
async def redeem_promo_code_handler(message: Message, state: FSMContext):
    code = (message.text or "").strip().upper()
    success, result_type, amount = await redeem_balance_promo(code, message.from_user.id)

    if success:
        if result_type == "account_upgrade":
            text = (
                f"<b>Account Upgraded!</b>\n\n"
                f"Code <code>{code}</code> applied.\n"
                f"You now get <b>{amount}% off</b> on every purchase automatically."
            )
        else:
            text = localize(
                "promo.balance_redeemed", code=code,
                amount=amount, currency=EnvKeys.PAY_CURRENCY,
            )
        await message.answer(text, parse_mode="HTML", reply_markup=back("profile"))
        await log_audit(
            "promo_redeem", user_id=message.from_user.id,
            resource_type="PromoCode", resource_id=code,
        )
        from apps.telegram_bot.utils.notify import notify_group
        await notify_group(
            message.bot,
            f"🎁 <b>Promo Redeemed</b>\n\n"
            f"👤 User: <a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a> (ID: <code>{message.from_user.id}</code>)\n"
            f"🎟 Code: <code>{code}</code>\n"
            f"💵 Added: <b>{amount}</b> ({'USDT' if result_type != 'account_upgrade' else '% discount'})"
        )
    else:
        await message.answer(localize(result_type), reply_markup=back("profile"))

    await state.clear()


# --- Review Handlers ---

@router.callback_query(F.data.startswith("review:"))
async def start_review_handler(call: CallbackQuery, state: FSMContext):
    if EnvKeys.REVIEWS_ENABLED != "1":
        await call.answer(localize("review.disabled"), show_alert=True)
        return

    item_name = call.data.split(":", 1)[1]

    # Check if user purchased the item
    purchased = await has_purchased_item(call.from_user.id, item_name)
    if not purchased:
        await call.answer(localize("review.not_purchased"), show_alert=True)
        return

    # Check if already reviewed
    existing = await get_user_review(call.from_user.id, item_name)
    if existing:
        await call.answer(localize("review.already_exists"), show_alert=True)
        return

    await state.update_data(review_item_name=item_name)
    await _edit_or_resend(
        call,
        localize("review.prompt_rating", name=item_name),
        rating_keyboard(item_name),
    )
    await state.set_state(ReviewFSM.waiting_rating)


@router.callback_query(F.data.startswith("rating:"), ReviewFSM.waiting_rating)
async def receive_rating_handler(call: CallbackQuery, state: FSMContext):
    rating = int(call.data.split(":")[1])
    await state.update_data(review_rating=rating)

    buttons = [
        (localize("btn.skip_review_text"), "skip_review_text"),
        (localize("btn.back"), "back_to_menu"),
    ]
    await call.message.edit_text(
        localize("review.prompt_text"),
        reply_markup=simple_buttons(buttons),
    )
    await state.set_state(ReviewFSM.waiting_text)


@router.callback_query(F.data == "skip_review_text", ReviewFSM.waiting_text)
async def skip_review_text_handler(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    item_name = data.get('review_item_name')
    rating = data.get('review_rating')

    await create_review(call.from_user.id, item_name, rating)
    await invalidate_rating_cache(item_name)
    await call.message.edit_text(localize("review.created"), reply_markup=back("back_to_menu"))
    await state.clear()


@router.message(ReviewFSM.waiting_text, F.text)
async def receive_review_text_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    item_name = data.get('review_item_name')
    rating = data.get('review_rating')
    text = (message.text or "")[:500].strip()

    await create_review(message.from_user.id, item_name, rating, text)
    await invalidate_rating_cache(item_name)
    await message.answer(localize("review.created"), reply_markup=back("back_to_menu"))
    await state.clear()


# --- Promo code text input (catch-all, must be AFTER state-specific message handlers) ---

@router.message(F.text)
async def promo_code_text_handler(message: Message, state: FSMContext):
    """Handle promo code text input when awaiting_promo is set."""
    data = await state.get_data()
    if not data.get('awaiting_promo'):
        return  # Not awaiting promo input — skip

    item_name = data.get('csrf_item')
    if not item_name:
        await state.update_data(awaiting_promo=False)
        return

    code = (message.text or "").strip().upper()
    valid, error_key, promo_data = await validate_promo_for_item(code, item_name, message.from_user.id)

    if not valid:
        await message.answer(localize(error_key), reply_markup=back("back_to_item"))
        await state.update_data(awaiting_promo=False)
        return

    # Store promo data for discounted price display
    await state.update_data(
        applied_promo=code,
        applied_promo_data={
            'discount_type': promo_data.get('discount_type'),
            'discount_value': str(promo_data.get('discount_value', 0)),
        },
        awaiting_promo=False,
    )

    # Re-render item page with discounted price
    await _render_item_page(
        message, state, item_name, user_id=message.from_user.id,
        reseller_product_id=(await state.get_data()).get("reseller_product_id"),
    )


# --- View Reviews ---

@router.callback_query(F.data.startswith("reviews:"))
async def view_reviews_handler(call: CallbackQuery, state: FSMContext):
    if EnvKeys.REVIEWS_ENABLED != "1":
        await call.answer(localize("review.disabled"), show_alert=True)
        return

    parts = call.data.split(":")
    item_name = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0

    paginator = LazyPaginator(
        partial(query_item_reviews, item_name),
        per_page=5,
    )

    reviews = await paginator.get_page(page)
    total_pages = await paginator.get_total_pages()

    if not reviews:
        await _edit_or_resend(call, localize("review.list_empty"), back("back_to_item"))
        return

    lines = [localize("review.list_title", name=item_name), ""]
    for r in reviews:
        if r.get('text'):
            lines.append(localize("review.item", rating=r['rating'], text=r['text'][:100]))
        else:
            lines.append(localize("review.item_no_text", rating=r['rating']))

    # Navigation
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    kb = InlineKeyboardBuilder()
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"reviews:{item_name}:{page - 1}"))
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"reviews:{item_name}:{page + 1}"))
    if nav_buttons:
        kb.row(*nav_buttons)
    kb.row(InlineKeyboardButton(text=localize("btn.back"), callback_data="back_to_item"))

    await _edit_or_resend(call, "\n".join(lines), kb.as_markup())


# --- Bought items ---

@router.callback_query(F.data == "bought_items")
async def bought_items_callback_handler(call: CallbackQuery, state: FSMContext):
    """
    Show list of user's purchased items with lazy loading.
    """
    from apps.telegram_bot.utils.loading import show_loading
    await show_loading(call, "Loading your purchase history…")

    user_id = call.from_user.id

    # Create paginator for user's bought items
    query_func = partial(query_user_bought_items, user_id)
    paginator = LazyPaginator(query_func, per_page=10)

    markup = await lazy_paginated_keyboard(
        paginator=paginator,
        item_text=lambda item: item.item_name,
        item_callback=lambda item: f"bought-item:{item.id}:bought-goods-page_user_0",
        page=0,
        back_cb="profile",
        nav_cb_prefix="bought-goods-page_user_"
    )

    await call.message.edit_text(localize("purchases.title"), reply_markup=markup)

    # Save paginator state
    await state.update_data(bought_items_paginator=paginator.get_state())



@router.callback_query(F.data.startswith('bought-goods-page_'))
async def navigate_bought_items(call: CallbackQuery, state: FSMContext):
    """
    Pagination for user's purchased items with lazy loading.
    Format: 'bought-goods-page_{data}_{page}', where data = 'user' or user_id.
    """
    parts = call.data.split('_')
    if len(parts) < 3:
        await call.answer(localize("purchases.pagination.invalid"))
        return

    data_type = parts[1]
    try:
        current_index = int(parts[2])
    except ValueError:
        current_index = 0

    if data_type == 'user':
        user_id = call.from_user.id
        back_cb = 'profile'
        pre_back = f'bought-goods-page_user_{current_index}'
    else:
        user_id = int(data_type)
        back_cb = f'check-user_{data_type}'
        pre_back = f'bought-goods-page_{data_type}_{current_index}'

    # Get saved state
    data = await state.get_data()
    paginator_state = data.get('bought_items_paginator')

    # Create paginator with cached state
    query_func = partial(query_user_bought_items, user_id)
    paginator = LazyPaginator(query_func, per_page=10, state=paginator_state)

    markup = await lazy_paginated_keyboard(
        paginator=paginator,
        item_text=lambda item: item.item_name,
        item_callback=lambda item: f"bought-item:{item.id}:{pre_back}",
        page=current_index,
        back_cb=back_cb,
        nav_cb_prefix=f"bought-goods-page_{data_type}_"
    )

    await call.message.edit_text(localize("purchases.title"), reply_markup=markup)

    # Update state
    await state.update_data(bought_items_paginator=paginator.get_state())


@router.callback_query(F.data.startswith('bought-item:'))
async def bought_item_info_callback_handler(call: CallbackQuery):
    """
    Show details for a purchased item.
    """
    trash, item_id, back_data = call.data.split(':', 2)
    item = await get_bought_item_info(int(item_id))
    if not item:
        await call.answer(localize("purchases.item.not_found"), show_alert=True)
        return

    text = "\n".join([
        localize("purchases.item.name", name=item["item_name"]),
        localize("purchases.item.price", amount=item["price"], currency=EnvKeys.PAY_CURRENCY),
        localize("purchases.item.datetime", dt=item["bought_datetime"]),
        localize("purchases.item.unique_id", uid=item["unique_id"]),
        localize("purchases.item.value", value=item["value"]),
    ])
    await call.message.edit_text(text, parse_mode='HTML', reply_markup=back(back_data))
@router.callback_query(F.data == "shop_review_up")
async def shop_review_up_handler(call: CallbackQuery):
    await call.answer(localize("shop.review.thanks", default="Thank you for your feedback! ❤️"), show_alert=True)
    try:
        await call.message.delete()
    except Exception:
        pass

@router.callback_query(F.data == "shop_review_down")
async def shop_review_down_handler(call: CallbackQuery):
    await call.answer(localize("shop.review.thanks", default="Thank you for your feedback! ❤️"), show_alert=True)
    try:
        await call.message.delete()
    except Exception:
        pass


async def navigate_categories(call: CallbackQuery, state: FSMContext):
    """Legacy helper for category pagination."""
    await shop_callback_handler(call, state)


async def items_list_callback_handler(call: CallbackQuery, state: FSMContext):
    """Legacy helper for item listing."""
    parts = call.data.split(":")
    idx = int(parts[1]) if len(parts) > 1 else 0
    data = await state.get_data()
    cats = data.get("category_page_items", [])
    if idx < 0 or idx >= len(cats):
        await call.answer(localize("shop.category.not_found"), show_alert=True)
        return
    cat = cats[idx]
    await state.update_data(current_category=cat)
    await _render_flat_shop_page(call, state, page=0, category=cat)
