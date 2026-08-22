from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select, exists as sa_exists, delete as sa_delete
from sqlalchemy.exc import IntegrityError

from packages.database.models import User, ItemValues, Goods, BoughtGoods, Payments, Operations, PaymentStatus, PaymentProvider
from packages.database.models.main import PromoCodes, PromoCodeUsages, CartItems, ReferralEarnings
from packages.database import Database
from packages.config.config import EnvKeys
from packages.database.methods.read import invalidate_user_cache, invalidate_stats_cache, invalidate_item_cache
from packages.database.methods.cache_utils import safe_create_task
from packages.database.methods.audit import log_audit


async def buy_item_transaction(telegram_id: int, item_name: str, promo_code: str = None) -> tuple[bool, str, dict | None]:
    """
    Complete transactional purchase of goods with checks and locks.
    Returns: (success, message, purchase_data)
    """
    max_retries = 3
    for attempt in range(max_retries):
        async with Database().session() as s:
            try:
                # 1. Lock the user to check the balance
                user = (await s.execute(
                    select(User).where(User.telegram_id == telegram_id).with_for_update()
                )).scalars().one_or_none()

                if not user:
                    await s.rollback()
                    return False, "user_not_found", None

                # 2. Get information about the product
                goods = (await s.execute(
                    select(Goods).where(Goods.name == item_name).with_for_update()
                )).scalars().one_or_none()

                if not goods:
                    await s.rollback()
                    return False, "item_not_found", None

                price = Decimal(str(goods.price))
                final_price = price
                discount_info = None

                # 2.5. Apply promo code if provided
                if promo_code:
                    promo = (await s.execute(
                        select(PromoCodes).where(PromoCodes.code == promo_code.upper()).with_for_update()
                    )).scalars().first()

                    if not promo or not promo.is_active:
                        await s.rollback()
                        return False, "promo_invalid", None

                    if promo.discount_type == "balance":
                        await s.rollback()
                        return False, "promo_invalid", None

                    if promo.expires_at and promo.expires_at < datetime.now(timezone.utc):
                        await s.rollback()
                        return False, "promo_expired", None

                    if promo.max_uses > 0 and promo.current_uses >= promo.max_uses:
                        await s.rollback()
                        return False, "promo_max_uses", None

                    # Check per-user usage
                    from sqlalchemy import func as sa_func
                    user_uses = (await s.execute(
                        select(sa_func.count(PromoCodeUsages.id)).where(
                            PromoCodeUsages.promo_id == promo.id,
                            PromoCodeUsages.user_id == telegram_id
                        )
                    )).scalar() or 0
                    if promo.max_uses_per_user > 0 and user_uses >= promo.max_uses_per_user:
                        await s.rollback()
                        return False, "promo_already_used", None

                    # Check item/category binding
                    if promo.item_id and promo.item_id != goods.id:
                        await s.rollback()
                        return False, "promo_wrong_item", None
                    if promo.category_id and promo.category_id != goods.category_id:
                        await s.rollback()
                        return False, "promo_wrong_category", None

                    # Apply discount
                    if promo.discount_type == 'percent':
                        final_price = price * (1 - Decimal(str(promo.discount_value)) / 100)
                    else:
                        final_price = max(price - Decimal(str(promo.discount_value)), Decimal(0))
                    final_price = final_price.quantize(Decimal("0.01"))

                    # Record usage
                    promo.current_uses += 1
                    s.add(PromoCodeUsages(promo_id=promo.id, user_id=telegram_id))
                    discount_info = {
                        "code": promo.code,
                        "original_price": float(price),
                        "discount": float(price - final_price),
                    }

                # 2.6. Apply account-upgrade discount if no explicit promo used
                if not promo_code and user.discount_percent and user.discount_percent > 0:
                    account_disc = Decimal(str(user.discount_percent)) / 100
                    final_price = (price * (1 - account_disc)).quantize(Decimal("0.01"))
                    discount_info = {
                        "code": f"ACCOUNT ({user.discount_percent}% off)",
                        "original_price": float(price),
                        "discount": float(price - final_price),
                    }

                # 3. Checking the balance
                if user.balance < final_price:
                    await s.rollback()
                    return False, "insufficient_funds", None

                # 4. Receive and lock the goods for purchase (blocking wait for row lock)
                item_value = (await s.execute(
                    select(ItemValues).where(ItemValues.item_id == goods.id).with_for_update()
                )).scalars().first()

                if not item_value:
                    await s.rollback()
                    return False, "out_of_stock", None

                # 5. If the product is not endless, we remove it
                if not item_value.is_infinity:
                    await s.delete(item_value)

                # 6. Write off the balance
                user.balance -= final_price

                # 7. Create a purchase record
                bought_item = BoughtGoods(
                    name=item_name,
                    value=item_value.value,
                    price=final_price,
                    cost_price=goods.cost_price,
                    buyer_id=telegram_id,
                    bought_datetime=datetime.now(timezone.utc),
                    unique_id=uuid4().int >> 65
                )
                s.add(bought_item)
                await s.flush()

                # 8. Commit the transaction
                await s.commit()

                safe_create_task(invalidate_user_cache(telegram_id))
                safe_create_task(invalidate_stats_cache())
                safe_create_task(invalidate_item_cache(item_name))

                result_data = {
                    "item_name": item_name,
                    "value": item_value.value,
                    "price": float(final_price),
                    "new_balance": float(user.balance),
                    "unique_id": bought_item.unique_id,
                    "bought_id": bought_item.id,
                    "bought_datetime": bought_item.bought_datetime.isoformat(),
                }
                if discount_info:
                    result_data["discount"] = discount_info

                return True, "success", result_data

            except IntegrityError as e:
                await s.rollback()
                if "unique_id" in str(e).lower() and attempt < max_retries - 1:
                    continue  # Retry with a new unique_id
                await log_audit(
                    "purchase_failed",
                    level="WARNING",
                    user_id=telegram_id,
                    resource_type="Item",
                    resource_id=item_name,
                    details=str(e),
                )
                return False, "transaction_error", None

            except Exception as e:
                await s.rollback()
                await log_audit(
                    "purchase_failed",
                    level="WARNING",
                    user_id=telegram_id,
                    resource_type="Item",
                    resource_id=item_name,
                    details=str(e),
                )
                return False, "transaction_error", None

    return False, "transaction_error", None


