"""
Admin — Categories Management (redesigned)
=============================================
Browse existing categories visually → click to rename or delete.
No more typing category names manually.
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from apps.telegram_bot.i18n import localize
from packages.database.models import Permission
from packages.database.methods import check_category_cached, create_category, delete_category, update_category
from apps.telegram_bot.keyboards.inline import back, simple_buttons
from apps.telegram_bot.filters import HasPermissionFilter
from packages.database.methods.audit import log_audit
from apps.telegram_bot.utils.validators import CategoryRequest
from apps.telegram_bot.states import CategoryFSM

router = Router()


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────

async def _fetch_all_categories() -> list[dict]:
    """Fetch all categories with product and stock counts."""
    from packages.database.methods.lazy_queries import query_categories_with_stock
    results = []
    offset = 0
    while True:
        page = await query_categories_with_stock(offset=offset, limit=20)
        if not page:
            break
        results.extend(page)
        offset += 20
    return results


def _category_list_keyboard(categories: list[dict], callback_prefix: str, back_cb: str = None):
    """Build a one-per-row button list of all categories with stock counts and active status."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    kb = InlineKeyboardBuilder()
    for cat in categories:
        if isinstance(cat, dict):
            name = cat["name"]
            products = cat.get("product_count", 0)
            stock = cat.get("stock_codes", 0)
            is_active = cat.get("is_active", True)
            status_icon = "🟢" if is_active else "🔴 [DISABLED]"
            label = f"{status_icon} {name}  •  {products} product{'s' if products != 1 else ''}  •  📦 {stock} stock"
        else:
            name = cat
            label = f"🟢 {name}"
        kb.button(text=label, callback_data=f"{callback_prefix}{name[:50]}")
    kb.adjust(1)
    if back_cb:
        kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data=back_cb))
    return kb.as_markup()


