import math
from decimal import Decimal, InvalidOperation

from aiogram import Router, F
from aiogram.exceptions import TelegramForbiddenError, TelegramNotFound, TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from packages.database.models import Permission
from packages.database.methods import (
    get_item_info_cached, create_item, add_values_to_item, query_categories
)
from apps.telegram_bot.handlers.other import _parse_channel_username
from apps.telegram_bot.keyboards.inline import back, question_buttons, simple_buttons, admin_category_picker_keyboard
from packages.database.methods.audit import log_audit
from apps.telegram_bot.filters import HasPermissionFilter
from packages.config.config import EnvKeys
from apps.telegram_bot.i18n import localize
from apps.telegram_bot.states import AddItemFSM

router = Router()

_PAGE_SIZE = 8


async def _notify_channel_upload(bot, item_name: str, category_name: str, count) -> None:
    """Notify the configured channel about a new stock upload. Silently ignores errors."""
    channel_username = _parse_channel_username()
    chat_id = int(EnvKeys.CHANNEL_ID) if EnvKeys.CHANNEL_ID else (f"@{channel_username}" if channel_username else "@kds_alert")
    try:
        from packages.database.methods.read import get_item_info_cached
        from apps.telegram_bot.keyboards.inline import simple_buttons
        
        item_data = await get_item_info_cached(item_name)
        if item_data:
            price = item_data.get('price', 0)
            stock = item_data.get('count', 0)
        else:
            price = 0
            stock = count
            
        cat_emoji = category_name.split()[0] if category_name and len(category_name) > 0 and not category_name[0].isalnum() else "🛍️"
        
        text = f"📣 <b>{count}</b> new stock added for <b>{item_name}</b>!"
        btn_text = f"{cat_emoji} {item_name} - {price} {EnvKeys.PAY_CURRENCY} (Stock: {stock})"
        
        # We use 'shop' callback so clicking it opens the main shop menu.
        markup = simple_buttons([(btn_text, "shop")], per_row=1)

        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode='HTML',
            reply_markup=markup
        )
    except (TelegramForbiddenError, TelegramNotFound, TelegramBadRequest):
        pass


# ── STEP 1: Show category picker first ──────────────────────────────────────