async def process_payment_with_referral(
        user_id: int,
        amount: Decimal,
        provider: str,
        external_id: str,
        referral_percent: int = 0
) -> tuple[bool, str]:
    """
    Processing a payment with a referral bonus in one transaction.
    Returns (success, message)
    """

    async with Database().session() as s:
        try:
            # 1. Check the idempotency of the payment
            existing_payment = (await s.execute(
                select(Payments).where(
                    Payments.provider == provider,
                    Payments.external_id == external_id
                ).with_for_update()
            )).scalars().first()

            if existing_payment:
                if existing_payment.status == PaymentStatus.SUCCEEDED:
                    await s.rollback()
                    return False, "already_processed"
                existing_payment.status = PaymentStatus.SUCCEEDED
            else:
                payment = Payments(
                    provider=provider,
                    external_id=external_id,
                    user_id=user_id,
                    amount=amount,
                    currency=EnvKeys.PAY_CURRENCY,
                    status=PaymentStatus.SUCCEEDED
                )
                s.add(payment)

            # 2. Update the user's balance
            user = (await s.execute(
                select(User).where(User.telegram_id == user_id).with_for_update()
            )).scalars().one()

            user.balance += amount

            # 3. Create a transaction record
            operation = Operations(
                user_id=user_id,
                operation_value=amount,
                operation_time=datetime.now(timezone.utc)
            )
            s.add(operation)

            # 4. Process the referral bonus
            clamped_percent = min(max(referral_percent, 0), 99)
            if clamped_percent > 0 and user.referral_id and user.referral_id != user_id:
                referral_amount = (Decimal(clamped_percent) / Decimal(100)) * amount

                if referral_amount > 0:
                    referrer = (await s.execute(
                        select(User).where(User.telegram_id == user.referral_id).with_for_update()
                    )).scalars().one_or_none()

                    if referrer:
                        referrer.balance += referral_amount
                        await log_audit(
                            "referral_bonus",
                            user_id=user.referral_id,
                            resource_type="User",
                            resource_id=str(user_id),
                            details=f"paid={amount}, bonus={referral_amount}",
                        )

                        earning = ReferralEarnings(
                            referrer_id=user.referral_id,
                            referral_id=user_id,
                            amount=referral_amount,
                            original_amount=amount
                        )
                        s.add(earning)

            referrer_id = user.referral_id if clamped_percent > 0 else None

            await s.commit()

            safe_create_task(invalidate_user_cache(user_id))
            safe_create_task(invalidate_stats_cache())
            if referrer_id:
                safe_create_task(invalidate_user_cache(referrer_id))

            return True, "success"

        except IntegrityError:
            await s.rollback()
            return False, "already_processed"

        except Exception as e:
            await s.rollback()
            await log_audit(
                "payment_failed",
                level="WARNING",
                user_id=user_id,
                resource_type="Payment",
                details=f"provider={provider}, amount={amount}, error={e}",
            )
            return False, "payment_error"


