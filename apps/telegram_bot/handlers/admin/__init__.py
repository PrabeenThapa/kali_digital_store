from aiogram import Router, F
from aiogram.enums.chat_type import ChatType

from .main import router as main_router
from .adding_position_states import router as adding_position_states_router
from .broadcast import router as broadcast_router
from .categories_management_states import router as categories_management_router
from .goods_management_states import router as goods_management_router
from .shop_management_states import router as shop_management_router
from .update_position_states import router as update_position_router
from .user_management_states import router as user_management_router
from .role_management_states import router as role_management_router
from .promo_management_states import router as promo_management_router
from .support_relay import router as support_relay_router
from .reseller_management import router as reseller_management_router
from .menu_icons_states import router as menu_icons_states_router
from .discussion_groups_states import router as discussion_groups_states_router

router = Router()
router.include_router(support_relay_router)  # relay first — handles support group messages

# Sub-router for all admin control panels — strictly restricted to private chats (PM only)
admin_pm_router = Router()
admin_pm_router.message.filter(F.chat.type == ChatType.PRIVATE)
admin_pm_router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)

admin_pm_router.include_router(main_router)
admin_pm_router.include_router(adding_position_states_router)
admin_pm_router.include_router(broadcast_router)
admin_pm_router.include_router(categories_management_router)
admin_pm_router.include_router(goods_management_router)
admin_pm_router.include_router(shop_management_router)
admin_pm_router.include_router(update_position_router)
admin_pm_router.include_router(user_management_router)
admin_pm_router.include_router(role_management_router)
admin_pm_router.include_router(promo_management_router)
admin_pm_router.include_router(reseller_management_router)
admin_pm_router.include_router(menu_icons_states_router)
admin_pm_router.include_router(discussion_groups_states_router)

router.include_router(admin_pm_router)
