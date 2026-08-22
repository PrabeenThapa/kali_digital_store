from aiogram.filters.state import StatesGroup, State


class BalanceStates(StatesGroup):
    """FSM states for the balance top-up flow."""

    waiting_amount = State()
    waiting_payment = State()
    waiting_tx_hash = State()      # BEP20 / TRC20 manual top-up
    waiting_bybit_tx_id = State()  # Bybit UID transfer — user pastes tx/order ID
