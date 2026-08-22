from aiogram.filters.state import StatesGroup, State


class GoodsFSM(StatesGroup):
    """FSM for position (goods) and item management scenarios."""

    waiting_item_name_delete = State()
    waiting_item_name_show = State()
    waiting_bought_item_id = State()
    waiting_stock_add = State()       # New: click-to-add-stock flow
    waiting_admin_balance_amount = State()  # Admin top-up/deduct user balance



class AddItemFSM(StatesGroup):
    """
    FSM for step-by-step creation of a product position:
    category → name → description → price → mode → values.
    """

    waiting_category = State()       # Step 1 — pick category (inline buttons)
    waiting_item_name = State()      # Step 2 — type product name
    waiting_item_description = State()  # Step 3 — type description
    waiting_item_price = State()     # Step 4 — type price
    waiting_infinity = State()       # Step 5 — yes/no infinite stock
    waiting_values = State()         # Step 6a — collect multiple stock codes
    waiting_single_value = State()   # Step 6b — enter one infinite value


class UpdateItemFSM(StatesGroup):
    """
    FSM for updating an existing product:
    - add stock values to an existing position
    - full update (name, description, price, mode, values)
    """

    # Add values
    waiting_item_name_for_amount_upd = State()
    waiting_item_values_upd = State()

    # Full update
    waiting_item_name_for_update = State()
    waiting_item_new_name = State()
    waiting_item_description = State()
    waiting_item_price = State()
    waiting_make_infinity = State()
    waiting_single_value = State()
    waiting_multiple_values = State()
    waiting_item_icon = State()
