from decimal import Decimal, InvalidOperation

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from packages.database.models import Permission
from packages.database.methods import get_item_info_cached, add_values_to_item, update_item, check_value, delete_only_items
from apps.telegram_bot.handlers.admin.adding_position_states import _notify_channel_upload
from apps.telegram_bot.keyboards.inline import back, question_buttons, simple_buttons
from packages.database.methods.audit import log_audit
from apps.telegram_bot.filters import HasPermissionFilter
from packages.config.config import EnvKeys
from apps.telegram_bot.i18n import localize
from apps.telegram_bot.states import UpdateItemFSM

router = Router()


@router.callback_query(F.data == 'update_item_amount', HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def update_item_amount_callback_handler(call: CallbackQuery, state):
    """Start the flow for adding values (stock) to an existing item."""
    await call.message.edit_text(
        localize('admin.goods.update.amount.prompt.name'),
        reply_markup=back("goods_management")
    )
    await state.set_state(UpdateItemFSM.waiting_item_name_for_amount_upd)


@router.message(UpdateItemFSM.waiting_item_name_for_amount_upd, F.text)
async def check_item_name_for_amount_upd(message: Message, state):
    """Validate that item exists and is NOT infinite before adding stock."""
    item_name = message.text.strip()
    item = await get_item_info_cached(item_name)
    if not item:
        await message.answer(
            localize('admin.goods.update.amount.not_exists'),
            reply_markup=back('goods_management')
        )
        return

    if await check_value(item_name):
        await message.answer(
            localize('admin.goods.update.amount.infinity_forbidden'),
            reply_markup=back('goods_management')
        )
        return

    await state.update_data(item_name=item_name)
    await message.answer(
        localize('admin.goods.add.values.prompt_multi'),
        reply_markup=back("goods_management")
    )
    await state.set_state(UpdateItemFSM.waiting_item_values_upd)


@router.message(UpdateItemFSM.waiting_item_values_upd, F.text)
async def updating_item_values(message: Message, state):
    """Accumulate values for the item. Show Finish button after first value."""
    data = await state.get_data()
    values = data.get('item_values', [])
    values.append(message.text)
    await state.update_data(item_values=values)

    await message.answer(
        localize('admin.goods.add.values.added', value=message.text, count=len(values)),
        reply_markup=simple_buttons([
            (localize('btn.add_values_finish'), "finish_updating_items"),
            (localize('btn.back'), "goods_management")
        ], per_row=1)
    )


@router.callback_query(F.data == 'finish_updating_items', UpdateItemFSM.waiting_item_values_upd)
async def updating_item_amount(call: CallbackQuery, state):
    """Finish adding new item values and optionally notify the channel."""
    data = await state.get_data()
    item_name = data.get('item_name')
    category_name = data.get('item_category', '')
    raw_values: list[str] = data.get("item_values", []) or []

    added = 0
    skipped_db_dup = 0
    skipped_batch_dup = 0
    skipped_invalid = 0
    seen_in_batch: set[str] = set()

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
        localize('admin.goods.update.values.result.title'),
        localize('admin.goods.add.result.added', n=added),
    ]
    if skipped_db_dup:
        text_lines.append(localize('admin.goods.add.result.skipped_db_dup', n=skipped_db_dup))
    if skipped_batch_dup:
        text_lines.append(localize('admin.goods.add.result.skipped_batch_dup', n=skipped_batch_dup))
    if skipped_invalid:
        text_lines.append(localize('admin.goods.add.result.skipped_invalid', n=skipped_invalid))

    await call.message.edit_text("\n".join(text_lines), parse_mode="HTML", reply_markup=back('goods_management'))
    await _notify_channel_upload(call.bot, item_name, category_name, added)

    admin_info = await call.message.bot.get_chat(call.from_user.id)
    await log_audit("add_item_values", user_id=call.from_user.id, resource_type="Item", resource_id=item_name,
                    details=f"admin={admin_info.first_name}, added={added}")
    await state.clear()


