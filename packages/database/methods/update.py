from sqlalchemy import exc, select, update

from packages.database.methods.read import invalidate_user_cache, invalidate_stats_cache, invalidate_item_cache, \
    invalidate_category_cache
from packages.database.methods.cache_utils import safe_create_task
from packages.database.models import User, Goods, Categories, BoughtGoods, Role
from packages.database.models.main import PromoCodes
from packages.database import Database
from apps.telegram_bot.i18n import localize


async def set_role(telegram_id: int, role: int) -> None:
    """Set user's role (by Telegram ID) and commit."""
    async with Database().session() as s:
        await s.execute(
            update(User).where(User.telegram_id == telegram_id).values(role_id=role)
        )

    safe_create_task(invalidate_user_cache(telegram_id))


async def update_balance(telegram_id: int, summ: float) -> None:
    """Increase user's balance by `summ` and commit."""
    async with Database().session() as s:
        await s.execute(
            update(User).where(User.telegram_id == telegram_id).values(balance=User.balance + summ)
        )

    safe_create_task(invalidate_user_cache(telegram_id))
    safe_create_task(invalidate_stats_cache())


async def update_user_discount(telegram_id: int, discount_percent: float) -> None:
    """Set user's persistent discount percent and commit."""
    from decimal import Decimal
    async with Database().session() as s:
        await s.execute(
            update(User).where(User.telegram_id == telegram_id).values(
                discount_percent=Decimal(str(discount_percent))
            )
        )
        await s.commit()

    safe_create_task(invalidate_user_cache(telegram_id))


async def update_item(item_name: str, new_name: str, description: str, price, category: str) -> tuple[bool, str | None]:
    """
    Update a Goods record with proper locking. Now uses integer PKs.
    """
    try:
        async with Database().session() as s:
            result = await s.execute(
                select(Goods).where(Goods.name == item_name).with_for_update()
            )
            goods = result.scalars().one_or_none()

            if not goods:
                return False, localize("admin.goods.update.position.invalid")

            cat_id = (await s.execute(
                select(Categories.id).where(Categories.name == category)
            )).scalar()
            if not cat_id:
                return False, localize("admin.goods.update.position.invalid")

            if new_name == item_name:
                goods.description = description
                goods.price = price
                goods.category_id = cat_id
                return True, None

            existing = (await s.execute(
                select(Goods).where(Goods.name == new_name)
            )).scalars().first()
            if existing:
                return False, localize("admin.goods.update.position.exists")

            goods.name = new_name
            goods.description = description
            goods.price = price
            goods.category_id = cat_id

            await s.execute(
                update(BoughtGoods).where(BoughtGoods.item_name == item_name).values(item_name=new_name)
            )

            safe_create_task(invalidate_item_cache(item_name, category))
            if new_name != item_name:
                safe_create_task(invalidate_item_cache(new_name, category))

            return True, None

    except exc.SQLAlchemyError as e:
        return False, f"DB Error: {e.__class__.__name__}"


async def set_user_blocked(telegram_id: int, blocked: bool) -> bool:
    """Set user blocked status and commit."""
    async with Database().session() as s:
        result = await s.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalars().first()
        if user:
            user.is_blocked = blocked
            safe_create_task(invalidate_user_cache(telegram_id))
            return True
        return False


async def is_user_blocked(telegram_id: int) -> bool:
    """Check if user is blocked."""
    async with Database().session() as s:
        result = await s.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalars().first()
        return user.is_blocked if user else False


async def update_category(category_name: str, new_name: str) -> None:
    """Rename a category. Handles Categories table rows, Goods, and ResellerProduct overrides."""
    from packages.database.models.main import ResellerProduct
    async with Database().session() as s:
        result = await s.execute(
            select(Categories).where(Categories.name == category_name).with_for_update()
        )
        category = result.scalars().one_or_none()

        if category:
            category.name = new_name
        else:
            # Create category row if it was dynamic
            s.add(Categories(name=new_name, original_name=category_name))

        # Update category_override on reseller products that were under category_name
        reseller_prods = (await s.execute(select(ResellerProduct))).scalars().all()
        for rp in reseller_prods:
            if rp.effective_category == category_name or rp.category_override == category_name:
                rp.category_override = new_name

        await s.commit()

    safe_create_task(invalidate_category_cache(category_name))
    if new_name != category_name:
        safe_create_task(invalidate_category_cache(new_name))


async def set_category_banner(category_name: str, file_id: str | None) -> bool:
    """Set (or clear) the banner file_id for a category. Returns True on success."""
    async with Database().session() as s:
        result = await s.execute(
            select(Categories).where(Categories.name == category_name).with_for_update()
        )
        category = result.scalars().one_or_none()
        if not category:
            return False
        category.banner_file_id = file_id
        return True


async def get_category_banner(category_name: str) -> str | None:
    """Return the banner file_id for a category, or None if not set."""
    async with Database().session() as s:
        result = await s.execute(
            select(Categories.banner_file_id).where(Categories.name == category_name)
        )
        return result.scalar()


async def update_role(role_id: int, name: str, permissions: int) -> tuple[bool, str | None]:
    """Update role name and permissions. Returns (success, error_message)."""
    async with Database().session() as s:
        result = await s.execute(
            select(Role).where(Role.id == role_id).with_for_update()
        )
        role = result.scalars().first()
        if not role:
            return False, "Role not found"
        if role.name != name:
            existing = (await s.execute(select(Role).where(Role.name == name))).scalars().first()
            if existing:
                return False, "Role name already exists"
        role.name = name
        role.permissions = permissions
        return True, None


async def toggle_promo_code(promo_id: int) -> bool | None:
    """Toggle promo code active status. Returns new is_active or None if not found."""
    async with Database().session() as s:
        result = await s.execute(
            select(PromoCodes).where(PromoCodes.id == promo_id).with_for_update()
        )
        promo = result.scalars().first()
        if not promo:
            return None
        promo.is_active = not promo.is_active
        return promo.is_active


async def reset_account_discount(telegram_id: int) -> bool:
    """Clear the user's account-upgrade discount (set discount_percent = 0)."""
    async with Database().session() as s:
        result = await s.execute(
            select(User).where(User.telegram_id == telegram_id).with_for_update()
        )
        user = result.scalars().first()
        if not user:
            return False
        user.discount_percent = 0
        await s.commit()
    safe_create_task(invalidate_user_cache(telegram_id))
    return True
