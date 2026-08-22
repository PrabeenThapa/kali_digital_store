from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.api.dependencies import get_db, get_current_user
from packages.database.models import User, BoughtGoods, ReferralEarnings, Role, Permission, Payments
from packages.config.config import EnvKeys
from packages.database.methods.read import get_referral_earnings_stats

router = APIRouter(prefix="/api/user", tags=["User"])

@router.get("/me")
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the authenticated user's profile and balances.
    """
    earnings = await get_referral_earnings_stats(current_user.telegram_id)
    referral_balance = float(earnings.get("total_amount", 0)) if earnings else 0.0

    is_admin = False
    if EnvKeys.OWNER_ID and current_user.telegram_id == EnvKeys.OWNER_ID:
        is_admin = True
    else:
        role = (await db.execute(select(Role).where(Role.id == current_user.role_id))).scalar_one_or_none()
        if role and (role.name in ("ADMIN", "OWNER") or Permission.has_any_admin_perm(role.permissions or 0)):
            is_admin = True

    from sqlalchemy import func
    total_users_count = (await db.execute(select(func.count(User.telegram_id)))).scalar() or 0
    total_delivered_count = (await db.execute(select(func.count(BoughtGoods.id)))).scalar() or 0
    customers_served = max(total_users_count + 1420, 1450)
    total_deliveries = max(total_delivered_count + 3890, 3920)

    return {
        "id": current_user.telegram_id,
        "email": current_user.email,
        "username": current_user.email.split("@")[0] if current_user.email else f"user_{current_user.telegram_id}",
        "first_name": current_user.email.split("@")[0] if current_user.email else f"User {current_user.telegram_id}",
        "balance": float(current_user.balance),
        "crypto_balance": float(current_user.balance),
        "referral_balance": referral_balance,
        "discount_percent": float(current_user.discount_percent or 0),
        "role_id": current_user.role_id,
        "is_blocked": current_user.is_blocked,
        "is_admin": is_admin,
        "customers_served": customers_served,
        "total_deliveries": total_deliveries,
        "satisfaction_rate": "99.8%",
    }

@router.get("/purchases")
async def get_my_purchases(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the user's purchase and order history, including delivered items and delivering/pending items.
    """
    # 1. Delivered digital products
    result_goods = await db.execute(
        select(BoughtGoods)
        .where(BoughtGoods.buyer_id == current_user.telegram_id)
        .order_by(BoughtGoods.bought_datetime.desc())
    )
    goods = result_goods.scalars().all()

    # 2. Nepal QR / web payment orders
    result_pmts = await db.execute(
        select(Payments)
        .where(Payments.user_id == current_user.telegram_id)
        .order_by(Payments.created_at.desc())
    )
    pmts = result_pmts.scalars().all()
    
    purchases = []

    # Map delivered goods
    for g in goods:
        purchases.append({
            "id": f"goods_{g.id}",
            "raw_id": g.id,
            "date": g.bought_datetime.isoformat() if g.bought_datetime else None,
            "amount": float(g.price),
            "description": g.item_name,
            "status": "delivered",
            "status_label": "Delivered",
            "delivered_content": g.value,
            "unique_id": str(g.unique_id),
            "type": "digital_product",
        })
        
    # Map pending / delivering / completed payment orders
    for p in pmts:
        if p.status == "pending":
            status_code = "delivering"
            status_label = "Delivering (Verifying)"
        elif p.status == "succeeded":
            status_code = "completed"
            status_label = "Verified / Completed"
        elif p.status == "failed":
            status_code = "cancelled"
            status_label = "Cancelled"
        else:
            status_code = p.status
            status_label = p.status.capitalize()

        ext_parts = (p.external_id or "").split("::")
        tx_code = ext_parts[0] if ext_parts else p.external_id
        
        desc = f"Order #{p.id} (Ref: {tx_code})"
        if p.provider == "nepal_qr":
            desc = f"🇳🇵 Nepal Order (Tx: {tx_code})"

        purchases.append({
            "id": f"pmt_{p.id}",
            "raw_id": p.id,
            "date": p.created_at.isoformat() if p.created_at else None,
            "amount": float(p.amount),
            "description": desc,
            "status": status_code,
            "status_label": status_label,
            "delivered_content": None,
            "unique_id": p.external_id,
            "type": "payment_order",
        })

    # Sort all entries by date descending
    purchases.sort(key=lambda x: x["date"] or "", reverse=True)
    return purchases
