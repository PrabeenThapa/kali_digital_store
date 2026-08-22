from aiogram.filters.state import StatesGroup, State


class BroadcastFSM(StatesGroup):
    """FSM state for the broadcast message flow."""

    waiting_message = State()