@router.callback_query(F.data == 'update_item', HasPermissionFilter(permission=Permission.CATALOG_MANAGE))
async def update_item_callback_handler(call: CallbackQuery, state):
    """Start the full item update flow."""
    await call.message.edit_text(localize('admin.goods.update.prompt.name'), reply_markup=back("goods_management"))
    await state.set_state(UpdateItemFSM.waiting_item_name_for_update)


@router.message(UpdateItemFSM.waiting_item_name_for_update, F.text)
async def check_item_name_for_update(message: Message, state):
    """Validate item exists and ask for a new name."""
    item_name = message.text.strip()
    item = await get_item_info_cached(item_name)
    if not item:
        await message.answer(
            localize('admin.goods.update.not_exists'),
            reply_markup=back('goods_management')
        )
        return

    from sqlalchemy import select
    from packages.database import Database
    from packages.database.models import Categories
    async with Database().session() as s:
        cat_name = (await s.execute(
            select(Categories.name).where(Categories.id == item['category_id'])
        )).scalar() or ""

    await state.update_data(item_old_name=item_name, item_category=cat_name)
    await message.answer(localize('admin.goods.update.prompt.new_name'), reply_markup=back('goods_management'))
    await state.set_state(UpdateItemFSM.waiting_item_new_name)


@router.message(UpdateItemFSM.waiting_item_new_name, F.text)
async def update_item_name(message: Message, state):
    """Ask for item description."""
    await state.update_data(item_new_name=message.text.strip())
    await message.answer(localize('admin.goods.update.prompt.description'), reply_markup=back('goods_management'))
    await state.set_state(UpdateItemFSM.waiting_item_description)


@router.message(UpdateItemFSM.waiting_item_description, F.text)
async def update_item_description(message: Message, state):
    """Ask for new price."""
    await state.update_data(item_description=message.text.strip())
    await message.answer(localize('admin.goods.add.prompt.price', currency=EnvKeys.PAY_CURRENCY),
                         reply_markup=back('goods_management'))
    await state.set_state(UpdateItemFSM.waiting_item_price)


@router.message(UpdateItemFSM.waiting_item_price, F.text)
async def update_item_price(message: Message, state):
    """Validate price then ask about infinity mode."""
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
    data = await state.get_data()
    item_old_name = data.get('item_old_name')

    if not await check_value(item_old_name):
        await message.answer(
            localize('admin.goods.update.infinity.make.question'),
            reply_markup=question_buttons('change_make_infinity', 'goods_management')
        )
    else:
        await message.answer(
            localize('admin.goods.update.infinity.deny.question'),
            reply_markup=question_buttons('change_deny_infinity', 'goods_management')
        )
    await state.set_state(UpdateItemFSM.waiting_make_infinity)


@router.callback_query(F.data.startswith('change_'), UpdateItemFSM.waiting_make_infinity)
async def update_item_process(call: CallbackQuery, state):
    """Handle infinity decision: no change, switch-to-infinite, or switch-to-regular."""
    parts = call.data.split('_')
    decision_scope = parts[1]   # make / deny
    decision_yesno = parts[3]   # yes / no

    data = await state.get_data()
    item_old_name = data.get('item_old_name')
    item_new_name = data.get('item_new_name')
    item_description = data.get('item_description')
    category = data.get('item_category')
    price = data.get('item_price')

    if decision_yesno == 'no':
        await update_item(item_old_name, item_new_name, item_description, price, category)
        await call.message.edit_text(localize('admin.goods.update.success'), reply_markup=back('goods_management'))
        admin_info = await call.message.bot.get_chat(call.from_user.id)
        await log_audit("update_item", user_id=call.from_user.id, resource_type="Item", resource_id=item_new_name,
                        details=f"admin={admin_info.first_name}, old_name={item_old_name}")
        await state.clear()
        return

    if decision_scope == 'make':
        await call.message.edit_text(
            localize('admin.goods.add.single.prompt_value'),
            reply_markup=back('goods_management')
        )
        await state.set_state(UpdateItemFSM.waiting_single_value)
    else:
        await call.message.edit_text(
            localize('admin.goods.add.values.prompt_multi'),
            reply_markup=back("goods_management")
        )
        await state.set_state(UpdateItemFSM.waiting_multiple_values)


