from aiogram import Router, F
from aiogram.enums.chat_type import ChatType

from .main import router as main_router
from .balance_and_payment import router as balance_and_payment_router
from .shop_and_goods import router as shop_and_goods_router
from .referral_system import router as referral_system_router
from .cart import router as cart_router
from .support import router as support_router
from .web_auth import router as web_auth_router

router = Router()

# Restrict all user interaction handlers to private chats (PM only)
user_pm_router = Router()
user_pm_router.message.filter(F.chat.type == ChatType.PRIVATE)
user_pm_router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)

user_pm_router.include_router(support_router)   # support first — catches SupportStates.chatting
user_pm_router.include_router(main_router)
user_pm_router.include_router(balance_and_payment_router)
user_pm_router.include_router(shop_and_goods_router)
user_pm_router.include_router(referral_system_router)
user_pm_router.include_router(cart_router)
user_pm_router.include_router(web_auth_router)

router.include_router(user_pm_router)
