from aiogram.filters.state import StatesGroup, State


class RoleMgmtFSM(StatesGroup):
    """FSM states for role management (create and edit)."""

    waiting_role_name = State()
    waiting_role_perms = State()
    editing_role_name = State()
    editing_role_perms = State()