# ─────────────────────────────────────────────────────────────
#  MAIN MENU
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == 'categories_management', HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def categories_callback_handler(call: CallbackQuery, state):
    """Opens the categories management submenu listing all categories."""
    await state.clear()
    categories = await _fetch_all_categories()
    total_stock = sum(c.get("stock_codes", 0) if isinstance(c, dict) else 0 for c in categories)

    header = (
        f"📂 <b>Categories Management</b>\n"
        f"<i>{len(categories)} categor{'y' if len(categories)==1 else 'ies'}  •  📦 {total_stock} total stock</i>\n\n"
        f"Select a category below to manage it:"
    )
    
    # Don't pass back_cb so it doesn't add a back button yet
    markup = _category_list_keyboard(categories, "acat_dash:")
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    # Use markup.inline_keyboard since aiogram expects a list of lists of buttons
    kb = InlineKeyboardBuilder(markup=markup.inline_keyboard)
    kb.row(InlineKeyboardButton(text="➕ Add Category", callback_data="add_category"))
    kb.row(InlineKeyboardButton(text="⬅️ Back to Console", callback_data="console"))
    
    await call.message.edit_text(
        header,
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

# ─────────────────────────────────────────────────────────────
#  CATEGORY DASHBOARD
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith('acat_dash:'), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def category_dashboard_handler(call: CallbackQuery, state: FSMContext):
    """Dashboard for a specific category."""
    cat_name = call.data[len('acat_dash:'):]
    
    categories = await _fetch_all_categories()
    cat_data = next((c for c in categories if c.get("name") == cat_name), None)
    
    if not cat_data:
        await call.answer("Category not found.", show_alert=True)
        return
        
    product_count = cat_data.get("product_count", 0)
    stock = cat_data.get("stock_codes", 0)
    
    # Check is_active from DB
    from packages.database.engine import Database
    from packages.database.models.main import Categories
    from sqlalchemy import select
    async with Database().session() as s:
        c_obj = (await s.execute(select(Categories).where(Categories.name == cat_name))).scalar_one_or_none()
        is_active = c_obj.is_active if c_obj else True
        
    status_str = "🟢 <b>Active</b>" if is_active else "🔴 <b>Disabled (Hidden from Shop)</b>"
    
    header = (
        f"📂 <b>Category Dashboard:</b> {cat_name}\n\n"
        f"Status: {status_str}\n"
        f"📦 Products: <b>{product_count}</b>\n"
        f"🛒 Total Stock: <b>{stock}</b>"
    )
    
    from apps.telegram_bot.keyboards.inline import _make_btn
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.row(_make_btn("📦 View Products", callback_data=f"acat_view:{cat_name}", style="primary"))
    kb.row(
        _make_btn("✏️ Rename", callback_data=f"acat_ren:{cat_name}", style="primary"),
        _make_btn("🏷 Set Custom Icon", callback_data=f"acat_icon:{cat_name}", style="primary")
    )
    if is_active:
        kb.row(_make_btn("🔴 Disable Category", callback_data=f"acat_toggle:{cat_name}", style="danger"))
    else:
        kb.row(_make_btn("🟢 Enable Category", callback_data=f"acat_toggle:{cat_name}", style="success"))
    kb.row(
        _make_btn("🗑 Delete", callback_data=f"acat_del:{cat_name}", style="danger"),
        _make_btn("⬅️ Back", callback_data="categories_management", style="primary")
    )
    
    await call.message.edit_text(
        header,
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith('acat_toggle:'), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def category_toggle_active_handler(call: CallbackQuery, state: FSMContext):
    """Toggle category active/disabled status."""
    cat_name = call.data[len('acat_toggle:'):]
    from packages.database.engine import Database
    from packages.database.models.main import Categories
    from sqlalchemy import select, update
    
    async with Database().session() as s:
        cat = (await s.execute(select(Categories).where(Categories.name == cat_name))).scalar_one_or_none()
        if cat:
            new_status = not cat.is_active
            await s.execute(update(Categories).where(Categories.id == cat.id).values(is_active=new_status))
            await s.commit()
            status_text = "enabled" if new_status else "disabled"
            await call.answer(f"Category '{cat_name}' has been {status_text}!", show_alert=True)
            log_audit(f"admin_toggle_category_{status_text}", f"category:{cat_name}")
        else:
            await call.answer("Category not found.", show_alert=True)
            
    await category_dashboard_handler(call, state)

# ─────────────────────────────────────────────────────────────
#  VIEW PRODUCTS
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith('acat_view:'), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_cat_view_products(call: CallbackQuery, state: FSMContext):
    """View products within this category (Page 0)."""
    cat_name = call.data[len('acat_view:'):]
    await _render_admin_category_products(call, state, cat_name, 0)

@router.callback_query(F.data.startswith('acat_vpage:'), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_cat_view_page(call: CallbackQuery, state: FSMContext):
    """Pagination for products within a category."""
    parts = call.data.split(':')
    page = int(parts[1])
    cat_name = parts[2]
    await _render_admin_category_products(call, state, cat_name, page)

async def _render_admin_category_products(call: CallbackQuery, state: FSMContext, cat_name: str, page: int):
    from packages.database.methods.lazy_queries import query_all_products_flat
    from apps.telegram_bot.utils.paginator import LazyPaginator
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    # Use LazyPaginator with our query
    async def fetcher(offset=0, limit=10, count_only=False):
        return await query_all_products_flat(offset, limit, count_only, category=cat_name)

    paginator = LazyPaginator(fetcher, per_page=8)
    page_items = await paginator.get_page(page)
    total_pages = max(await paginator.get_total_pages(), 1)

    kb = InlineKeyboardBuilder()
    
    for p in page_items:
        icon = "♾" if p.get("is_infinity") else ("🔴" if not p.get("stock") else ("🟡" if p.get("stock") <= 3 else "🟢"))
        src = p.get("source", "local")
        src_tag = "" if src == "local" else f" [{src.upper()}]"
        
        btn_text = f"{icon} {p['name']}{src_tag} - ${p['price']:.2f}"
        
        # Route to different editors based on source
        if src == "local":
            cb_data = f"aprod:{p['id']}" # Standard local product editor
        else:
            cb_data = f"rs_product:{p['reseller_product_id']}" # Reseller product editor
            
        kb.button(text=btn_text[:64], callback_data=cb_data)
        
    kb.adjust(1)
    
    # Pagination nav
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀ Prev", callback_data=f"acat_vpage:{page - 1}:{cat_name}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Next ▶", callback_data=f"acat_vpage:{page + 1}:{cat_name}"))
    
    if len(nav) > 1 or total_pages > 1:
        kb.row(*nav)
        
    kb.row(InlineKeyboardButton(text="⬅️ Back to Category", callback_data=f"acat_dash:{cat_name}"))

    await call.message.edit_text(
        f"📦 <b>Products in {cat_name}</b>\n\n"
        f"<i>Tap a product to edit its price, stock, or settings.</i>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

# ─────────────────────────────────────────────────────────────
#  SET CUSTOM ICON
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith('acat_icon:'), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_cat_set_icon(call: CallbackQuery, state: FSMContext):
    """Ask admin for custom emoji for category."""
    cat_name = call.data[len('acat_icon:'):]
    await state.update_data(cat_name=cat_name)
    await call.message.edit_text(
        f"Send the custom premium emoji you want to use for <b>{cat_name}</b>.",
        reply_markup=back(f"acat_dash:{cat_name}"),
        parse_mode="HTML"
    )
    await state.set_state(CategoryFSM.waiting_category_icon)

@router.message(CategoryFSM.waiting_category_icon, F.text)
async def process_category_icon(message: Message, state: FSMContext):
    """Saves the custom emoji ID."""
    data = await state.get_data()
    cat_name = data.get("cat_name")
    
    custom_emoji_id = None
    if message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji":
                custom_emoji_id = entity.custom_emoji_id
                break
                
    if not custom_emoji_id:
        await message.answer(
            "I couldn't find a custom premium emoji in your message. Please send one, or press Back.",
            reply_markup=back(f"acat_dash:{cat_name}")
        )
        return
        
    # Update DB
    from packages.database.engine import Database
    from sqlalchemy import update
    from packages.database.models.main import Categories
    async with Database().session() as s:
        await s.execute(update(Categories).where(Categories.name == cat_name).values(icon_custom_emoji_id=custom_emoji_id))
        await s.commit()
        
    await message.answer(
        f"✅ <b>Custom icon saved for {cat_name}!</b>",
        reply_markup=back(f"acat_dash:{cat_name}"),
        parse_mode="HTML"
    )
    await state.clear()
# ─────────────────────────────────────────────────────────────
#  ADD CATEGORY  (text input — unchanged)
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == 'add_category', HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def add_category_callback_handler(call: CallbackQuery, state):
    """Asks admin for a new category name."""
    await call.message.edit_text(
        localize("admin.categories.prompt.add"),
        reply_markup=back("categories_management"),
    )
    await state.set_state(CategoryFSM.waiting_add_category)


@router.message(CategoryFSM.waiting_add_category, F.text)
async def process_category_for_add(message: Message, state):
    """Creates a category if it doesn't exist yet."""
    try:
        raw_text = message.text.strip() if message.text else ""
        if raw_text.startswith("/"):
            await message.answer(
                "❌ Bot commands (like <code>/start</code>) cannot be used as category names.",
                reply_markup=back("categories_management"),
                parse_mode="HTML"
            )
            await state.clear()
            return

        category_request = CategoryRequest(name=raw_text)
        category_name = category_request.sanitize_name()

        if await check_category_cached(category_name):
            await message.answer(
                localize("admin.categories.add.exist"),
                reply_markup=back("categories_management"),
            )
        else:
            await create_category(category_name)
            await message.answer(
                f"✅ {localize('admin.categories.add.success')} <b>{category_name}</b>",
                reply_markup=back("categories_management"),
                parse_mode="HTML"
            )
            admin_info = await message.bot.get_chat(message.from_user.id)
            await log_audit("create_category", user_id=message.from_user.id,
                            resource_type="Category", resource_id=category_name,
                            details=f"admin={admin_info.first_name}")
    except Exception as e:
        await message.answer(
            localize("errors.invalid_data"),
            reply_markup=back("categories_management"),
        )
        await log_audit("create_category_error", level="ERROR",
                        user_id=message.from_user.id, resource_type="Category", details=str(e))
    await state.clear()


# ─────────────────────────────────────────────────────────────
#  DELETE CATEGORY
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("acat_del:"), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_cat_delete_confirm(call: CallbackQuery, state: FSMContext):
    """Show confirmation before deleting."""
    cat_name = call.data[len("acat_del:"):]

    # Get product count in this category
    from packages.database.methods.lazy_queries import query_all_products_flat
    product_count = await query_all_products_flat(category=cat_name, count_only=True)

    await state.update_data(delete_cat_name=cat_name)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="⚠️ Yes, Delete",  callback_data="acat_del_confirm"),
        InlineKeyboardButton(text="❌ Cancel",        callback_data=f"acat_dash:{cat_name}"),
    )


    await call.message.edit_text(
        f"🗑 <b>Confirm Delete</b>\n\n"
        f"Category: <b>{cat_name}</b>\n"
        f"Products inside: <b>{product_count}</b>\n\n"
        f"<b>⚠️ This will permanently delete the category and ALL its products!</b>",
        reply_markup=kb.as_markup(), parse_mode="HTML"
    )


@router.callback_query(F.data == "acat_del_confirm", HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_cat_delete_execute(call: CallbackQuery, state: FSMContext):
    """Execute category deletion."""
    data = await state.get_data()
    cat_name = data.get("delete_cat_name", "")

    await delete_category(cat_name)
    admin_info = await call.message.bot.get_chat(call.from_user.id)
    await log_audit("delete_category", user_id=call.from_user.id,
                    resource_type="Category", resource_id=cat_name,
                    details=f"admin={admin_info.first_name}")
    await state.clear()

    await call.message.edit_text(
        f"✅ <b>Category deleted:</b> {cat_name}",
        reply_markup=back("categories_management"), parse_mode="HTML"
    )


# ─────────────────────────────────────────────────────────────
#  RENAME CATEGORY
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("acat_ren:"), HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def admin_cat_rename_selected(call: CallbackQuery, state: FSMContext):
    """Ask for the new name after selecting a category."""
    old_name = call.data[len("acat_ren:"):]
    await state.update_data(old_category=old_name)
    await state.set_state(CategoryFSM.waiting_update_category_name)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data=f"acat_dash:{old_name}"))

    await call.message.edit_text(
        f"✏️ <b>Rename: {old_name}</b>\n\n"
        f"Type the <b>new name</b> for this category:",
        reply_markup=kb.as_markup(), parse_mode="HTML"
    )


@router.message(CategoryFSM.waiting_update_category_name, F.text)
async def check_category_name_for_update(message: Message, state: FSMContext):
    """Renames the category to the new name."""
    new_name = message.text.strip()
    if new_name.startswith("/"):
        await message.answer(
            "❌ Bot commands (like <code>/start</code>) cannot be used as category names.",
            reply_markup=back("categories_management"),
            parse_mode="HTML"
        )
        await state.clear()
        return

    data = await state.get_data()
    old_name = data.get("old_category")

    if await check_category_cached(new_name):
        await message.answer(
            localize("admin.categories.rename.exist"),
            reply_markup=back("categories_management"),
        )
        await state.clear()
        return

    await update_category(old_name, new_name)
    await message.answer(
        f"✅ {localize('admin.categories.rename.success')} <b>{old_name} → {new_name}</b>",
        reply_markup=back("categories_management"),
        parse_mode="HTML"
    )
    admin_info = await message.bot.get_chat(message.from_user.id)
    await log_audit("rename_category", user_id=message.from_user.id,
                    resource_type="Category", resource_id=new_name,
                    details=f"admin={admin_info.first_name}, old_name={old_name}")
    await state.clear()


# ─────────────────────────────────────────────────────────────
#  LEGACY CALLBACKS — kept for backward compatibility
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == 'delete_category', HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def delete_category_callback_handler(call: CallbackQuery, state):
    """Legacy: redirect to dashboard list."""
    await categories_callback_handler(call, state)


@router.callback_query(F.data == 'update_category', HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def update_category_callback_handler(call: CallbackQuery, state):
    """Legacy: redirect to dashboard list."""
    await categories_callback_handler(call, state)


async def process_category_for_delete(message: Message, state: FSMContext):
    """Delete a category by text name (compatibility helper)."""
    raw_name = message.text.strip() if message.text else ""
    if not await check_category_cached(raw_name):
        await message.answer(localize("admin.categories.delete.not_found"), reply_markup=back("categories_management"))
        await state.clear()
        return
    await delete_category(raw_name)
    await message.answer(localize("admin.categories.delete.success"), reply_markup=back("categories_management"))
    await state.clear()


async def check_category_for_update(message: Message, state: FSMContext):
    """Check old category name before renaming (compatibility helper)."""
    raw_name = message.text.strip() if message.text else ""
    if not await check_category_cached(raw_name):
        await message.answer(localize("admin.categories.rename.not_found"), reply_markup=back("categories_management"))
        await state.clear()
        return
    await state.update_data(old_category=raw_name)
    await state.set_state(CategoryFSM.waiting_update_category_name)
    await message.answer(localize("admin.categories.prompt.new_name"), reply_markup=back("categories_management"))