async def checkout_cart_transaction(user_id: int) -> tuple[bool, str, list | None]:
    """
    Atomic cart checkout — purchase all items from user's cart in one transaction.
    Promo codes are read from cart_items.promo_code and validated at checkout time.
    Returns: (success, message, list[purchase_data])
    """
    max_retries = 3
    for attempt in range(max_retries):
        async with Database().session() as s:
            try:
                # 1. Lock user
                user = (await s.execute(
                    select(User).where(User.telegram_id == user_id).with_for_update()
                )).scalars().one_or_none()
                if not user:
                    await s.rollback()
                    return False, "user_not_found", None

                # 2. Get cart items
                cart_items = (await s.execute(
                    select(CartItems).where(CartItems.user_id == user_id)
                )).scalars().all()

                if not cart_items:
                    await s.rollback()
                    return False, "cart_empty", None

                # 3. Resolve items, validate promos, calculate total
                purchases = []
                total_price = Decimal(0)
                items_to_remove = []
                promos_to_record = []  # (promo_obj, promo_id) for usage tracking
                claimed_value_ids: set[int] = set()

                for ci in cart_items:
                    goods = (await s.execute(
                        select(Goods).where(Goods.name == ci.item_name).with_for_update()
                    )).scalars().first()

                    if not goods:
                        items_to_remove.append(ci.id)
                        continue

                    query = select(ItemValues).where(ItemValues.item_id == goods.id)
                    if claimed_value_ids:
                        query = query.where(ItemValues.id.notin_(claimed_value_ids))
                    item_value = (await s.execute(
                        query.with_for_update()
                    )).scalars().first()

                    if not item_value:
                        items_to_remove.append(ci.id)
                        continue

                    claimed_value_ids.add(item_value.id)

                    price = Decimal(str(goods.price))
                    final_price = price

                    # Validate and apply promo code if stored on cart item
                    if ci.promo_code:
                        promo = (await s.execute(
                            select(PromoCodes).where(PromoCodes.code == ci.promo_code.upper()).with_for_update()
                        )).scalars().first()

                        promo_valid = False
                        if promo and promo.is_active and promo.discount_type != 'balance':
                            if not (promo.expires_at and promo.expires_at < datetime.now(timezone.utc)):
                                if not (promo.max_uses > 0 and promo.current_uses >= promo.max_uses):
                                    # Check per-user usage
                                    used = (await s.execute(
                                        select(sa_exists().where(
                                            PromoCodeUsages.promo_id == promo.id,
                                            PromoCodeUsages.user_id == user_id
                                        ))
                                    )).scalar()
                                    if not used:
                                        # Check item/category binding
                                        if promo.item_id and promo.item_id != goods.id:
                                            pass
                                        elif promo.category_id and promo.category_id != goods.category_id:
                                            pass
                                        else:
                                            promo_valid = True

                        if not promo_valid:
                            # Promo was on cart but is no longer valid — abort instead
                            # of silently charging full price.
                            await s.rollback()
                            return False, "promo_expired_during_checkout", None

                        if promo.discount_type == 'percent':
                            final_price = price * (1 - Decimal(str(promo.discount_value)) / 100)
                        else:
                            final_price = max(price - Decimal(str(promo.discount_value)), Decimal(0))
                        final_price = final_price.quantize(Decimal("0.01"))
                        promos_to_record.append(promo)

                    purchases.append({
                        'cart_item': ci,
                        'goods': goods,
                        'item_value': item_value,
                        'price': final_price,
                    })
                    total_price += final_price

                # Remove invalid cart items
                if items_to_remove:
                    await s.execute(
                        sa_delete(CartItems).where(CartItems.id.in_(items_to_remove))
                    )

                if not purchases:
                    await s.commit()
                    return False, "cart_items_unavailable", None

                # 4. Check balance
                if user.balance < total_price:
                    await s.rollback()
                    return False, "insufficient_funds", None

                # 5. Process each purchase
                results = []
                for p in purchases:
                    if not p['item_value'].is_infinity:
                        await s.delete(p['item_value'])

                    bought_item = BoughtGoods(
                        name=p['goods'].name,
                        value=p['item_value'].value,
                        price=p['price'],
                        cost_price=p['goods'].cost_price,
                        buyer_id=user_id,
                        bought_datetime=datetime.now(timezone.utc),
                        unique_id=uuid4().int >> 65
                    )
                    s.add(bought_item)
                    await s.flush()
                    results.append({
                        "item_name": p['goods'].name,
                        "value": p['item_value'].value,
                        "price": float(p['price']),
                        "bought_id": bought_item.id,
                        "unique_id": bought_item.unique_id,
                        "bought_datetime": bought_item.bought_datetime.isoformat(),
                    })

                # 6. Record promo usage
                for promo in promos_to_record:
                    promo.current_uses += 1
                    s.add(PromoCodeUsages(promo_id=promo.id, user_id=user_id))

                # 7. Deduct total
                user.balance -= total_price

                # 8. Clear cart
                await s.execute(
                    sa_delete(CartItems).where(CartItems.user_id == user_id)
                )

                await s.commit()

                safe_create_task(invalidate_user_cache(user_id))
                safe_create_task(invalidate_stats_cache())
                # Invalidate cache for all purchased items
                purchased_names = {r["item_name"] for r in results}
                for name in purchased_names:
                    safe_create_task(invalidate_item_cache(name))

                return True, "success", results

            except IntegrityError as e:
                await s.rollback()
                if "unique_id" in str(e).lower() and attempt < max_retries - 1:
                    continue  # Retry with new unique_ids
                await log_audit(
                    "cart_checkout_failed",
                    level="WARNING",
                    user_id=user_id,
                    details=str(e),
                )
                return False, "transaction_error", None

            except Exception as e:
                await s.rollback()
                await log_audit(
                    "cart_checkout_failed",
                    level="WARNING",
                    user_id=user_id,
                    details=str(e),
                )
                return False, "transaction_error", None

    return False, "transaction_error", None


