from aiogram.fsm.state import StatesGroup, State


class ReviewFSM(StatesGroup):
    """FSM states for the product review flow."""

    waiting_rating = State()
    waiting_text = State()
