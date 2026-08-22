from aiogram.filters.state import State, StatesGroup


class ShopStates(StatesGroup):
    """FSM states for the shopping section (browsing, purchases)."""

    viewing_goods = State()
    viewing_bought_items = State()
    viewing_categories = State()
