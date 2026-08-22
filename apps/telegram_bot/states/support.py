from aiogram.fsm.state import State, StatesGroup


class SupportStates(StatesGroup):
    chatting = State()   # User is in live support mode — all messages relay to topic


class AdminSupportReplyStates(StatesGroup):
    waiting_for_reply = State()


class AdminDeliverItemStates(StatesGroup):
    waiting_for_content = State()
    waiting_for_confirmation = State()
