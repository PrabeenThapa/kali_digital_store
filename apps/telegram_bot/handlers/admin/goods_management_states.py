"""
Admin — Product Management (redesigned)
=========================================
Browse products visually → click to manage.
No more typing product names for delete/stock-add.
"""
from functools import partial

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from apps.telegram_bot.handlers.other import generate_short_hash
from apps.telegram_bot.i18n import localize
from packages.database.models import Permission
from packages.database.methods import (
    get_item_info_cached, delete_item, get_goods_info,
    delete_item_from_position, query_items_in_position,
    add_values_to_item,
)
from packages.database.methods.lazy_queries import query_all_goods_with_stock
from apps.telegram_bot.keyboards.inline import back, simple_buttons, lazy_paginated_keyboard
from packages.database.methods.audit import log_audit
from apps.telegram_bot.filters import HasPermissionFilter
from packages.config.config import EnvKeys
from apps.telegram_bot.utils.paginator import LazyPaginator
from apps.telegram_bot.states import GoodsFSM
from apps.telegram_bot.states.goods import UpdateItemFSM

router = Router()


# ─────────────────────────────────────────────────────────────
#  MAIN GOODS MANAGEMENT MENU
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == 'goods_management', HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def goods_management_callback_handler(call: CallbackQuery, state):
    """Main product management menu — visual overview."""
    await state.clear()

    # Quick stock summary
    from packages.database.methods.lazy_queries import query_all_goods_with_stock
    total_products = await query_all_goods_with_stock(count_only=True)
    first_page = await query_all_goods_with_stock(offset=0, limit=100)
    out_of_stock = sum(
        1 for p in first_page
        if not p["is_infinity"] and p["stock"] == 0
    )
    low_stock = sum(
        1 for p in first_page
        if not p["is_infinity"] and 0 < p["stock"] <= 3
    )

    header = (
        f"🗂 <b>Product Management</b>\n\n"
        f"📦 Total Products: <b>{total_products}</b>\n"
        f"🔴 Out of Stock: <b>{out_of_stock}</b>\n"
        f"🟡 Low Stock (≤3): <b>{low_stock}</b>"
    )

    actions = [
        ("📋 Browse & Manage Products", "admin_browse_products"),
        ("➕ Add New Product",          "add_item"),
        ("📥 Add Stock to Product",     "admin_stock_add_browse"),
        ("🗑 Delete a Product",         "admin_delete_browse"),
        ("👁 View Stock Items",         "show__items_in_position"),
        ("⬅️ Back",                    "console"),
    ]
    markup = simple_buttons(actions, per_row=1)
    await call.message.edit_text(header, reply_markup=markup, parse_mode="HTML")


# ─────────────────────────────────────────────────────────────
#  BROWSE & MANAGE PRODUCTS  (click → product detail page)
# ─────────────────────────────────────────────────────────────