async def admin_balance_change(telegram_id: int, amount: Decimal) -> tuple[bool, str]:
    """
    Atomic admin balance change (top-up or deduction) with operation record.
    amount > 0 for top-up, amount < 0 for deduction.
    Returns (success, message).
    """
    async with Database().session() as s:
        try:
            user = (await s.execute(
                select(User).where(User.telegram_id == telegram_id).with_for_update()
            )).scalars().one_or_none()

            if not user:
                await s.rollback()
                return False, "user_not_found"

            if amount < 0 and user.balance < abs(amount):
                await s.rollback()
                return False, "insufficient_funds"

            user.balance += amount

            operation = Operations(
                user_id=telegram_id,
                operation_value=amount,
                operation_time=datetime.now(timezone.utc)
            )
            s.add(operation)

            await s.commit()

            safe_create_task(invalidate_user_cache(telegram_id))
            safe_create_task(invalidate_stats_cache())

            return True, "success"

        except Exception as e:
            await s.rollback()
            await log_audit(
                "admin_balance_change_failed",
                level="WARNING",
                user_id=telegram_id,
                resource_type="User",
                details=f"amount={amount}, error={e}",
            )
            return False, "balance_change_error"


async def redeem_balance_promo(code: str, user_id: int) -> tuple[bool, str, Decimal | None]:
    """
    Redeem a balance-type promo code: add discount_value to user balance.
    Returns (success, error_key_or_empty, amount_added).
    """
    async with Database().session() as s:
        try:
            user = (await s.execute(
                select(User).where(User.telegram_id == user_id).with_for_update()
            )).scalars().one_or_none()
            if not user:
                await s.rollback()
                return False, "promo.not_found", None

            promo = (await s.execute(
                select(PromoCodes).where(PromoCodes.code == code.upper()).with_for_update()
            )).scalars().first()

            if not promo:
                await s.rollback()
                return False, "promo.not_found", None
            if not promo.is_active:
                await s.rollback()
                return False, "promo.inactive", None
            if promo.discount_type not in ("balance", "account_upgrade"):
                await s.rollback()
                return False, "promo.not_balance_type", None
            if promo.expires_at and promo.expires_at < datetime.now(timezone.utc):
                await s.rollback()
                return False, "promo.expired", None
            if promo.max_uses > 0 and promo.current_uses >= promo.max_uses:
                await s.rollback()
                return False, "promo.max_uses_reached", None

            used = (await s.execute(
                select(sa_exists().where(
                    PromoCodeUsages.promo_id == promo.id,
                    PromoCodeUsages.user_id == user_id
                ))
            )).scalar()
            if used:
                await s.rollback()
                return False, "promo.already_used", None

            amount = Decimal(str(promo.discount_value))

            if promo.discount_type == "account_upgrade":
                # Store persistent discount on the user's profile
                user.discount_percent = amount
                promo.current_uses += 1
                s.add(PromoCodeUsages(promo_id=promo.id, user_id=user_id))
                await s.commit()
                safe_create_task(invalidate_user_cache(user_id))
                return True, "account_upgrade", amount
            else:
                # balance type: credit balance
                user.balance += amount
                promo.current_uses += 1
                s.add(PromoCodeUsages(promo_id=promo.id, user_id=user_id))
                s.add(Operations(
                    user_id=user_id,
                    operation_value=amount,
                    operation_time=datetime.now(timezone.utc),
                ))
                await s.commit()
                safe_create_task(invalidate_user_cache(user_id))
                safe_create_task(invalidate_stats_cache())
                return True, "balance", amount

        except Exception as e:
            await s.rollback()
            await log_audit(
                "promo_redeem_failed",
                level="WARNING",
                user_id=user_id,
                resource_type="PromoCode",
                resource_id=code,
                details=str(e),
            )
            return False, "errors.something_wrong", None


