"""
Helper to create InlineKeyboardButton with icon_custom_emoji_id support.

Aiogram's InlineKeyboardButton doesn't officially support icon_custom_emoji_id yet
(it's a newer Telegram Bot API 9.4+ feature requiring Premium bot owner or Fragment username).

We inject the field directly into the button's model_extra so it gets serialized
correctly when Aiogram sends the JSON to Telegram's API.
"""
from aiogram.types import InlineKeyboardButton


def make_button(
    text: str,
    callback_data: str = None,
    url: str = None,
    icon_custom_emoji_id: str = None,
    style: str = None,
    **kwargs
) -> InlineKeyboardButton:
    """
    Create an InlineKeyboardButton with optional icon_custom_emoji_id.
    
    The icon_custom_emoji_id is passed via model_extra so Aiogram includes it
    in the API payload even though it's not in the official Pydantic schema yet.
    """
    btn_kwargs = {}
    if callback_data:
        btn_kwargs["callback_data"] = callback_data
    if url:
        btn_kwargs["url"] = url
    if style:
        btn_kwargs["style"] = style
    btn_kwargs.update(kwargs)
    
    if icon_custom_emoji_id and str(icon_custom_emoji_id).strip().isdigit():
        # Pass via model_extra to force-include in JSON payload
        btn = InlineKeyboardButton(text=text, **btn_kwargs)
        # Inject into __pydantic_extra__ so it's included in serialization
        if btn.__pydantic_extra__ is None:
            btn.__pydantic_extra__ = {}
        btn.__pydantic_extra__["icon_custom_emoji_id"] = str(icon_custom_emoji_id).strip()
        return btn
    
    return InlineKeyboardButton(text=text, **btn_kwargs)
