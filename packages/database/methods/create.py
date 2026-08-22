from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, exists

from packages.database.models import User, ItemValues, Goods, Categories, Operations, Payments, ReferralEarnings, Role
from packages.database.models.main import PromoCodes, CartItems, Reviews
from packages.database.engine import Database
from packages.database.methods.cache_utils import safe_create_task
from packages.database.methods.read import invalidate_stats_cache, invalidate_user_cache


async def create_user(telegram_id: int, registration_date: datetime, referral_id: int | None, role: int = 1) -> tuple[bool, int | None]:
    """Create user if missing.

    Returns (is_new, valid_referrer_id):
    - is_new: True if the user row was inserted this call, False if it already existed
    - valid_referrer_id: the referrer's telegram_id when the signup should trigger a referral credit
      (only set when is_new is True, referral_id was provided, and the referrer exists and isn't the same user)
    """
    async with Database().session() as s:
        result = await s.execute(select(exists().where(User.telegram_id == telegram_id)))
        if result.scalar():
            return False, None

        valid_ref = None
        if referral_id and referral_id != telegram_id:
            ref_exists = (await s.execute(
                select(exists().where(User.telegram_id == referral_id))
            )).scalar()
            if ref_exists:
                valid_ref = referral_id

        s.add(
            User(
                telegram_id=telegram_id,
                role_id=role,
                registration_date=registration_date,
                referral_id=valid_ref,
            )
        )
        return True, valid_ref


async def credit_signup_referral_bonus(referrer_id: int, referral_id: int, bonus: Decimal) -> bool:
    """Credit a flat signup bonus to a referrer for a newly-signed-up referral.

    Idempotent: uses a unique row on ReferralEarnings.original_amount == 0 as the signup marker;
    if a signup record already exists for this pair, does nothing.
    Returns True if credited.
    """
    if bonus <= 0:
        return False

    async with Database().session() as s:
        already = (await s.execute(
            select(exists().where(
                ReferralEarnings.referrer_id == referrer_id,
                ReferralEarnings.referral_id == referral_id,
                ReferralEarnings.original_amount == 0,
            ))
        )).scalar()
        if already:
            return False

        referrer = (await s.execute(
            select(User).where(User.telegram_id == referrer_id).with_for_update()
        )).scalars().one_or_none()
        if not referrer:
            return False

        referrer.balance += bonus
        s.add(ReferralEarnings(
            referrer_id=referrer_id,
            referral_id=referral_id,
            amount=bonus,
            original_amount=Decimal("0"),
        ))

    safe_create_task(invalidate_user_cache(referrer_id))
    safe_create_task(invalidate_stats_cache())
    return True


async def create_item(item_name: str, item_description: str, item_price: Decimal | int, category_name: str, cost_price: Decimal | int = 0) -> None:
    """Insert item (goods); commit. Resolves category_name to category_id."""
    async with Database().session() as s:
        result = await s.execute(select(exists().where(Goods.name == item_name)))
        if result.scalar():
            return
        cat = (await s.execute(select(Categories.id).where(Categories.name == category_name))).scalar()
        if not cat:
            return
        s.add(
            Goods(
                name=item_name,
                description=item_description,
                price=item_price,
                cost_price=cost_price,
                category_id=cat,
            )
        )

    safe_create_task(invalidate_stats_cache())


async def add_values_to_item(item_name: str, value: str, is_infinity: bool) -> bool:
    """Add item value if not duplicate; True if inserted. Resolves item_name to item_id."""
    value_norm = (value or "").strip()
    if not value_norm:
        return False

    async with Database().session() as s:
        item_id = (await s.execute(select(Goods.id).where(Goods.name == item_name))).scalar()
        if not item_id:
            return False

        dup = (await s.execute(
            select(exists().where(
                ItemValues.item_id == item_id,
                ItemValues.value == value_norm,
            ))
        )).scalar()
        if dup:
            return False

        try:
            s.add(ItemValues(item_id=item_id, value=value_norm, is_infinity=bool(is_infinity)))
            await s.flush()
            from packages.database.methods.read import invalidate_item_cache
            from packages.database.methods.cache_utils import safe_create_task
            safe_create_task(invalidate_item_cache(item_name))
            return True
        except Exception:
            return False