async def buy_reseller_item_transaction(
    telegram_id: int, item_name: str, qty: int = 1, product_id: int | None = None, promo_code: str | None = None
) -> tuple[bool, str, dict | None]:
    """
    Deducts balance for a reseller product purchase and creates a pending ResellerOrder record.
    Returns (success, message, purchase_data).
    """
    from packages.database.models.main import ResellerProduct, ResellerOrder, PromoCodes, PromoCodeUsages

    max_retries = 3
    for attempt in range(max_retries):
        async with Database().session() as s:
            try:
                # 1. Lock the user to check balance
                user = (await s.execute(
                    select(User).where(User.telegram_id == telegram_id).with_for_update()
                )).scalars().one_or_none()

                if not user:
                    await s.rollback()
                    return False, "user_not_found", None

                # 2. Get the reseller product
                product_lookup = (
                    ResellerProduct.id == product_id
                    if product_id is not None
                    else ResellerProduct.name == item_name
                )
                product = (await s.execute(
                    select(ResellerProduct).where(
                        product_lookup,
                        ResellerProduct.is_enabled == True,  # noqa: E712
                    ).with_for_update()
                )).scalars().one_or_none()

                if not product:
                    await s.rollback()
                    return False, "item_not_found", None

                # 3. Check stock
                if product.stock is not None and product.stock < qty:
                    await s.rollback()
                    return False, "out_of_stock", None

                # 4. Calculate base price
                unit_price = Decimal(str(product.effective_sell_price))
                final_price = unit_price * qty
                discount_info = None

                # 4.1 Apply promo code if provided
                if promo_code:
                    promo = (await s.execute(
                        select(PromoCodes).where(PromoCodes.code == promo_code.upper()).with_for_update()
                    )).scalars().first()

                    if not promo or not promo.is_active or promo.discount_type == "balance":
                        await s.rollback()
                        return False, "promo_invalid", None

                    if promo.expires_at and promo.expires_at < datetime.now(timezone.utc):
                        await s.rollback()
                        return False, "promo_expired", None

                    if promo.max_uses > 0 and promo.current_uses >= promo.max_uses:
                        await s.rollback()
                        return False, "promo_max_uses", None

                    # Check per-user usage
                    user_uses = (await s.execute(
                        select(sa_func.count(PromoCodeUsages.id)).where(
                            PromoCodeUsages.promo_id == promo.id,
                            PromoCodeUsages.user_id == telegram_id
                        )
                    )).scalar() or 0
                    if promo.max_uses_per_user > 0 and user_uses >= promo.max_uses_per_user:
                        await s.rollback()
                        return False, "promo_already_used", None

                    # Check item/category binding if specified
                    if promo.category_id and promo.category_id != product.category_id:
                        await s.rollback()
                        return False, "promo_wrong_category", None

                    # Apply discount
                    if promo.discount_type == 'percent':
                        final_price = final_price * (1 - Decimal(str(promo.discount_value)) / 100)
                    else:
                        final_price = max(final_price - Decimal(str(promo.discount_value)) * qty, Decimal(0))
                    final_price = final_price.quantize(Decimal("0.01"))

                    # Record usage
                    promo.current_uses += 1
                    s.add(PromoCodeUsages(promo_id=promo.id, user_id=telegram_id))
                    discount_info = {
                        "code": promo.code,
                        "discount": float((unit_price * qty) - final_price),
                    }

                # 4.2 Apply account-upgrade discount if no explicit promo used
                elif user.discount_percent and user.discount_percent > 0:
                    account_disc = Decimal(str(user.discount_percent)) / 100
                    final_price = (final_price * (1 - account_disc)).quantize(Decimal("0.01"))
                    discount_info = {
                        "code": f"ACCOUNT ({user.discount_percent}% off)",
                        "discount": float((unit_price * qty) - final_price),
                    }

                # 5. Check balance
                if user.balance < final_price:
                    await s.rollback()
                    return False, "insufficient_funds", None

                # 6. Deduct balance
                user.balance -= final_price

                # Update stock in cache/DB if finite
                if product.stock is not None:
                    product.stock -= qty

                # 7. Create a temporary unique order/receipt
                unique_id = uuid4().int >> 65
                bought_item = BoughtGoods(
                    name=item_name,
                    value="[Processing reseller order...]",
                    price=final_price,
                    cost_price=Decimal(str(product.cost_price)) * qty,
                    buyer_id=telegram_id,
                    bought_datetime=datetime.now(timezone.utc),
                    unique_id=unique_id
                )
                s.add(bought_item)
                await s.flush()

                # Create ResellerOrder record
                order_rec = ResellerOrder(
                    source_id=product.source_id,
                    reseller_product_id=product.id,
                    bought_goods_id=bought_item.id,
                    user_id=telegram_id,
                    quantity=qty,
                )
                s.add(order_rec)
                await s.flush()

                order_id = order_rec.id
                bought_id = bought_item.id

                await s.commit()

                safe_create_task(invalidate_user_cache(telegram_id))
                safe_create_task(invalidate_stats_cache())

                return True, "success", {
                    "item_name": item_name,
                    "price": float(final_price),
                    "new_balance": float(user.balance),
                    "unique_id": unique_id,
                    "bought_id": bought_id,
                    "reseller_order_id": order_id,
                    "qty": qty,
                    "product_type": product.product_type,
                }

            except IntegrityError as e:
                await s.rollback()
                if "unique_id" in str(e).lower() and attempt < max_retries - 1:
                    continue  # Retry
                return False, "transaction_error", None

            except Exception as e:
                await s.rollback()
                await log_audit(
                    "reseller_purchase_failed",
                    level="WARNING",
                    user_id=telegram_id,
                    resource_type="Item",
                    resource_id=item_name,
                    details=str(e),
                )
                return False, "transaction_error", None

    return False, "transaction_error", None