@router.callback_query(F.data == 'add_item', HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def add_item_callback_handler(call: CallbackQuery, state):
    """
    STEP 1 — Show category picker inline keyboard.
    Admin selects a category before typing the product name.
    """
    categories = await query_categories(offset=0, limit=_PAGE_SIZE)
    total = await query_categories(count_only=True)
    total_pages = max(1, math.ceil(total / _PAGE_SIZE))

    if not categories:
        await call.message.edit_text(
            localize('admin.goods.add.category.none_exist'),
            reply_markup=back('goods_management')
        )
        return

    await state.update_data(_cat_page=0, _cat_page_size=_PAGE_SIZE)
    await call.message.edit_text(
        "📂 <b>Add New Product</b>\n\n"
        "<i>Step 1 of 6 — Select a category for the new product:</i>",
        reply_markup=admin_category_picker_keyboard(categories, page=0, total_pages=total_pages),
        parse_mode="HTML",
    )
    await state.set_state(AddItemFSM.waiting_category)


# ── Category page navigation ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith('pick_cat_page:'), AddItemFSM.waiting_category)
async def pick_cat_page_handler(call: CallbackQuery, state):
    """Navigate between category picker pages."""
    data = await state.get_data()
    page_size = data.get('_cat_page_size', _PAGE_SIZE)
    try:
        page = int(call.data.split(':', 1)[1])
    except (ValueError, IndexError):
        await call.answer()
        return

    categories = await query_categories(offset=page * page_size, limit=page_size)
    total = await query_categories(count_only=True)
    total_pages = max(1, math.ceil(total / page_size))

    await state.update_data(_cat_page=page)
    await call.message.edit_text(
        "📂 <b>Add New Product</b>\n\n"
        "<i>Step 1 of 6 — Select a category for the new product:</i>",
        reply_markup=admin_category_picker_keyboard(categories, page=page, total_pages=total_pages),
        parse_mode="HTML",
    )
    await call.answer()


# ── STEP 2: Category selected → ask for product name ─────────────────────────

@router.callback_query(F.data.startswith('pick_cat:'), AddItemFSM.waiting_category)
async def pick_category_for_add_item(call: CallbackQuery, state):
    """STEP 2 — Category chosen. Save it and ask the admin to type the product name."""
    category_name = call.data.split(':', 1)[1]
    if not category_name:
        await call.answer(localize('admin.goods.add.category.not_found'), show_alert=True)
        return

    await state.update_data(item_category=category_name)
    await call.message.edit_text(
        f"📂 <b>Category:</b> {category_name}\n\n"
        "📝 <b>Step 2 of 6</b> — Enter the <b>product name</b>:",
        reply_markup=back('add_item'),
        parse_mode="HTML",
    )
    await state.set_state(AddItemFSM.waiting_item_name)
    await call.answer()


# ── STEP 3: Product name → description ───────────────────────────────────────

@router.message(AddItemFSM.waiting_item_name, F.text)
async def check_item_name_for_add(message: Message, state):
    """STEP 3 — Validate name uniqueness, then ask for description."""
    item_name = (message.text or "").strip()
    item = await get_item_info_cached(item_name)
    if item:
        await message.answer(
            localize('admin.goods.add.name.exists'),
            reply_markup=back('goods_management')
        )
        return

    await state.update_data(item_name=item_name)
    await message.answer(
        f"📝 <b>Product name:</b> {item_name}\n\n"
        "<b>Step 3 of 6</b> — Enter a <b>description</b>:",
        reply_markup=back('goods_management'),
        parse_mode="HTML",
    )
    await state.set_state(AddItemFSM.waiting_item_description)


# ── STEP 4: Description → price ───────────────────────────────────────────────

@router.message(AddItemFSM.waiting_item_description, F.text)
async def add_item_description(message: Message, state):
    """STEP 4 — Save description and ask for price."""
    await state.update_data(item_description=(message.text or "").strip())
    await message.answer(
        f"<b>Step 4 of 6</b> — Enter the <b>price</b> in {EnvKeys.PAY_CURRENCY}:\n<i>Examples: 5, 1.5, 14.99</i>",
        reply_markup=back('goods_management'),
        parse_mode="HTML",
    )
    await state.set_state(AddItemFSM.waiting_item_price)


# ── STEP 5: Price → infinity question ────────────────────────────────────────

@router.message(AddItemFSM.waiting_item_price, F.text)
async def add_item_price(message: Message, state):
    """STEP 5 — Validate price, then ask about infinite stock mode."""
    price_text = (message.text or "").strip().replace(",", ".")
    try:
        price = Decimal(price_text)
        if price <= 0:
            raise InvalidOperation
    except InvalidOperation:
        await message.answer(
            "⚠️ Invalid price. Enter a positive number (e.g. 5, 1.5, 14.99):",
            reply_markup=back('goods_management')
        )
        return

    await state.update_data(item_price=str(price))
    await message.answer(
        f"💰 <b>Price set:</b> {price} {EnvKeys.PAY_CURRENCY}\n\n"
        f"<b>Step 5 of 6</b> — {localize('admin.goods.add.infinity.question')}",
        reply_markup=question_buttons('infinity', 'goods_management'),
        parse_mode="HTML",
    )
    await state.set_state(AddItemFSM.waiting_infinity)


# ── STEP 6: Infinity mode → collect values ────────────────────────────────────

@router.callback_query(F.data.startswith('infinity_'), AddItemFSM.waiting_infinity)
async def adding_value_to_position(call: CallbackQuery, state):
    """STEP 6 — Route to single-value (infinite) or multi-value collection."""
    answer = call.data.split('_')[1]
    await state.update_data(is_infinity=(answer == 'yes'))

    if answer == 'no':
        await call.message.edit_text(
            "<b>Step 6 of 6</b> — Send stock codes one per message (or paste multiple lines at once).\n\n"
            + localize('admin.goods.add.values.prompt_multi'),
            reply_markup=back("goods_management"),
            parse_mode="HTML",
        )
        await state.set_state(AddItemFSM.waiting_values)
    else:
        await call.message.edit_text(
            "<b>Step 6 of 6</b> — " + localize('admin.goods.add.single.prompt_value'),
            reply_markup=back('goods_management'),
            parse_mode="HTML",
        )
        await state.set_state(AddItemFSM.waiting_single_value)


# ── Multi-value collection ────────────────────────────────────────────────────

@router.message(AddItemFSM.waiting_values, F.text)
async def collect_item_value(message: Message, state):
    """Accumulate values in FSM state. After the first one — show a Finish button."""
    data = await state.get_data()
    values = data.get('item_values', [])
    value = (message.text or "")
    values.append(value)
    await state.update_data(item_values=values)

    await message.answer(
        localize('admin.goods.add.values.added', value=value, count=len(values)),
        reply_markup=simple_buttons([
            (localize('btn.add_values_finish'), "finish_adding_items"),
            (localize('btn.back'), "goods_management")
        ], per_row=1)
    )


@router.callback_query(F.data == 'finish_adding_items', AddItemFSM.waiting_values)
async def finish_adding_items_callback_handler(call: CallbackQuery, state):
    """Create a position, add all collected values, notify group (if configured)."""
    data = await state.get_data()
    item_name = data.get('item_name')
    item_description = data.get('item_description')
    item_price = data.get('item_price')
    category_name = data.get('item_category')
    raw_values: list[str] = data.get("item_values", []) or []

    added = 0
    skipped_db_dup = 0
    skipped_batch_dup = 0
    skipped_invalid = 0
    seen_in_batch: set[str] = set()

    price_decimal = Decimal(str(item_price))
    await create_item(item_name, item_description, price_decimal, category_name)

    from packages.database.methods.read import invalidate_item_cache
    await invalidate_item_cache(item_name, category_name)

    for v in raw_values:
        v_norm = (v or "").strip()
        if not v_norm:
            skipped_invalid += 1
            continue
        if v_norm in seen_in_batch:
            skipped_batch_dup += 1
            continue
        seen_in_batch.add(v_norm)
        if await add_values_to_item(item_name, v_norm, False):
            added += 1
        else:
            skipped_db_dup += 1

    text_lines = [
        localize('admin.goods.add.result.created'),
        localize('admin.goods.add.result.added', n=added)
    ]
    if skipped_db_dup:
        text_lines.append(localize('admin.goods.add.result.skipped_db_dup', n=skipped_db_dup))
    if skipped_batch_dup:
        text_lines.append(localize('admin.goods.add.result.skipped_batch_dup', n=skipped_batch_dup))
    if skipped_invalid:
        text_lines.append(localize('admin.goods.add.result.skipped_invalid', n=skipped_invalid))

    await call.message.edit_text("\n".join(text_lines), parse_mode="HTML", reply_markup=back("goods_management"))
    await _notify_channel_upload(call.bot, item_name, category_name, added)

    admin_info = await call.message.bot.get_chat(call.from_user.id)
    await log_audit("create_item", user_id=call.from_user.id, resource_type="Item", resource_id=item_name,
                    details=f"admin={admin_info.first_name}, category={category_name}")
    await state.clear()


# ── Single (infinite) value ───────────────────────────────────────────────────

@router.message(AddItemFSM.waiting_single_value, F.text)
async def finish_adding_item_callback_handler(message: Message, state):
    """Create a position and add one infinite value. Notify group (if configured)."""
    data = await state.get_data()
    item_name = data.get('item_name')
    item_description = data.get('item_description')
    item_price = data.get('item_price')
    category_name = data.get('item_category')

    single_value = (message.text or "").strip()
    if not single_value:
        await message.answer(localize('admin.goods.add.single.empty'), reply_markup=back('goods_management'))
        return

    price_decimal = Decimal(str(item_price))
    await create_item(item_name, item_description, price_decimal, category_name)
    await add_values_to_item(item_name, single_value, True)

    from packages.database.methods.read import invalidate_item_cache
    await invalidate_item_cache(item_name, category_name)

    await _notify_channel_upload(message.bot, item_name, category_name, "∞")

    await message.answer(localize('admin.goods.add.single.created'), reply_markup=back('goods_management'))
    admin_info = await message.bot.get_chat(message.from_user.id)
    await log_audit("create_item", user_id=message.from_user.id, resource_type="Item", resource_id=item_name,
                    details=f"admin={admin_info.first_name}, category={category_name}, infinite=true")
    await state.clear()
