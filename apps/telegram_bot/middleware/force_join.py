import logging
from typing import Dict, Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from packages.config.config import EnvKeys
from apps.telegram_bot.keyboards import check_sub
from apps.telegram_bot.i18n import localize
from apps.telegram_bot.handlers.other import _parse_channel_username, check_sub_channel

logger = logging.getLogger(__name__)

class ForceJoinMiddleware(BaseMiddleware):
    """
    Middleware that mandates users to join a specific discussion group or channel.
    Blocks updates if the user is not a member of EnvKeys.CHANNEL_ID.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Force join checks ONLY apply to private chat interactions with the bot.
        # Never block or post subscribe alerts in group chats, supergroups, or channel discussions!
        if isinstance(event, Message) and event.chat and event.chat.type != "private":
            return await handler(event, data)

        if isinstance(event, CallbackQuery) and event.message and event.message.chat and event.message.chat.type != "private":
            return await handler(event, data)

        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if not user:
            return await handler(event, data)
        
        # If no CHANNEL_ID is configured, skip
        if not EnvKeys.CHANNEL_ID:
            return await handler(event, data)

        channel_username = _parse_channel_username()
        if not channel_username:
            return await handler(event, data)

        # Allow sub_channel_done to proceed so user can click "Check Subscription"
        if isinstance(event, CallbackQuery) and event.data == "sub_channel_done":
            return await handler(event, data)
            
        # Exempt /start for NEW users so they can be registered in the database and referral processed
        if isinstance(event, Message) and event.text and event.text.startswith('/start'):
            from packages.database.methods import check_user_cached
            user_data = await check_user_cached(user.id)
            if not user_data:
                return await handler(event, data)
            
        chat_id = int(EnvKeys.CHANNEL_ID) if str(EnvKeys.CHANNEL_ID).lstrip('-').isdigit() else f"@{channel_username}"
        bot = event.bot

        try:
            chat_member = await bot.get_chat_member(chat_id=chat_id, user_id=user.id)
            is_member = await check_sub_channel(chat_member)
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            logger.warning(f"Force join check failed for user {user.id}: {e}")
            is_member = True # Fail open to avoid blocking users if bot lacks permissions

        if not is_member:
            markup = check_sub(channel_username)
            if isinstance(event, Message):
                await event.answer(localize("subscribe.prompt"), reply_markup=markup)
            elif isinstance(event, CallbackQuery):
                await event.message.answer(localize("subscribe.prompt"), reply_markup=markup)
                await event.answer()
            return None # Block further processing

        return await handler(event, data)