async def refund_reseller_purchase(user_id: int, amount: Decimal, bought_id: int, reseller_order_id: int, reason: str = None) -> bool:
    """Refunds the user balance and marks purchase/order as failed/refunded."""
    from packages.database.models.main import ResellerOrder
    async with Database().session() as s:
        try:
            user = (await s.execute(
                select(User).where(User.telegram_id == user_id).with_for_update()
            )).scalars().one_or_none()
            if user:
                user.balance += amount

            bought = (await s.execute(
                select(BoughtGoods).where(BoughtGoods.id == bought_id)
            )).scalars().first()
            if bought:
                await s.delete(bought)

            order = (await s.execute(
                select(ResellerOrder).where(ResellerOrder.id == reseller_order_id)
            )).scalars().first()
            if order:
                order.status = "failed"
                order.error_message = reason or "API fulfillment failed, auto-refunded."

            await s.commit()
            safe_create_task(invalidate_user_cache(user_id))
            return True
        except Exception as e:
            await s.rollback()
            logger.error(f"Error refunding reseller purchase: {e}")
            return False


async def confirm_reseller_purchase_success(bought_id: int, value: str, reseller_order_id: int, external_order_id: str = None):
    """Updates BoughtGoods and ResellerOrder upon successful external API delivery."""
    from packages.database.models.main import ResellerOrder
    async with Database().session() as s:
        try:
            bought = (await s.execute(
                select(BoughtGoods).where(BoughtGoods.id == bought_id)
            )).scalars().first()
            if bought:
                bought.value = value

            order = (await s.execute(
                select(ResellerOrder).where(ResellerOrder.id == reseller_order_id)
            )).scalars().first()
            if order:
                order.status = "delivered"
                if external_order_id:
                    order.external_order_id = external_order_id
                import json
                order.delivered_codes = json.dumps([value])
                order.fulfilled_at = datetime.now(timezone.utc)

            await s.commit()
        except Exception as e:
            await s.rollback()
            logger.error(f"Error confirming reseller purchase: {e}")

