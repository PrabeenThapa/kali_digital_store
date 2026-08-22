from aiogram.fsm.state import StatesGroup, State


class CartStates(StatesGroup):
    """FSM states for the shopping cart view."""

    viewing_cart = State()