async def create_category(category_name: str) -> None:
    """Insert category; commit."""
    async with Database().session() as s:
        result = await s.execute(select(exists().where(Categories.name == category_name)))
        if result.scalar():
            return
        s.add(Categories(name=category_name))

    safe_create_task(invalidate_stats_cache())


async def create_operation(user_id: int, value: int, operation_time: datetime) -> None:
    """Record completed balance operation; commit."""
    async with Database().session() as s:
        s.add(Operations(user_id, value, operation_time))


async def create_pending_payment(provider: str, external_id: str, user_id: int, amount: int | float | Decimal, currency: str) -> None:
    """Create pending payment."""
    from packages.database.models import PaymentStatus
    async with Database().session() as s:
        s.add(Payments(
            provider=provider,
            external_id=external_id,
            user_id=user_id,
            amount=Decimal(str(amount)),
            currency=currency,
            status=PaymentStatus.PENDING
        ))


async def create_referral_earning(referrer_id: int, referral_id: int, amount: int, original_amount: int) -> None:
    """Create a referral credit record."""
    async with Database().session() as s:
        s.add(
            ReferralEarnings(
                referrer_id=referrer_id,
                referral_id=referral_id,
                amount=Decimal(amount),
                original_amount=Decimal(original_amount)
            )
        )


async def create_role(name: str, permissions: int) -> int | None:
    """Create a new role. Returns the new role ID, or None if name conflict."""
    async with Database().session() as s:
        result = await s.execute(select(exists().where(Role.name == name)))
        if result.scalar():
            return None
        role = Role(name=name, permissions=permissions)
        s.add(role)
        await s.flush()
        return role.id


async def create_promo_code(
    code: str,
    discount_type: str,
    discount_value,
    max_uses: int = 0,
    max_uses_per_user: int = 1,
    expires_at=None,
    category_id: int = None,
    item_id: int = None,
) -> int | None:
    """Create a promo code. Returns ID or None if code already exists."""
    from decimal import Decimal
    async with Database().session() as s:
        result = await s.execute(select(exists().where(PromoCodes.code == code.upper())))
        if result.scalar():
            return None
        promo = PromoCodes(
            code=code.upper(),
            discount_type=discount_type,
            discount_value=Decimal(str(discount_value)),
            max_uses=max_uses,
            max_uses_per_user=max_uses_per_user,
            expires_at=expires_at,
            category_id=category_id,
            item_id=item_id,
        )
        s.add(promo)
        await s.flush()
        return promo.id


async def add_to_cart(user_id: int, item_name: str, promo_code: str = None) -> tuple[bool, str]:
    """Add item to user's cart. Returns (success, message)."""
    from sqlalchemy import func as sa_func
    CART_MAX_ITEMS = 10
    async with Database().session() as s:
        count = (await s.execute(
            select(sa_func.count(CartItems.id)).where(CartItems.user_id == user_id)
        )).scalar() or 0
        if count >= CART_MAX_ITEMS:
            return False, "cart_full"

        # Check item exists
        item_exists = (await s.execute(
            select(exists().where(Goods.name == item_name))
        )).scalar()
        if not item_exists:
            return False, "item_not_found"

        s.add(CartItems(user_id=user_id, item_name=item_name, promo_code=promo_code))
        return True, "success"



async def create_review(user_id: int, item_name: str, rating: int, text: str = None) -> int | None:
    """Create a review. Returns ID or None if already reviewed."""
    async with Database().session() as s:
        existing = (await s.execute(
            select(exists().where(
                Reviews.user_id == user_id,
                Reviews.item_name == item_name
            ))
        )).scalar()
        if existing:
            return None
        review = Reviews(
            user_id=user_id,
            item_name=item_name,
            rating=rating,
            text=text,
        )
        s.add(review)
        await s.flush()
        return review.id