@router.message(UpdateItemFSM.waiting_single_value, F.text)
async def update_item_infinity(message: Message, state):
    """Switch to infinite mode: purge values, add one infinite value, update meta."""
    data = await state.get_data()
    item_old_name = data.get('item_old_name')
    item_new_name = data.get('item_new_name')
    item_description = data.get('item_description')
    category = data.get('item_category')
    price = data.get('item_price')
    value = message.text

    await delete_only_items(item_old_name)
    await add_values_to_item(item_old_name, value, True)
    await update_item(item_old_name, item_new_name, item_description, price, category)

    await message.answer(localize('admin.goods.update.success'), reply_markup=back('goods_management'))
    admin_info = await message.bot.get_chat(message.from_user.id)
    await log_audit("update_item", user_id=message.from_user.id, resource_type="Item", resource_id=item_new_name,
                    details=f"admin={admin_info.first_name}, old_name={item_old_name}")
    await state.clear()


@router.message(UpdateItemFSM.waiting_multiple_values, F.text)
async def updating_item(message: Message, state):
    """Accumulate values for switch-to-regular mode."""
    data = await state.get_data()
    values = data.get('item_values', [])
    values.append(message.text)
    await state.update_data(item_values=values)

    await message.answer(
        localize('admin.goods.add.values.added', value=message.text, count=len(values)),
        reply_markup=simple_buttons([
            (localize('btn.add_values_finish'), "finish_update_item"),
            (localize('btn.back'), "goods_management")
        ], per_row=1)
    )


@router.callback_query(F.data == 'finish_update_item', UpdateItemFSM.waiting_multiple_values)
async def update_item_no_infinity(call: CallbackQuery, state):
    """Finalize switch to regular mode: purge values, add collected ones, update meta."""
    data = await state.get_data()
    item_old_name = data.get('item_old_name')
    item_new_name = data.get('item_new_name')
    item_description = data.get('item_description')
    category = data.get('item_category')
    price = data.get('item_price')
    raw_values: list[str] = data.get("item_values", []) or []

    added = 0
    skipped_db_dup = 0
    skipped_batch_dup = 0
    skipped_invalid = 0
    seen_in_batch: set[str] = set()

    await delete_only_items(item_old_name)

    for v in raw_values:
        v_norm = (v or "").strip()
        if not v_norm:
            skipped_invalid += 1
            continue
        if v_norm in seen_in_batch:
            skipped_batch_dup += 1
            continue
        seen_in_batch.add(v_norm)
        if await add_values_to_item(item_old_name, v_norm, False):
            added += 1
        else:
            skipped_db_dup += 1

    await update_item(item_old_name, item_new_name, item_description, price, category)

    text_lines = [
        localize('admin.goods.update.success'),
        localize('admin.goods.add.result.added', n=added),
    ]
    if skipped_db_dup:
        text_lines.append(localize('admin.goods.add.result.skipped_db_dup', n=skipped_db_dup))
    if skipped_batch_dup:
        text_lines.append(localize('admin.goods.add.result.skipped_batch_dup', n=skipped_batch_dup))
    if skipped_invalid:
        text_lines.append(localize('admin.goods.add.result.skipped_invalid', n=skipped_invalid))

    await call.message.edit_text("\n".join(text_lines), parse_mode="HTML", reply_markup=back('goods_management'))
    await _notify_channel_upload(call.bot, item_new_name, category, added)

    admin_info = await call.message.bot.get_chat(call.from_user.id)
    await log_audit("update_item", user_id=call.from_user.id, resource_type="Item", resource_id=item_new_name,
                    details=f"admin={admin_info.first_name}, old_name={item_old_name}")
    await state.clear()