def _admin_products_keyboard(products: list[dict], page: int, total_pages: int) -> object:
    """Build the product browser keyboard for admins."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    kb = InlineKeyboardBuilder()
    for p in products:
        if p["is_infinity"]:
            icon = "♾"
        elif p["stock"] is None:  # Reseller preorder/unlimited
            icon = "♾"
        elif p["stock"] == 0:
            icon = "🔴"
        elif p["stock"] <= 3:
            icon = "🟡"
        else:
            icon = "🟢"
            
        # Optional indicator for disabled reseller products
        disabled_str = ""
        if p.get("source") == "resell" and not p.get("is_enabled"):
            disabled_str = " (Disabled)"
            
        label = f"{icon} {p['name']}  (${p['price']:.2f}){disabled_str}"
        if p["source"] == "local":
            cb = f"aprod:{p['id']}"
        else:
            cb = f"rs_product:{p['id']}"
        kb.button(text=label, callback_data=cb)
    kb.adjust(1)

    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀ Prev", callback_data=f"abrowse_page:{page-1}"))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="Next ▶", callback_data=f"abrowse_page:{page+1}"))
        kb.row(*nav)

    kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="goods_management"))
    return kb.as_markup()


@router.callback_query(F.data == 'admin_browse_products', HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_browse_products(call: CallbackQuery, state: FSMContext):
    """Show paged product list — click any product to manage it."""
    from packages.database.methods.lazy_queries import query_admin_all_products_flat
    paginator = LazyPaginator(query_admin_all_products_flat, per_page=8)
    page_items = await paginator.get_page(0)
    total_pages = max(await paginator.get_total_pages(), 1)

    markup = _admin_products_keyboard(page_items, 0, total_pages)
    await call.message.edit_text(
        "📋 <b>All Products</b>\n<i>Tap a product to view details, add stock, or delete it.</i>\n\n"
        "🟢 In Stock  🟡 Low (≤3)  🔴 Out  ♾ Unlimited",
        reply_markup=markup, parse_mode="HTML"
    )
    await state.update_data(admin_prod_paginator=paginator.get_state())


@router.callback_query(F.data.startswith("abrowse_page:"), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_browse_page(call: CallbackQuery, state: FSMContext):
    """Paginate the admin product browser."""
    from packages.database.methods.lazy_queries import query_admin_all_products_flat
    page = int(call.data.split(":")[1])
    data = await state.get_data()
    paginator = LazyPaginator(query_admin_all_products_flat, per_page=8, state=data.get("admin_prod_paginator"))

    page_items = await paginator.get_page(page)
    total_pages = max(await paginator.get_total_pages(), 1)
    markup = _admin_products_keyboard(page_items, page, total_pages)

    try:
        await call.message.edit_text(
            "📋 <b>All Products</b>\n<i>Tap a product to view details, add stock, or delete it.</i>\n\n"
            "🟢 In Stock  🟡 Low (≤3)  🔴 Out  ♾ Unlimited",
            reply_markup=markup, parse_mode="HTML"
        )
    except Exception:
        pass
    await state.update_data(admin_prod_paginator=paginator.get_state())


@router.callback_query(F.data.startswith("aprod:"), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_product_detail(call: CallbackQuery, state: FSMContext):
    """
    Product detail page for admin.
    Shows all info + action buttons: Add Stock | Delete Product | View Stock Items | Back
    """
    product_id = int(call.data.split(":")[1])

    # Fetch product info via DB
    from sqlalchemy import select
    from packages.database import Database
    from packages.database.models import Goods, Categories, ItemValues
    from sqlalchemy import func

    async with Database().session() as s:
        row = (await s.execute(
            select(Goods.id, Goods.name, Goods.price, Goods.description,
                   Goods.warranty, Goods.note, Goods.is_featured, Categories.name.label("category"))
            .join(Categories, Categories.id == Goods.category_id)
            .where(Goods.id == product_id)
        )).first()

        if not row:
            await call.answer("Product not found.", show_alert=True)
            return

        stock_count = (await s.execute(
            select(func.count(ItemValues.id))
            .where(ItemValues.item_id == product_id, ItemValues.is_infinity == False)  # noqa
        )).scalar() or 0

        is_infinity = (await s.execute(
            select(func.count(ItemValues.id))
            .where(ItemValues.item_id == product_id, ItemValues.is_infinity == True)  # noqa
        )).scalar() or 0

    stock_label = "♾ Unlimited" if is_infinity else f"{stock_count} codes"
    if not is_infinity:
        stock_icon = "🟢" if stock_count > 3 else ("🟡" if stock_count > 0 else "🔴")
    else:
        stock_icon = "♾"

    text = (
        f"📦 <b>{row.name}</b>\n"
        f"📂 Category: <b>{row.category}</b>\n"
        f"💰 Price: <b>${row.price:.2f} {EnvKeys.PAY_CURRENCY}</b>\n"
        f"{stock_icon} Stock: <b>{stock_label}</b>\n\n"
        f"📝 <i>{row.description or 'No description'}</i>\n"
        f"🛡 Warranty: {row.warranty or 'None'}"
    )

    await state.update_data(
        manage_product_id=product_id,
        manage_product_name=row.name,
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    kb = InlineKeyboardBuilder()
    
    feat_text = "⭐ Remove Featured" if row.is_featured else "⭐ Make Featured"
    kb.button(text=feat_text, callback_data=f"aprod_feat:{product_id}")
    
    kb.button(text="📥 Add Stock",   callback_data=f"astockadd:{product_id}")
    kb.button(text="👁 View Stock",  callback_data=f"aviewstock:{product_id}")
    kb.button(text="✏️ Edit",      callback_data=f"aedit:{product_id}")
    kb.button(text="🏷 Set Icon",  callback_data=f"aicon:{product_id}")
    kb.button(text="🗑 Delete",    callback_data=f"adelete:{product_id}")
    kb.adjust(1, 2, 2, 1)
    kb.row(InlineKeyboardButton(text="⬅️ Back to Products", callback_data="admin_browse_products"))

    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("aprod_feat:"), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_toggle_featured_local(call: CallbackQuery, state: FSMContext):
    """Toggle the is_featured flag for a local product."""
    product_id = int(call.data.split(":")[1])
    from packages.database.models import Goods
    from packages.database import Database
    from sqlalchemy import select

    async with Database().session() as s:
        product = (await s.execute(select(Goods).where(Goods.id == product_id))).scalars().first()
        if product:
            product.is_featured = not getattr(product, "is_featured", False)
            await s.commit()
            
# Refresh the same page
    new_call = call.model_copy(update={'data': f"aprod:{product_id}"})
    await admin_product_detail(new_call, state)


# ─────────────────────────────────────────────────────────────
#  SET CUSTOM ICON (LOCAL PRODUCT)
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("aicon:"), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_prod_set_icon(call: CallbackQuery, state: FSMContext):
    product_id = int(call.data.split(":")[1])
    data = await state.get_data()
    product_name = data.get("manage_product_name", f"Product #{product_id}")
    
    await state.update_data(manage_product_id=product_id)
    await call.message.edit_text(
        f"Send the custom premium emoji you want to use for <b>{product_name}</b>.",
        reply_markup=back(f"aprod:{product_id}"),
        parse_mode="HTML"
    )
    await state.set_state(UpdateItemFSM.waiting_item_icon)

@router.message(UpdateItemFSM.waiting_item_icon, F.text)
async def process_prod_icon(message: Message, state: FSMContext):
    data = await state.get_data()
    product_id = data.get("manage_product_id")
    
    custom_emoji_id = None
    entities = message.entities or message.caption_entities or []
    for entity in entities:
        if entity.type == "custom_emoji":
            custom_emoji_id = entity.custom_emoji_id
            break
    if not custom_emoji_id and hasattr(message, "sticker") and message.sticker:
        custom_emoji_id = getattr(message.sticker, "custom_emoji_id", None)
                
    if not custom_emoji_id:
        await message.answer(
            "I couldn't find a custom premium emoji in your message. Please send one, or press Back.",
            reply_markup=back(f"aprod:{product_id}")
        )
        return
        
    from packages.database.engine import Database
    from sqlalchemy import update
    from packages.database.models.main import Goods
    async with Database().session() as s:
        await s.execute(update(Goods).where(Goods.id == product_id).values(icon_custom_emoji_id=custom_emoji_id))
        await s.commit()
        
    await message.answer(
        f"✅ <b>Custom icon saved!</b>",
        reply_markup=back(f"aprod:{product_id}"),
        parse_mode="HTML"
    )
    await state.clear()


# ─────────────────────────────────────────────────────────────
#  ADD STOCK — Browse → click product → paste codes
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == 'admin_stock_add_browse', HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_stock_add_browse(call: CallbackQuery, state: FSMContext):
    """Browse products to pick one for adding stock."""
    await _render_stock_add_page(call, state, 0)


async def _render_stock_add_page(call: CallbackQuery, state: FSMContext, page: int):
    """Render the stock-add product browser at a given page."""
    paginator = LazyPaginator(query_all_goods_with_stock, per_page=8)
    page_items = await paginator.get_page(page)
    total_pages = max(await paginator.get_total_pages(), 1)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    kb = InlineKeyboardBuilder()
    for p in page_items:
        icon = "♾" if p["is_infinity"] else ("🔴" if p["stock"] == 0 else ("🟡" if p["stock"] <= 3 else "🟢"))
        kb.button(text=f"{icon} {p['name']} ({p['stock']} in stock)", callback_data=f"astockadd:{p['id']}")
    kb.adjust(1)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀ Prev", callback_data=f"astockadd_page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Next ▶", callback_data=f"astockadd_page:{page + 1}"))
    if len(nav) > 1 or total_pages > 1:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="goods_management"))

    await call.message.edit_text(
        "📥 <b>Add Stock — Select a Product</b>\n"
        "<i>Tap the product you want to add stock codes to:</i>",
        reply_markup=kb.as_markup(), parse_mode="HTML"
    )
    await state.update_data(stock_add_paginator=paginator.get_state())


@router.callback_query(F.data.startswith("astockadd_page:"), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_stock_add_page(call: CallbackQuery, state: FSMContext):
    """Paginate the stock-add product browser."""
    page = int(call.data.split(":")[1])
    await _render_stock_add_page(call, state, page)


@router.callback_query(F.data.startswith("astockadd:"), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_stock_add_selected(call: CallbackQuery, state: FSMContext):
    """Ask for stock codes after product is selected."""
    product_id = int(call.data.split(":")[1])

    from sqlalchemy import select
    from packages.database import Database
    from packages.database.models import Goods

    async with Database().session() as s:
        name = (await s.execute(select(Goods.name).where(Goods.id == product_id))).scalar()

    if not name:
        await call.answer("Product not found.", show_alert=True)
        return

    await state.update_data(stock_add_product_id=product_id, stock_add_product_name=name, stock_add_values=[])
    await state.set_state(GoodsFSM.waiting_stock_add)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Done — Save all codes", callback_data="astock_done"))
    kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="admin_stock_add_browse"))

    await call.message.edit_text(
        f"📥 <b>Adding stock to: {name}</b>\n\n"
        f"Send one code per message, or paste multiple codes separated by newlines.\n\n"
        f"<i>Example:\n"
        f"user1@gmail.com:password123\n"
        f"user2@gmail.com:password456</i>\n\n"
        f"When done, tap <b>✅ Done</b>.",
        reply_markup=kb.as_markup(), parse_mode="HTML"
    )


@router.message(GoodsFSM.waiting_stock_add, F.text)
async def admin_stock_collect_codes(message: Message, state: FSMContext):
    """Collect stock codes — supports multiline paste."""
    data = await state.get_data()
    product_name = data.get("stock_add_product_name")
    existing = data.get("stock_add_values", [])

    # Support newline-separated batch paste
    lines = [ln.strip() for ln in (message.text or "").splitlines() if ln.strip()]
    existing.extend(lines)
    await state.update_data(stock_add_values=existing)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Done — Save all codes", callback_data="astock_done"))
    kb.row(InlineKeyboardButton(text="🗑 Cancel & Discard",      callback_data="goods_management"))

    await message.answer(
        f"✅ Added {len(lines)} code(s). Total staged: <b>{len(existing)}</b>\n\n"
        f"📦 Product: <b>{product_name}</b>\n"
        f"Keep sending more codes, or tap <b>✅ Done</b> to save.",
        parse_mode="HTML", reply_markup=kb.as_markup()
    )


@router.callback_query(F.data == "astock_done", HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_stock_save(call: CallbackQuery, state: FSMContext):
    """Save all staged codes to the database."""
    data = await state.get_data()
    product_name = data.get("stock_add_product_name")
    values: list[str] = data.get("stock_add_values", [])

    if not product_name or not values:
        await call.answer("No codes to save.", show_alert=True)
        return

    added = skipped = 0
    for v in values:
        if await add_values_to_item(product_name, v, False):
            added += 1
        else:
            skipped += 1

    await log_audit("add_stock", user_id=call.from_user.id, resource_type="Item",
                    resource_id=product_name, details=f"added={added}, skipped={skipped}")
    await state.clear()
    
    if added > 0:
        # Get price and total stock for notification
        from packages.database import Database
        from sqlalchemy import select, func
        from packages.database.models import Goods, ItemValues
        
        async with Database().session() as s:
            row = (await s.execute(select(Goods.id, Goods.price).where(Goods.name == product_name))).fetchone()
            if row:
                product_id, price = row
                current_stock = (await s.execute(
                    select(func.count(ItemValues.id))
                    .where(ItemValues.item_id == product_id, ItemValues.is_infinity == False)
                )).scalar() or 0
                
                # Send alert
                from apps.telegram_bot.utils.notify import notify_group
                from aiogram.utils.keyboard import InlineKeyboardBuilder
                from apps.telegram_bot.utils.menu_icons import get_menu_icons, format_icon_html
                icons = await get_menu_icons()
                header_icon = format_icon_html("notify_header", "💥", icons)
                added_icon = format_icon_html("notify_added", "➕", icons)
                stock_icon = format_icon_html("notify_stock", "📦", icons)
                price_icon = format_icon_html("notify_price", "💸", icons)
                buy_custom_id = icons.get("notify_buy_btn")

                me = await call.bot.get_me()
                kb = InlineKeyboardBuilder()
                safe_name = product_name.replace(' ', '_')[:50]
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
                    f"{header_icon} <b>{product_name}</b>\n"
                    f"{added_icon} Added: {added}\n"
                    f"{stock_icon} Current stock: {current_stock}\n"
                    f"{price_icon} Price: ${float(price):.2f}"
                )
                await notify_group(call.bot, msg, reply_markup=kb.as_markup())

    await call.message.edit_text(
        f"✅ <b>Stock Updated: {product_name}</b>\n\n"
        f"📥 Added: <b>{added}</b> codes\n"
        f"⚠️ Skipped (duplicates): <b>{skipped}</b>",
        reply_markup=back("goods_management"), parse_mode="HTML"
    )


# ─────────────────────────────────────────────────────────────
#  DELETE PRODUCT — Browse → click → confirm → delete
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == 'admin_delete_browse', HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_delete_browse(call: CallbackQuery, state: FSMContext):
    """Browse products to pick one for deletion."""
    paginator = LazyPaginator(query_all_goods_with_stock, per_page=8)
    page_items = await paginator.get_page(0)
    total_pages = max(await paginator.get_total_pages(), 1)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    kb = InlineKeyboardBuilder()
    for p in page_items:
        icon = "🔴" if (not p["is_infinity"] and p["stock"] == 0) else "📦"
        kb.button(text=f"{icon} {p['name']} ({p['stock']} stock)", callback_data=f"adelete:{p['id']}")
    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="goods_management"))

    await call.message.edit_text(
        "🗑 <b>Delete Product — Select one:</b>\n"
        "<i>⚠️ Deleting a product removes ALL its stock codes permanently.</i>",
        reply_markup=kb.as_markup(), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adelete:"), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_delete_confirm(call: CallbackQuery, state: FSMContext):
    """Show delete confirmation for a product."""
    product_id = int(call.data.split(":")[1])

    from sqlalchemy import select
    from packages.database import Database
    from packages.database.models import Goods, ItemValues
    from sqlalchemy import func

    async with Database().session() as s:
        row = (await s.execute(select(Goods.name, Goods.price).where(Goods.id == product_id))).first()
        stock = (await s.execute(
            select(func.count(ItemValues.id)).where(ItemValues.item_id == product_id)
        )).scalar() or 0

    if not row:
        await call.answer("Product not found.", show_alert=True)
        return

    await state.update_data(delete_product_id=product_id, delete_product_name=row.name)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="⚠️ Yes, Delete It", callback_data=f"adelete_confirm:{product_id}"),
        InlineKeyboardButton(text="❌ Cancel",          callback_data="admin_browse_products"),
    )

    await call.message.edit_text(
        f"🗑 <b>Confirm Delete</b>\n\n"
        f"Product: <b>{row.name}</b>\n"
        f"Price: <b>${row.price:.2f}</b>\n"
        f"Stock codes that will be lost: <b>{stock}</b>\n\n"
        f"<b>⚠️ This cannot be undone!</b>",
        reply_markup=kb.as_markup(), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adelete_confirm:"), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_delete_execute(call: CallbackQuery, state: FSMContext):
    """Execute product deletion after confirmation."""
    product_id = int(call.data.split(":")[1])
    data = await state.get_data()
    product_name = data.get("delete_product_name", "")

    await delete_item(product_name)
    await log_audit("delete_item", user_id=call.from_user.id, resource_type="Item",
                    resource_id=product_name, details=f"id={product_id}")
    await state.clear()

    await call.message.edit_text(
        f"✅ <b>Product deleted: {product_name}</b>",
        reply_markup=back("goods_management"), parse_mode="HTML"
    )


# ─────────────────────────────────────────────────────────────
#  VIEW STOCK ITEMS (existing flow — kept for compatibility)
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("aviewstock:"), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_view_stock_by_id(call: CallbackQuery, state: FSMContext):
    """Jump straight to viewing stock for a product by ID."""
    product_id = int(call.data.split(":")[1])

    from sqlalchemy import select
    from packages.database import Database
    from packages.database.models import Goods

    async with Database().session() as s:
        name = (await s.execute(select(Goods.name).where(Goods.id == product_id))).scalar()

    if not name:
        await call.answer("Product not found.", show_alert=True)
        return

    # Inject the name into state and redirect to the existing show_str_item flow
    await state.update_data(current_position_name=name)

    # Re-use old paginator flow
    query_func = partial(query_items_in_position, name)
    paginator = LazyPaginator(query_func, per_page=10)
    total = await paginator.get_total_count()

    if total == 0:
        await call.message.edit_text(
            f"📭 <b>{name}</b> has no stock items yet.\n"
            f"Use 📥 Add Stock to upload codes.",
            reply_markup=back(f"aprod:{product_id}"), parse_mode="HTML"
        )
        return

    item_hash = generate_short_hash(name)
    await state.update_data(
        item_hash_mapping={item_hash: name},
        current_position_name=name,
        items_in_position_paginator=paginator.get_state()
    )

    markup = await lazy_paginated_keyboard(
        paginator=paginator,
        item_text=lambda g: f"#{g}",
        item_callback=lambda g: f"si_{g}_{item_hash}_0",
        page=0,
        back_cb=f"aprod:{product_id}",
        nav_cb_prefix=f"gip_{item_hash}_"
    )
    await call.message.edit_text(
        f"👁 <b>Stock items for: {name}</b>\n<i>Tap any item to view/delete it.</i>",
        reply_markup=markup, parse_mode="HTML"
    )


@router.callback_query(F.data == 'show__items_in_position', HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def show_items_callback_handler(call: CallbackQuery, state: FSMContext):
    """Show a product browser so admin can click a product to see its stock items."""
    await _render_view_stock_browser(call, state, page=0)


async def _render_view_stock_browser(call: CallbackQuery, state: FSMContext, page: int):
    """Render the product picker for viewing stock items."""
    paginator = LazyPaginator(query_all_goods_with_stock, per_page=8)
    page_items = await paginator.get_page(page)
    total_pages = max(await paginator.get_total_pages(), 1)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    kb = InlineKeyboardBuilder()

    if not page_items:
        await call.message.edit_text(
            "📭 <b>No products found.</b>\nAdd products first from the Items Management menu.",
            reply_markup=back("goods_management"), parse_mode="HTML"
        )
        return

    for p in page_items:
        icon = "♾" if p["is_infinity"] else ("🔴" if p["stock"] == 0 else ("🟡" if p["stock"] <= 3 else "🟢"))
        kb.button(
            text=f"{icon} {p['name']} — {p['stock']} item(s)",
            callback_data=f"aviewstock:{p['id']}"
        )
    kb.adjust(1)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀ Prev", callback_data=f"aviewstock_page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Next ▶", callback_data=f"aviewstock_page:{page + 1}"))
    if len(nav) > 1 or total_pages > 1:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="goods_management"))

    await call.message.edit_text(
        "👁 <b>View Stock Items — Select a Product</b>\n"
        "<i>Tap a product to see all its stock codes:</i>\n\n"
        "♾ Infinite  🟢 In Stock  🟡 Low Stock  🔴 Out of Stock",
        reply_markup=kb.as_markup(), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("aviewstock_page:"), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_view_stock_page(call: CallbackQuery, state: FSMContext):
    """Paginate the view-stock product browser."""
    page = int(call.data.split(":")[1])
    await _render_view_stock_browser(call, state, page)


# ─────────────────────────────────────────────────────────────
#  EXISTING PAGINATOR CALLBACKS (unchanged)
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith('gip_'), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def navigate_items_in_goods(call: CallbackQuery, state: FSMContext):
    """Paginates items inside a position. Format: gip_{item_hash}_{page}"""
    payload = call.data[4:]
    try:
        item_hash, page_str = payload.rsplit('_', 1)
        current_index = int(page_str)
    except ValueError:
        item_hash, current_index = payload, 0

    data = await state.get_data()
    paginator_state = data.get('items_in_position_paginator')
    item_hash_mapping = data.get('item_hash_mapping', {})
    item_name = item_hash_mapping.get(item_hash) or data.get('current_position_name')

    if not item_name:
        await call.answer(localize('errors.invalid_data'), show_alert=True)
        return

    query_func = partial(query_items_in_position, item_name)
    paginator = LazyPaginator(query_func, per_page=10, state=paginator_state)
    total = await paginator.get_total_count()
    if total == 0:
        await call.message.edit_text(localize('admin.goods.list_in_position.empty'), reply_markup=back('goods_management'))
        return

    markup = await lazy_paginated_keyboard(
        paginator=paginator,
        item_text=lambda g: str(g),
        item_callback=lambda g: f"si_{g}_{item_hash}_{current_index}",
        page=current_index,
        back_cb="goods_management",
        nav_cb_prefix=f"gip_{item_hash}_"
    )
    await call.message.edit_text(localize('admin.goods.list_in_position.title'), reply_markup=markup)
    await state.update_data(
        items_in_position_paginator=paginator.get_state(),
        current_position_name=item_name,
        item_hash_mapping={item_hash: item_name}
    )


@router.callback_query(F.data.startswith('si_'), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def item_info_callback_handler(call: CallbackQuery, state: FSMContext):
    """Shows details for a specific item value. Format: si_{id}_{item_hash}_{page}"""
    payload = call.data[3:]
    parts = payload.split('_')
    if len(parts) < 2:
        await call.answer(localize("admin.goods.item.invalid"), show_alert=True)
        return

    item_id_str = parts[0]
    item_hash = parts[1] if len(parts) > 1 else ""
    page = parts[2] if len(parts) > 2 else "0"

    try:
        item_id = int(item_id_str)
    except ValueError:
        await call.answer(localize("admin.goods.item.invalid_id"), show_alert=True)
        return

    item_info = await get_goods_info(item_id)
    if not item_info:
        await call.answer(localize("admin.goods.item.not_found"), show_alert=True)
        return

    position_info = await get_item_info_cached(item_info["item_name"])
    await state.update_data(
        delete_item_id=item_id, delete_item_hash=item_hash,
        delete_page=page, delete_item_name=item_info["item_name"]
    )

    actions = [
        (localize("admin.goods.item.delete.button"), f"dip_{item_id}"),
        (localize("btn.back"), f"gip_{item_hash}_{page}"),
    ]
    markup = simple_buttons(actions, per_row=1)
    text = (
        f'{localize("admin.goods.item.info.position", name=item_info["item_name"])}\n'
        f'{localize("admin.goods.item.info.price", price=position_info["price"], currency=EnvKeys.PAY_CURRENCY)}\n'
        f'{localize("admin.goods.item.info.id", id=item_info["id"])}\n'
        f'{localize("admin.goods.item.info.value", value=item_info["value"])}'
    )
    await call.message.edit_text(text, parse_mode='HTML', reply_markup=markup)


@router.callback_query(F.data.startswith('dip_'), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def process_delete_item_from_position(call: CallbackQuery, state: FSMContext):
    """Delete item value from position. Format: dip_{id}"""
    payload = call.data[4:]
    try:
        item_id = int(payload)
    except ValueError:
        await call.answer(localize("admin.goods.item.invalid"), show_alert=True)
        return

    data = await state.get_data()
    item_hash = data.get('delete_item_hash', '')
    page = data.get('delete_page', '0')
    item_name = data.get('delete_item_name', '')

    item_info = await get_goods_info(item_id)
    if not item_info:
        await call.answer(localize("admin.goods.item.already_deleted_or_missing"), show_alert=True)
        await call.message.edit_text(
            localize("admin.goods.list_in_position.title"),
            reply_markup=back(f"gip_{item_hash}_{page}")
        )
        return

    position_name = item_info["item_name"]
    await delete_item_from_position(item_id)

    if item_hash and item_name:
        try:
            page_int = int(page)
        except Exception:
            await call.message.edit_text(localize('admin.goods.item.deleted'), reply_markup=back(f"gip_{item_hash}_{page}"))
            return

        paginator_state = data.get('items_in_position_paginator')
        query_func = partial(query_items_in_position, item_name)
        paginator = LazyPaginator(query_func, per_page=10, state=paginator_state)
        paginator.clear_cache()

        total = await paginator.get_total_count()
        if total == 0:
            await call.message.edit_text(localize('admin.goods.list_in_position.empty'), reply_markup=back("goods_management"))
        else:
            max_page = max((total - 1) // 10, 0)
            page_int = max(0, min(page_int, max_page))
            markup = await lazy_paginated_keyboard(
                paginator=paginator,
                item_text=lambda g: str(g),
                item_callback=lambda g: f"si_{g}_{item_hash}_{page_int}",
                page=page_int,
                back_cb="goods_management",
                nav_cb_prefix=f"gip_{item_hash}_"
            )
            await call.message.edit_text(
                f'{localize("admin.goods.item.deleted")}\n\n{localize("admin.goods.list_in_position.title")}',
                reply_markup=markup
            )
            await state.update_data(
                items_in_position_paginator=paginator.get_state(),
                item_hash_mapping={item_hash: item_name}
            )
    else:
        await call.message.edit_text(localize('admin.goods.item.deleted'), reply_markup=back("goods_management"))

    admin_info = await call.message.bot.get_chat(call.from_user.id)
    await log_audit("delete_item_value", user_id=call.from_user.id, resource_type="ItemValue",
                    resource_id=str(item_id), details=f"admin={admin_info.first_name}, position={position_name or '<?>'}",)


# ────────────────────────────────────────────────────────────
#  EDIT PRODUCT FROM DETAIL PAGE
# ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("aedit:"), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_edit_product(call: CallbackQuery, state: FSMContext):
    """
    Pre-fill the UpdateItemFSM with the selected product so admin doesn't have to retype name.
    Then transition directly into the update flow at the name step.
    """
    product_id = int(call.data.split(":")[1])

    from sqlalchemy import select
    from packages.database import Database
    from packages.database.models import Goods, Categories
    async with Database().session() as s:
        row = (await s.execute(
            select(Goods.name, Goods.description, Goods.price, Goods.category_id)
            .where(Goods.id == product_id)
        )).first()
        if not row:
            await call.answer("Product not found.", show_alert=True)
            return
        cat_name = (await s.execute(
            select(Categories.name).where(Categories.id == row.category_id)
        )).scalar() or ""

    from apps.telegram_bot.states import UpdateItemFSM
    await state.update_data(
        item_old_name=row.name,
        item_category=cat_name,
    )
    await call.message.edit_text(
        f"✏️ <b>Editing: {row.name}</b>\n\n"
        f"Current name: <b>{row.name}</b>\n"
        f"Current price: <b>{row.price} {EnvKeys.PAY_CURRENCY}</b>\n"
        f"Current description: <i>{row.description or 'None'}</i>\n\n"
        f"Enter the <b>new product name</b> (or send the same name to keep it):",
        reply_markup=back(f"aprod:{product_id}"),
        parse_mode="HTML",
    )
    await state.set_state(UpdateItemFSM.waiting_item_new_name)


async def delete_str_item(message: Message, state: FSMContext):
    """Delete an item by text name (compatibility helper)."""
    raw_name = message.text.strip() if message.text else ""
    from packages.database.methods.read import get_item_info
    from packages.database.methods.delete import delete_item
    item = await get_item_info(raw_name)
    if not item:
        await message.answer(localize("admin.goods.delete.not_found"), reply_markup=back("goods_management"))
        await state.clear()
        return
    await delete_item(raw_name)
    await message.answer(localize("admin.goods.delete.success"), reply_markup=back("goods_management"))
    await state.clear()


async def show_str_item(message: Message, state: FSMContext):
    """Show an item by text name (compatibility helper)."""
    raw_name = message.text.strip() if message.text else ""
    from packages.database.methods.read import get_item_info
    item = await get_item_info(raw_name)
    if not item:
        await message.answer(localize("admin.goods.view.not_found"), reply_markup=back("goods_management"))
        await state.clear()
        return
    await message.answer(f"📦 Product: {raw_name}", reply_markup=back("goods_management"))
    await state.clear()
