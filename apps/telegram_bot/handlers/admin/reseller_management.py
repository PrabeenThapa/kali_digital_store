"""
Admin Reseller Management Handler.

Provides admin interface to:
- View all reseller products per source
- Toggle products on/off (is_enabled)
- Set custom sell price or reset to auto-markup
- Change markup percentage per product
- Trigger manual sync from APIs
- View API wallet balance
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from html import escape

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup

from sqlalchemy import case, func, select

from packages.config.config import EnvKeys
from packages.database.engine import Database
from packages.database.models.main import ResellerSource, ResellerProduct, Permission
from packages.database.methods.read import check_role

router = Router()

_log = logging.getLogger(__name__)


class ResellerAdminStates(StatesGroup):
    waiting_custom_price = State()
    waiting_markup_percent = State()
    waiting_category = State()
    waiting_name = State()
    waiting_icon = State()


# ────────────────────────────────────────────────────────────────
#  Permission guard helper
# ────────────────────────────────────────────────────────────────

async def _has_reseller_perm(user_id: int) -> bool:
    perms = await check_role(user_id)  # returns an int permission bitmask
    if not perms:
        return False
    return bool(perms & Permission.CATALOG_MANAGE) or bool(perms & Permission.OWN)


# ────────────────────────────────────────────────────────────────
#  Main Reseller Admin Menu
# ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_resellers")
async def reseller_admin_menu(call: CallbackQuery, state: FSMContext):
    """Main reseller management menu."""
    if not await _has_reseller_perm(call.from_user.id):
        await call.answer("❌ No permission.", show_alert=True)
        return

    async with Database().session() as s:
        sources = (await s.execute(
            select(ResellerSource).order_by(ResellerSource.name)
        )).scalars().all()
        count_rows = (await s.execute(
            select(
                ResellerProduct.source_id,
                func.count(ResellerProduct.id),
                func.coalesce(func.sum(case((ResellerProduct.is_enabled == True, 1), else_=0)), 0),  # noqa: E712
            ).group_by(ResellerProduct.source_id)
        )).all()

    counts = {source_id: (total, enabled) for source_id, total, enabled in count_rows}
    total_products = sum(total for total, _ in counts.values())
    enabled_products = sum(enabled for _, enabled in counts.values())

    kb = InlineKeyboardBuilder()
    for src in sources:
        status = "🟢" if src.is_active else "🔴"
        total, enabled = counts.get(src.id, (0, 0))
        synced = src.last_synced.strftime("%d %b · %H:%M UTC") if src.last_synced else "not synced"
        kb.button(
            text=f"{status} {src.name.upper()} · {enabled}/{total} live · {synced}",
            callback_data=f"rs_source:{src.id}:0",
        )

    kb.button(text="💲 Manage prices", callback_data="rs_prices:0")
    kb.button(text="🔄 Sync all sources", callback_data="rs_sync_all")
    kb.button(text="💰 Wallet balances", callback_data="rs_balances")
    kb.button(text="◀ Admin menu", callback_data="console")
    kb.adjust(1)

    await call.message.edit_text(
        "🔌 <b>Reseller catalog</b>\n\n"
        f"<b>{enabled_products}</b> of <b>{total_products}</b> products are live across "
        f"<b>{len(sources)}</b> sources.\n"
        "<i>Select a source to review its catalog and sync status.</i>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )


# ────────────────────────────────────────────────────────────────
#  RENAME PRODUCT (OVERRIDE API NAME)
# ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rs_set_name:"))
async def reseller_set_name(call: CallbackQuery, state: FSMContext):
    product_id = int(call.data.split(":")[1])
    await state.update_data(rs_editing_product_id=product_id)
    await call.message.edit_text(
        "Enter the new name for this product (this overrides the API name).\nSend /cancel to abort.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data=f"rs_product:{product_id}")]])
    )
    await state.set_state(ResellerAdminStates.waiting_name)

@router.message(ResellerAdminStates.waiting_name, F.text)
async def reseller_process_name(message: Message, state: FSMContext):
    product_id = (await state.get_data()).get("rs_editing_product_id")
    new_name = message.text.strip()
    if new_name == "/cancel":
        await state.set_state(None)
        await message.answer("Cancelled.")
        return
    
    async with Database().session() as s:
        p = (await s.execute(select(ResellerProduct).where(ResellerProduct.id == product_id))).scalars().first()
        if p:
            p.name_override = new_name
            await s.commit()
            
    await state.set_state(None)
    await message.answer(f"✅ Name overridden to <b>{escape(new_name)}</b>", parse_mode="HTML")
    
    new_call = CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", message=message, data=f"rs_product:{product_id}")
    await reseller_product_detail(new_call, state)


# ────────────────────────────────────────────────────────────────
#  SET ICON FOR PRODUCT
# ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rs_set_icon:"))
async def reseller_set_icon(call: CallbackQuery, state: FSMContext):
    product_id = int(call.data.split(":")[1])
    await state.update_data(rs_editing_product_id=product_id)
    await call.message.edit_text(
        "Send the custom premium emoji you want to use for this item.\nSend /cancel to abort.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data=f"rs_product:{product_id}")]])
    )
    await state.set_state(ResellerAdminStates.waiting_icon)

@router.message(ResellerAdminStates.waiting_icon)
async def reseller_process_icon(message: Message, state: FSMContext):
    product_id = (await state.get_data()).get("rs_editing_product_id")
    if message.text and message.text.strip() == "/cancel":
        await state.set_state(None)
        await message.answer("Cancelled.")
        return

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
            "❌ That doesn't look like a valid custom premium emoji. Try sending one from your sticker panel.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data=f"rs_product:{product_id}")]])
        )
        return
    
    async with Database().session() as s:
        p = (await s.execute(select(ResellerProduct).where(ResellerProduct.id == product_id))).scalars().first()
        if p:
            p.icon_custom_emoji_id = custom_emoji_id
            await s.commit()
            
    await state.set_state(None)
    await message.answer(f"✅ Icon updated successfully!", parse_mode="HTML")
    
    new_call = CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", message=message, data=f"rs_product:{product_id}")
    await reseller_product_detail(new_call, state)


# ────────────────────────────────────────────────────────────────
#  Price Manager — all products across all sources, one flat list
# ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rs_prices:"))
async def reseller_price_manager(call: CallbackQuery, state: FSMContext):
    """Flat paginated list of ALL reseller products across every source for quick price editing."""
    if not await _has_reseller_perm(call.from_user.id):
        await call.answer("❌ No permission.", show_alert=True)
        return

    page = int(call.data.split(":")[1]) if ":" in call.data else 0
    per_page = 8

    async with Database().session() as s:
        total = (await s.execute(select(func.count(ResellerProduct.id)))).scalar_one()
        total_pages = max((total + per_page - 1) // per_page, 1)
        page = min(max(page, 0), total_pages - 1)
        rows = (await s.execute(
            select(ResellerProduct, ResellerSource.name)
            .join(ResellerSource, ResellerSource.id == ResellerProduct.source_id)
            .order_by(ResellerSource.name, ResellerProduct.name)
            .offset(page * per_page)
            .limit(per_page)
        )).all()

    badge = {"forkpixel": "🔷", "cgpt": "🟢", "safwan": "🐯", "canboso": "🟨"}

    kb = InlineKeyboardBuilder()
    for p, src_name in rows:
        b = badge.get(src_name, "•")
        price_label = f"${p.effective_sell_price:.2f}" if p.sell_price is None else f"${float(p.sell_price):.2f}*"
        status = "✅" if p.is_enabled else "❌"
        kb.button(
            text=f"{status}{b} {p.name[:24]} → {price_label}",
            callback_data=f"rs_product:{p.id}",
        )
    kb.adjust(1)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"rs_prices:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"rs_prices:{page + 1}"))
    if nav:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="◀ Reseller catalog", callback_data="admin_resellers"))

    await call.message.edit_text(
        f"💲 <b>Reseller pricing</b>\n\n"
        f"<b>{total}</b> products across all sources.\n"
        f"<i>Tap a product to edit it. * marks a custom price.</i>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )


# ────────────────────────────────────────────────────────────────
#  Product List for a Source
# ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rs_source:"))
async def reseller_source_products(call: CallbackQuery, state: FSMContext):
    """List products for a given source with enable/disable + price controls."""
    if not await _has_reseller_perm(call.from_user.id):
        await call.answer("❌ No permission.", show_alert=True)
        return

    parts = call.data.split(":")
    source_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0
    per_page = 8

    async with Database().session() as s:
        source = (await s.execute(
            select(ResellerSource).where(ResellerSource.id == source_id)
        )).scalars().first()

        total, enabled_count = (await s.execute(
            select(
                func.count(ResellerProduct.id),
                func.coalesce(func.sum(case((ResellerProduct.is_enabled == True, 1), else_=0)), 0),  # noqa: E712
            ).where(ResellerProduct.source_id == source_id)
        )).one()

        total_pages = max((total + per_page - 1) // per_page, 1)
        page = min(max(page, 0), total_pages - 1)
        page_products = (await s.execute(
            select(ResellerProduct)
            .where(ResellerProduct.source_id == source_id)
            .order_by(ResellerProduct.name)
            .offset(page * per_page)
            .limit(per_page)
        )).scalars().all()

    if not source:
        await call.answer("Source not found.", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    for p in page_products:
        status = "✅" if p.is_enabled else "❌"
        price_label = f"${p.effective_sell_price:.2f}" if p.sell_price is None else f"${float(p.sell_price):.2f}*"
        kb.button(
            text=f"{status} {p.name[:30]} · {price_label}",
            callback_data=f"rs_product:{p.id}",
        )

    kb.adjust(1)

    # Pagination
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"rs_source:{source_id}:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"rs_source:{source_id}:{page + 1}"))
    if nav:
        kb.row(*nav)

    kb.row(
        InlineKeyboardButton(text="✅ Enable all", callback_data=f"rs_enable_all:{source_id}"),
        InlineKeyboardButton(text="⏸ Disable all", callback_data=f"rs_disable_all:{source_id}"),
    )
    kb.row(
        InlineKeyboardButton(text="🔄 Sync source", callback_data=f"rs_sync:{source_id}"),
        InlineKeyboardButton(text="◀ Sources", callback_data="admin_resellers"),
    )

    synced = source.last_synced.strftime("%d %b %Y · %H:%M UTC") if source.last_synced else "Not synced yet"
    source_status = "Active" if source.is_active else "Paused"
    await call.message.edit_text(
        f"📦 <b>{escape(source.name.upper())} catalog</b>\n\n"
        f"{('🟢' if source.is_active else '🔴')} <b>{source_status}</b>  ·  "
        f"<b>{enabled_count}/{total}</b> live\n"
        f"Last sync: <b>{synced}</b>\n\n"
        f"<i>Tap a product to manage it. * marks a custom price.</i>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )
    await state.update_data(rs_source_id=source_id, rs_source_page=page)


# ────────────────────────────────────────────────────────────────
#  Product Detail / Controls
# ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rs_product:"))
async def reseller_product_detail(call: CallbackQuery, state: FSMContext):
    """Show controls for a single reseller product."""
    if not await _has_reseller_perm(call.from_user.id):
        await call.answer("❌ No permission.", show_alert=True)
        return

    product_id = int(call.data.split(":")[1])
    async with Database().session() as s:
        row = (await s.execute(
            select(ResellerProduct, ResellerSource.name)
            .join(ResellerSource, ResellerSource.id == ResellerProduct.source_id)
            .where(ResellerProduct.id == product_id)
        )).first()

    if not row:
        await call.answer("Product not found.", show_alert=True)
        return
    p, source_name = row

    status = "✅ Enabled" if p.is_enabled else "❌ Disabled"
    cost = float(p.cost_price)
    sell = p.effective_sell_price
    markup = float(p.markup_percent)
    price_mode = f"${float(p.sell_price):.2f} (custom)" if p.sell_price else f"auto ${sell:.2f} ({markup}% markup)"

    category = p.effective_category
    cat_mode = f"{p.category_override} (manual)" if p.category_override else f"{category} (auto)"

    text = (
        f"📦 <b>{escape(p.effective_name)}</b>{' (API: <i>' + escape(p.name) + '</i>)' if p.name_override else ''}\n"
        f"<i>{escape(source_name.upper())}</i>\n\n"
        f"{status}\n"
        f"🏷 <b>Category:</b> {escape(cat_mode)}\n"
        f"📋 <b>Type:</b> {escape(p.product_type.replace('_', ' ').title())}\n"
        f"📥 <b>Cost:</b> ${cost:.4f} USD\n"
        f"💵 <b>Sell price:</b> {escape(price_mode)}\n"
        f"📊 <b>Stock:</b> {p.stock if p.stock is not None else 'Preorder / unlimited'}\n"
        f"🔗 <b>External ID:</b> <code>{escape(p.external_id)}</code>"
    )

    data = await state.get_data()
    back_page = data.get("rs_source_page", 0) if data.get("rs_source_id") == p.source_id else 0
    kb = InlineKeyboardBuilder()
    
    feat_text = "⭐ Remove Featured" if getattr(p, "is_featured", False) else "⭐ Make Featured"
    kb.button(text=feat_text, callback_data=f"rs_feat:{product_id}")
    
    toggle_label = "❌ Disable" if p.is_enabled else "✅ Enable"
    kb.button(text=toggle_label, callback_data=f"rs_toggle:{product_id}")
    kb.button(text="💲 Set Custom Price", callback_data=f"rs_set_price:{product_id}")
    kb.button(text="🔄 Reset to Auto Price", callback_data=f"rs_reset_price:{product_id}")
    kb.button(text="📊 Set Markup %", callback_data=f"rs_set_markup:{product_id}")
    kb.button(text="📂 Set Category", callback_data=f"rs_set_cat:{product_id}")
    kb.button(text="✏️ Edit Name", callback_data=f"rs_set_name:{product_id}")
    kb.button(text="🏷 Set Icon", callback_data=f"rs_set_icon:{product_id}")
    if p.category_override:
        kb.button(text="↺ Auto Category", callback_data=f"rs_reset_cat:{product_id}")
    kb.button(text="◀ API Source List", callback_data=f"rs_source:{p.source_id}:{back_page}")
    kb.button(text="◀ All Products (Unified)", callback_data="admin_browse_products")
    kb.adjust(1)

    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await state.update_data(rs_editing_product_id=product_id)


@router.callback_query(F.data.startswith("rs_feat:"))
async def reseller_toggle_featured(call: CallbackQuery, state: FSMContext):
    """Toggle the is_featured flag for a reseller product."""
    if not await _has_reseller_perm(call.from_user.id):
        await call.answer("❌ No permission.", show_alert=True)
        return

    product_id = int(call.data.split(":")[1])
    async with Database().session() as s:
        p = (await s.execute(select(ResellerProduct).where(ResellerProduct.id == product_id))).scalars().first()
        if p:
            p.is_featured = not getattr(p, "is_featured", False)
            await s.commit()

    # Refresh the same page
    new_call = call.model_copy(update={'data': f"rs_product:{product_id}"})
    await reseller_product_detail(new_call, state)


# ────────────────────────────────────────────────────────────────
#  Toggle Enable/Disable
# ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rs_toggle:"))
async def reseller_toggle_product(call: CallbackQuery, state: FSMContext):
    if not await _has_reseller_perm(call.from_user.id):
        await call.answer("❌ No permission.", show_alert=True)
        return

    product_id = int(call.data.split(":")[1])
    async with Database().session() as s:
        p = (await s.execute(
            select(ResellerProduct).where(ResellerProduct.id == product_id)
        )).scalars().first()
        if not p:
            await call.answer("Not found.", show_alert=True)
            return
        p.is_enabled = not p.is_enabled
        new_status = "enabled" if p.is_enabled else "disabled"
        await s.commit()

    await call.answer(f"✅ Product {new_status}.")
    # Re-render product detail
    new_call = call.model_copy(update={'data': f"rs_product:{product_id}"})
    await reseller_product_detail(new_call, state)


# ────────────────────────────────────────────────────────────────
#  Enable All / Disable All for a source
# ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rs_enable_all:"))
async def reseller_enable_all(call: CallbackQuery, state: FSMContext):
    """Enable every product in a source at once."""
    if not await _has_reseller_perm(call.from_user.id):
        await call.answer("❌ No permission.", show_alert=True)
        return

    source_id = int(call.data.split(":")[1])
    async with Database().session() as s:
        products = (await s.execute(
            select(ResellerProduct).where(ResellerProduct.source_id == source_id)
        )).scalars().all()
        count = 0
        for p in products:
            if not p.is_enabled:
                p.is_enabled = True
                count += 1
        await s.commit()

    await call.answer(f"✅ {count} products enabled.", show_alert=True)
    new_call = call.model_copy(update={'data': f"rs_source:{source_id}:0"})
    await reseller_source_products(new_call, state)


@router.callback_query(F.data.startswith("rs_disable_all:"))
async def reseller_disable_all(call: CallbackQuery, state: FSMContext):
    """Disable every product in a source at once."""
    if not await _has_reseller_perm(call.from_user.id):
        await call.answer("❌ No permission.", show_alert=True)
        return

    source_id = int(call.data.split(":")[1])
    async with Database().session() as s:
        products = (await s.execute(
            select(ResellerProduct).where(ResellerProduct.source_id == source_id)
        )).scalars().all()
        count = 0
        for p in products:
            if p.is_enabled:
                p.is_enabled = False
                count += 1
        await s.commit()

    await call.answer(f"❌ {count} products disabled.", show_alert=True)
    new_call = call.model_copy(update={'data': f"rs_source:{source_id}:0"})
    await reseller_source_products(new_call, state)


# ────────────────────────────────────────────────────────────────
#  Set Custom Price
# ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rs_set_price:"))
async def reseller_set_price_prompt(call: CallbackQuery, state: FSMContext):
    if not await _has_reseller_perm(call.from_user.id):
        await call.answer("❌ No permission.", show_alert=True)
        return

    product_id = int(call.data.split(":")[1])
    await state.update_data(rs_editing_product_id=product_id)
    await state.set_state(ResellerAdminStates.waiting_custom_price)
    await call.message.edit_text(
        "💲 <b>Set Custom Sell Price</b>\n\n"
        "Send the new price in USD (e.g. <code>2.99</code>).\n"
        "This overrides the auto-markup calculation.\n\n"
        "Send /cancel to abort.",
        parse_mode="HTML",
    )


@router.message(ResellerAdminStates.waiting_custom_price, F.text)
async def reseller_set_price_handler(message: Message, state: FSMContext):
    if not await _has_reseller_perm(message.from_user.id):
        return

    text = (message.text or "").strip()
    if text == "/cancel":
        await state.clear()
        await message.answer("Cancelled.")
        return

    try:
        price = Decimal(text.replace(",", "."))
        if price <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await message.answer("❌ Invalid price. Send a positive number like <code>2.99</code>.", parse_mode="HTML")
        return

    data = await state.get_data()
    product_id = data.get("rs_editing_product_id")
    if not product_id:
        await state.clear()
        return

    async with Database().session() as s:
        p = (await s.execute(
            select(ResellerProduct).where(ResellerProduct.id == product_id)
        )).scalars().first()
        if not p:
            await message.answer("Product not found.")
            await state.clear()
            return
        p.sell_price = price
        await s.commit()

    await message.answer(
        f"✅ Custom price set to <b>${price:.2f} USD</b> for <b>{p.name}</b>.",
        parse_mode="HTML",
    )
    await state.clear()


# ────────────────────────────────────────────────────────────────
#  Reset to Auto Price
# ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rs_reset_price:"))
async def reseller_reset_price(call: CallbackQuery, state: FSMContext):
    if not await _has_reseller_perm(call.from_user.id):
        await call.answer("❌ No permission.", show_alert=True)
        return

    product_id = int(call.data.split(":")[1])
    async with Database().session() as s:
        p = (await s.execute(
            select(ResellerProduct).where(ResellerProduct.id == product_id)
        )).scalars().first()
        if p:
            p.sell_price = None
            await s.commit()

    await call.answer("✅ Price reset to auto (cost × markup%).")
    new_call = call.model_copy(update={'data': f"rs_product:{product_id}"})
    await reseller_product_detail(new_call, state)


# ────────────────────────────────────────────────────────────────
#  Set Markup Percent
# ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rs_set_markup:"))
async def reseller_set_markup_prompt(call: CallbackQuery, state: FSMContext):
    if not await _has_reseller_perm(call.from_user.id):
        await call.answer("❌ No permission.", show_alert=True)
        return

    product_id = int(call.data.split(":")[1])
    await state.update_data(rs_editing_product_id=product_id)
    await state.set_state(ResellerAdminStates.waiting_markup_percent)
    await call.message.edit_text(
        "📊 <b>Set Markup Percentage</b>\n\n"
        "Send the markup % (e.g. <code>30</code> for 30%).\n"
        "This only applies when no custom price is set.\n\n"
        "Send /cancel to abort.",
        parse_mode="HTML",
    )


@router.message(ResellerAdminStates.waiting_markup_percent, F.text)
async def reseller_set_markup_handler(message: Message, state: FSMContext):
    if not await _has_reseller_perm(message.from_user.id):
        return

    text = (message.text or "").strip().rstrip("%")
    if text == "/cancel":
        await state.clear()
        await message.answer("Cancelled.")
        return

    try:
        markup = Decimal(text)
        if markup < 0 or markup > 999:
            raise ValueError
    except (InvalidOperation, ValueError):
        await message.answer("❌ Invalid markup. Send a number between 0 and 999.", parse_mode="HTML")
        return

    data = await state.get_data()
    product_id = data.get("rs_editing_product_id")

    async with Database().session() as s:
        p = (await s.execute(
            select(ResellerProduct).where(ResellerProduct.id == product_id)
        )).scalars().first()
        if not p:
            await message.answer("Product not found.")
            await state.clear()
            return
        p.markup_percent = markup
        await s.commit()

    await message.answer(
        f"✅ Markup set to <b>{markup}%</b> for <b>{p.name}</b>.\n"
        f"New auto price: <b>${float(p.cost_price) * (1 + float(markup)/100):.2f} USD</b>",
        parse_mode="HTML",
    )
    await state.clear()


# ────────────────────────────────────────────────────────────────
#  Set / Reset Category Override
# ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rs_set_cat:"))
async def reseller_set_category_prompt(call: CallbackQuery, state: FSMContext):
    if not await _has_reseller_perm(call.from_user.id):
        await call.answer("❌ No permission.", show_alert=True)
        return

    product_id = int(call.data.split(":")[1])
    await state.update_data(rs_editing_product_id=product_id)
    await state.set_state(ResellerAdminStates.waiting_category)

    from packages.database.methods.lazy_queries import query_categories, query_reseller_custom_categories
    from apps.telegram_bot.utils.category_resolver import KNOWN_CATEGORIES
    
    manual_categories = await query_categories(limit=100)
    custom_categories = await query_reseller_custom_categories()
    
    # Merge manual categories, custom categories and known API categories, removing duplicates and preserving order
    all_categories = list(dict.fromkeys(list(manual_categories) + list(custom_categories) + list(KNOWN_CATEGORIES)))
    
    kb = InlineKeyboardBuilder()
    for cat in all_categories:
        kb.button(text=f"📂 {cat}", callback_data=f"rscat:{cat[:30]}")
    kb.button(text="✍️ Type custom category", callback_data="rscat_custom")
    kb.button(text="❌ Cancel", callback_data=f"rs_product:{product_id}")
    kb.adjust(1)

    await call.message.edit_text(
        "📂 <b>Set Category</b>\n\n"
        "Choose an existing manual category below to merge this product into it, "
        "or click 'Type custom category'.",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

@router.callback_query(F.data.startswith("rscat:"))
async def reseller_set_category_callback(call: CallbackQuery, state: FSMContext):
    if not await _has_reseller_perm(call.from_user.id):
        return
    
    data = await state.get_data()
    product_id = data.get("rs_editing_product_id")
    if not product_id:
        await call.answer("Session expired.", show_alert=True)
        return
        
    cat_name = call.data.split(":", 1)[1]
    
    async with Database().session() as s:
        p = (await s.execute(
            select(ResellerProduct).where(ResellerProduct.id == product_id)
        )).scalars().first()
        if not p:
            await call.answer("Product not found.", show_alert=True)
            return
        p.category_override = cat_name
        await s.commit()

    await call.answer(f"✅ Category set to {cat_name}")
    new_call = call.model_copy(update={'data': f"rs_product:{product_id}"})
    await reseller_product_detail(new_call, state)

@router.callback_query(F.data == "rscat_custom")
async def reseller_set_category_custom(call: CallbackQuery, state: FSMContext):
    if not await _has_reseller_perm(call.from_user.id):
        return
    await state.set_state(ResellerAdminStates.waiting_category)
    await call.message.edit_text(
        "✍️ <b>Custom Category Name</b>\n\n"
        "Send the category name in chat. Send /cancel to abort.",
        parse_mode="HTML"
    )


@router.message(ResellerAdminStates.waiting_category, F.text)
async def reseller_set_category_handler(message: Message, state: FSMContext):
    if not await _has_reseller_perm(message.from_user.id):
        return

    text = (message.text or "").strip()
    if text.startswith("/"):
        await state.clear()
        await message.answer("Action cancelled because a command was sent.")
        return

    if len(text) > 64 or not text:
        await message.answer("❌ Category must be 1–64 characters.")
        return

    data = await state.get_data()
    product_id = data.get("rs_editing_product_id")
    if not product_id:
        await state.clear()
        return

    async with Database().session() as s:
        p = (await s.execute(
            select(ResellerProduct).where(ResellerProduct.id == product_id)
        )).scalars().first()
        if not p:
            await message.answer("Product not found.")
            await state.clear()
            return
        p.category_override = text
        await s.commit()

    await message.answer(
        f"✅ Category set to <b>{text}</b> for <b>{p.name}</b>.",
        parse_mode="HTML",
    )
    await state.clear()


@router.callback_query(F.data.startswith("rs_reset_cat:"))
async def reseller_reset_category(call: CallbackQuery, state: FSMContext):
    if not await _has_reseller_perm(call.from_user.id):
        await call.answer("❌ No permission.", show_alert=True)
        return

    product_id = int(call.data.split(":")[1])
    async with Database().session() as s:
        p = (await s.execute(
            select(ResellerProduct).where(ResellerProduct.id == product_id)
        )).scalars().first()
        if p:
            p.category_override = None
            await s.commit()

    await call.answer("✅ Category reset to auto.")
    new_call = call.model_copy(update={'data': f"rs_product:{product_id}"})
    await reseller_product_detail(new_call, state)


# ────────────────────────────────────────────────────────────────
#  Manual Sync
# ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "rs_sync_all")
async def reseller_sync_all(call: CallbackQuery, state: FSMContext):
    if not await _has_reseller_perm(call.from_user.id):
        await call.answer("❌ No permission.", show_alert=True)
        return

    await call.answer("🔄 Syncing all sources…")
    from packages.services.reseller.sync import sync_all_sources
    try:
        results = await sync_all_sources()
        parts = [
            f"{'✅' if res is not None else '❌'} <b>{escape(name.upper())}</b>: " + (f"{res.get('upserted', 0)} products refreshed" if res is not None else "sync failed")
            for name, res in results.items()
        ]
        summary = "\n".join(parts) if parts else "  No active sources."
        complete = all(res is not None for res in results.values())
        await call.message.edit_text(
            f"{'✅' if complete else '⚠️'} <b>Catalog sync {'complete' if complete else 'finished with errors'}</b>\n\n"
            f"{summary}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardBuilder().button(text="◀ Reseller catalog", callback_data="admin_resellers").as_markup(),
        )
    except Exception as exc:
        await call.message.edit_text(
            f"❌ <b>Catalog sync failed</b>\n\n<code>{escape(str(exc))}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardBuilder().button(text="◀ Reseller catalog", callback_data="admin_resellers").as_markup(),
        )


@router.callback_query(F.data.startswith("rs_sync:"))
async def reseller_sync_source(call: CallbackQuery, state: FSMContext):
    if not await _has_reseller_perm(call.from_user.id):
        await call.answer("❌ No permission.", show_alert=True)
        return

    source_id = int(call.data.split(":")[1])
    await call.answer("🔄 Syncing…")

    async with Database().session() as s:
        source_name = (await s.execute(
            select(ResellerSource.name).where(ResellerSource.id == source_id)
        )).scalar_one_or_none()
    if source_name is None:
        await call.message.edit_text(
            "❌ <b>Source not found</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardBuilder().button(text="◀ Reseller catalog", callback_data="admin_resellers").as_markup(),
        )
        return

    await call.message.edit_text(
        f"🔄 <b>Syncing {escape(source_name.upper())}</b>\n\n"
        "<i>Refreshing products, stock, and wholesale prices…</i>",
        parse_mode="HTML",
    )

    from packages.services.reseller.sync import sync_source
    data = await state.get_data()
    page = data.get("rs_source_page", 0)
    kb = InlineKeyboardBuilder()
    kb.button(text="📦 View products", callback_data=f"rs_source:{source_id}:{page}")
    kb.button(text="◀ Reseller catalog", callback_data="admin_resellers")
    kb.adjust(1)
    try:
        count = await sync_source(source_id)
        await call.message.edit_text(
            f"✅ <b>{escape(source_name.upper())} synced</b>\n\n"
            f"<b>{count}</b> products refreshed successfully.\n"
            "<i>Stock and wholesale prices are now up to date.</i>",
            parse_mode="HTML",
            reply_markup=kb.as_markup(),
        )
    except Exception as exc:
        await call.message.edit_text(
            f"❌ <b>{escape(source_name.upper())} sync failed</b>\n\n"
            f"<code>{escape(str(exc))}</code>\n\n"
            "The existing catalog was left unchanged.",
            parse_mode="HTML",
            reply_markup=kb.as_markup(),
        )


# ────────────────────────────────────────────────────────────────
#  Check API Balances
# ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "rs_balances")
async def reseller_balances(call: CallbackQuery, state: FSMContext):
    if not await _has_reseller_perm(call.from_user.id):
        await call.answer("❌ No permission.", show_alert=True)
        return

    await call.answer("💰 Checking balances…")
    lines = ["💰 <b>API Wallet Balances</b>\n"]

    if EnvKeys.FORKPIXEL_API_KEY:
        try:
            from packages.services.reseller.client import ForkPixelClient
            client = ForkPixelClient(
                api_key=EnvKeys.FORKPIXEL_API_KEY,
                base_url=EnvKeys.FORKPIXEL_BASE_URL,
                currency=EnvKeys.FORKPIXEL_CURRENCY,
            )
            bal = await client.get_balance()
            usd = bal.get("usd", bal.get("balance", "?"))
            lines.append(f"🔷 <b>ForkPixel:</b> ${usd} USD")
        except Exception as exc:
            lines.append(f"🔷 <b>ForkPixel:</b> Error — {exc}")

    if EnvKeys.CGPT_API_KEY:
        try:
            from packages.services.reseller.client import CGPTClient
            client = CGPTClient(api_key=EnvKeys.CGPT_API_KEY, base_url=EnvKeys.CGPT_BASE_URL)
            me = await client.get_me()
            bal = me.get("balance", "?")
            lines.append(f"🟢 <b>CGPT:</b> ${bal} USD")
        except Exception as exc:
            lines.append(f"🟢 <b>CGPT:</b> Error — {exc}")

    if EnvKeys.SAFWAN_API_KEY:
        try:
            from packages.services.reseller.client import SafwanTigerClient
            client = SafwanTigerClient(api_key=EnvKeys.SAFWAN_API_KEY, base_url=EnvKeys.SAFWAN_BASE_URL)
            bal_resp = await client.get_balance()
            bal = bal_resp.get("balance", "?")
            cur = bal_resp.get("currency", "USDT")
            lines.append(f"🐯 <b>SafwanTiger:</b> {bal} {cur}")
        except Exception as exc:
            lines.append(f"🐯 <b>SafwanTiger:</b> Error — {exc}")

    if EnvKeys.CANBOSO_API_KEY:
        try:
            from packages.services.reseller.client import CanbosoClient
            client = CanbosoClient(api_key=EnvKeys.CANBOSO_API_KEY, base_url=EnvKeys.CANBOSO_BASE_URL)
            bal_resp = await client.get_balance()
            bal = bal_resp.get("balanceUsd", bal_resp.get("balance", "?"))
            lines.append(f"🟨 <b>Canboso:</b> ${bal} USD")
        except Exception as exc:
            lines.append(f"🟨 <b>Canboso:</b> Error — {exc}")

    if EnvKeys.GGSOMA_API_KEY:
        try:
            from packages.services.reseller.client import GGSomaClient
            client = GGSomaClient(api_key=EnvKeys.GGSOMA_API_KEY, base_url=EnvKeys.GGSOMA_BASE_URL)
            bal_resp = await client.get_balance()
            bal = bal_resp.get("balance", "?")
            cur = bal_resp.get("currency", "USD")
            lines.append(f"💎 <b>GGSOMA:</b> ${bal} {cur}")
        except Exception as exc:
            lines.append(f"💎 <b>GGSOMA:</b> Error — {exc}")

    await call.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardBuilder().button(text="◀ Back", callback_data="admin_resellers").as_markup(),
    )
