from datetime import datetime, timezone, timedelta
from typing import Optional, List
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_, and_, update

from apps.api.dependencies import get_db, get_current_admin_user
from packages.database.models import (
    User, Role, Goods, Categories, ItemValues, BoughtGoods,
    Payments, Operations, AuditLog, ResellerProduct, ResellerOrder, BotSettings,
    PromoCodes, ResellerSource
)

router = APIRouter(prefix="/api/admin", tags=["Admin Panel"])


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────────────────────

class AdminStats(BaseModel):
    total_users: int
    new_users_today: int
    total_sales_usd: float
    sales_today_usd: float
    total_profit_usd: float
    total_orders: int
    orders_today: int
    total_products: int
    in_stock_products: int
    pending_payments: int
    succeeded_payments_volume: float

class AdminUserItem(BaseModel):
    telegram_id: int
    email: Optional[str]
    balance: float
    role_name: str
    role_id: int
    registration_date: str
    is_blocked: bool
    discount_percent: float
    purchases_count: int
    total_spent: float

class AdminProductItem(BaseModel):
    id: int
    name: str
    category_id: int
    category_name: str
    price: float
    cost_price: float
    stock: int
    is_featured: bool
    warranty: Optional[str]
    note: Optional[str]
    source_type: str  # "native" | "reseller"

class AdminCategoryItem(BaseModel):
    id: int
    name: str
    is_active: bool
    products_count: int

class AdminOrderItem(BaseModel):
    id: int
    unique_id: int
    buyer_id: Optional[int]
    buyer_email: Optional[str]
    item_name: str
    price: float
    cost_price: float
    profit: float
    bought_datetime: str
    value: str

class AdminPaymentItem(BaseModel):
    id: int
    provider: str
    external_id: str
    user_id: Optional[int]
    amount: float
    currency: str
    status: str
    created_at: str

class AdminAuditLogItem(BaseModel):
    id: int
    timestamp: str
    level: str
    user_id: Optional[int]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[str]

class BalanceAdjustRequest(BaseModel):
    amount: float
    reason: Optional[str] = "Admin web adjustment"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Overview & Statistics
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    # 1. Total users & new users today
    total_users = (await db.scalar(select(func.count(User.telegram_id)))) or 0
    new_users_today = (await db.scalar(
        select(func.count(User.telegram_id)).where(User.registration_date >= today_start)
    )) or 0

    # 2. Sales & Orders
    total_orders = (await db.scalar(select(func.count(BoughtGoods.id)))) or 0
    orders_today = (await db.scalar(
        select(func.count(BoughtGoods.id)).where(BoughtGoods.bought_datetime >= today_start)
    )) or 0

    total_sales_res = (await db.scalar(select(func.sum(BoughtGoods.price)))) or 0
    sales_today_res = (await db.scalar(
        select(func.sum(BoughtGoods.price)).where(BoughtGoods.bought_datetime >= today_start)
    )) or 0
    total_cost_res = (await db.scalar(select(func.sum(BoughtGoods.cost_price)))) or 0

    total_sales_usd = float(total_sales_res)
    sales_today_usd = float(sales_today_res)
    total_profit_usd = max(0.0, total_sales_usd - float(total_cost_res))

    # 3. Products & Stock
    total_goods = (await db.scalar(select(func.count(Goods.id)))) or 0
    
    # In stock items (goods with values or infinite)
    in_stock_goods = (await db.scalar(
        select(func.count(func.distinct(Goods.id)))
        .join(ItemValues, ItemValues.item_id == Goods.id)
    )) or 0

    # 4. Payments
    pending_payments = (await db.scalar(
        select(func.count(Payments.id)).where(Payments.status == "pending")
    )) or 0
    succeeded_payments_vol = (await db.scalar(
        select(func.sum(Payments.amount)).where(Payments.status == "succeeded")
    )) or 0

    return AdminStats(
        total_users=total_users,
        new_users_today=new_users_today,
        total_sales_usd=round(total_sales_usd, 2),
        sales_today_usd=round(sales_today_usd, 2),
        total_profit_usd=round(total_profit_usd, 2),
        total_orders=total_orders,
        orders_today=orders_today,
        total_products=total_goods,
        in_stock_products=in_stock_goods,
        pending_payments=pending_payments,
        succeeded_payments_volume=round(float(succeeded_payments_vol), 2),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Users Management
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=List[AdminUserItem])
async def get_admin_users(
    search: Optional[str] = None,
    role_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(User, Role.name.label("role_name")).outerjoin(Role, User.role_id == Role.id)

    if search:
        s = search.strip()
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            query = query.where(User.telegram_id == int(s))
        else:
            query = query.where(User.email.ilike(f"%{s}%"))

    if role_id is not None:
        query = query.where(User.role_id == role_id)

    query = query.order_by(desc(User.registration_date)).offset(offset).limit(limit)
    rows = (await db.execute(query)).all()

    items = []
    for user, role_name in rows:
        # Get purchase stats for this user
        purchases_count = (await db.scalar(
            select(func.count(BoughtGoods.id)).where(BoughtGoods.buyer_id == user.telegram_id)
        )) or 0
        total_spent = (await db.scalar(
            select(func.sum(BoughtGoods.price)).where(BoughtGoods.buyer_id == user.telegram_id)
        )) or 0

        items.append(AdminUserItem(
            telegram_id=user.telegram_id,
            email=user.email,
            balance=float(user.balance or 0),
            role_name=role_name or "USER",
            role_id=user.role_id or 1,
            registration_date=user.registration_date.isoformat() if user.registration_date else "",
            is_blocked=bool(user.is_blocked),
            discount_percent=float(user.discount_percent or 0),
            purchases_count=purchases_count,
            total_spent=round(float(total_spent), 2),
        ))

    return items


@router.post("/users/{user_id}/balance")
async def adjust_user_balance(
    user_id: int,
    data: BalanceAdjustRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    target = (await db.execute(select(User).where(User.telegram_id == user_id))).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    adj = Decimal(str(data.amount))
    target.balance += adj

    # Log operation
    op = Operations(
        user_id=user_id,
        operation_value=adj,
        operation_time=datetime.now(timezone.utc)
    )
    db.add(op)

    # Log audit
    audit = AuditLog(
        timestamp=datetime.now(timezone.utc),
        level="INFO",
        user_id=admin.telegram_id,
        action="admin_balance_adjust",
        resource_type="User",
        resource_id=str(user_id),
        details=f"Adjusted by {adj:+f} (new balance: {target.balance}). Reason: {data.reason}"
    )
    db.add(audit)

    return {"status": "success", "new_balance": float(target.balance)}


@router.post("/users/{user_id}/toggle-block")
async def toggle_user_block(
    user_id: int,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    target = (await db.execute(select(User).where(User.telegram_id == user_id))).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target.is_blocked = not target.is_blocked

    audit = AuditLog(
        timestamp=datetime.now(timezone.utc),
        level="INFO",
        user_id=admin.telegram_id,
        action="admin_user_block_toggle",
        resource_type="User",
        resource_id=str(user_id),
        details=f"User blocked status changed to {target.is_blocked}"
    )
    db.add(audit)

    return {"status": "success", "is_blocked": target.is_blocked}


# ─────────────────────────────────────────────────────────────────────────────
# 3. Products & Catalog
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/products", response_model=List[AdminProductItem])
async def get_admin_products(
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=300),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(Goods, Categories.name.label("category_name"))
        .join(Categories, Goods.category_id == Categories.id)
    )

    if category_id:
        query = query.where(Goods.category_id == category_id)

    if search:
        query = query.where(Goods.name.ilike(f"%{search.strip()}%"))

    query = query.order_by(Goods.id).offset(offset).limit(limit)
    rows = (await db.execute(query)).all()

    items = []
    for good, cat_name in rows:
        # Check stock count
        stock_count = (await db.scalar(
            select(func.count(ItemValues.id)).where(ItemValues.item_id == good.id)
        )) or 0

        items.append(AdminProductItem(
            id=good.id,
            name=good.name,
            category_id=good.category_id,
            category_name=cat_name,
            price=float(good.price),
            cost_price=float(good.cost_price or 0),
            stock=stock_count,
            is_featured=bool(good.is_featured),
            warranty=good.warranty,
            note=good.note,
            source_type="native"
        ))

    return items


@router.post("/products/{product_id}/toggle-featured")
async def toggle_product_featured(
    product_id: int,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    product = (await db.execute(select(Goods).where(Goods.id == product_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.is_featured = not product.is_featured
    return {"status": "success", "is_featured": product.is_featured}


@router.post("/products/{product_id}/auto-describe")
async def auto_describe_product(
    product_id: str,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Auto-formats / enhances product descriptions based on bot API metadata,
    generating structured bullet points, warranty details, and instant delivery info.
    """
    prod_name = "Digital Product"
    existing_desc = ""
    is_reseller = product_id.startswith("reseller_")

    if is_reseller:
        res_id = int(product_id.replace("reseller_", ""))
        rp = (await db.execute(select(ResellerProduct).where(ResellerProduct.id == res_id))).scalar_one_or_none()
        if not rp:
            raise HTTPException(status_code=404, detail="Reseller product not found")
        prod_name = rp.effective_name
        existing_desc = rp.description or ""
    else:
        raw_id = int(product_id.replace("local_", "")) if str(product_id).startswith("local_") else int(product_id)
        good = (await db.execute(select(Goods).where(Goods.id == raw_id))).scalar_one_or_none()
        if not good:
            raise HTTPException(status_code=404, detail="Product not found")
        prod_name = good.name
        existing_desc = good.description or ""

    # Generate enhanced structured markdown description
    auto_description = (
        f"🌟 **{prod_name}**\n\n"
        f"✨ **Key Features & Benefits:**\n"
        f"• 100% Genuine and authentic activation / access\n"
        f"• Instant automated delivery directly to your dashboard & Telegram\n"
        f"• High-speed stable credentials with 24/7 global uptime\n\n"
        f"🛡️ **Warranty & Guarantee:**\n"
        f"• Full replacement warranty against invalid keys / accounts\n"
        f"• Priority customer support on Telegram & Web Live Chat\n\n"
        f"🚀 **How to Redeem / Use:**\n"
        f"1. Complete purchase and copy your credentials from the order confirmation\n"
        f"2. Follow redemption link / instructions provided with your item key\n"
        f"3. Need help? Contact live support anytime in 1-click!"
    )
    if existing_desc and len(existing_desc) > 10:
        auto_description += f"\n\n📝 **Item Specifications:**\n{existing_desc}"

    if is_reseller:
        rp.description = auto_description
    else:
        good.description = auto_description
    await db.commit()

    return {"status": "success", "description": auto_description}



# ─────────────────────────────────────────────────────────────────────────────
# 4. Categories
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/categories", response_model=List[AdminCategoryItem])
async def get_admin_categories(
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    cats = (await db.execute(select(Categories).order_by(Categories.name))).scalars().all()
    results = []
    for cat in cats:
        count = (await db.scalar(
            select(func.count(Goods.id)).where(Goods.category_id == cat.id)
        )) or 0
        results.append(AdminCategoryItem(
            id=cat.id,
            name=cat.name,
            is_active=bool(cat.is_active),
            products_count=count
        ))
    return results


@router.post("/categories/{category_id}/toggle-active")
async def toggle_category_active(
    category_id: int,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    cat = (await db.execute(select(Categories).where(Categories.id == category_id))).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    cat.is_active = not cat.is_active
    return {"status": "success", "is_active": cat.is_active}


# ─────────────────────────────────────────────────────────────────────────────
# 5. Orders / Bought Goods
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/orders", response_model=List[AdminOrderItem])
async def get_admin_orders(
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(BoughtGoods, User.email.label("buyer_email"))
        .outerjoin(User, BoughtGoods.buyer_id == User.telegram_id)
    )

    if search:
        s = search.strip()
        if s.isdigit():
            query = query.where(or_(BoughtGoods.buyer_id == int(s), BoughtGoods.unique_id == int(s)))
        else:
            query = query.where(BoughtGoods.item_name.ilike(f"%{s}%"))

    query = query.order_by(desc(BoughtGoods.bought_datetime)).offset(offset).limit(limit)
    rows = (await db.execute(query)).all()

    orders = []
    for item, buyer_email in rows:
        price = float(item.price)
        cost_price = float(item.cost_price or 0)
        profit = max(0.0, price - cost_price)
        orders.append(AdminOrderItem(
            id=item.id,
            unique_id=item.unique_id,
            buyer_id=item.buyer_id,
            buyer_email=buyer_email,
            item_name=item.item_name,
            price=price,
            cost_price=cost_price,
            profit=round(profit, 2),
            bought_datetime=item.bought_datetime.isoformat() if item.bought_datetime else "",
            value=item.value or "",
        ))

    return orders


# ─────────────────────────────────────────────────────────────────────────────
# 6. Payments & Transactions
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/payments", response_model=List[AdminPaymentItem])
async def get_admin_payments(
    provider: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Payments)

    if provider:
        query = query.where(Payments.provider == provider)

    if status_filter:
        query = query.where(Payments.status == status_filter)

    if search:
        s = search.strip()
        if s.isdigit():
            query = query.where(Payments.user_id == int(s))
        else:
            query = query.where(Payments.external_id.ilike(f"%{s}%"))

    query = query.order_by(desc(Payments.created_at)).offset(offset).limit(limit)
    rows = (await db.execute(query)).scalars().all()

    return [
        AdminPaymentItem(
            id=p.id,
            provider=p.provider,
            external_id=p.external_id,
            user_id=p.user_id,
            amount=float(p.amount),
            currency=p.currency,
            status=p.status,
            created_at=p.created_at.isoformat() if p.created_at else "",
        )
        for p in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 7. Security Audit Logs
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/audit-logs", response_model=List[AdminAuditLogItem])
async def get_admin_audit_logs(
    level: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=300),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(AuditLog)

    if level:
        query = query.where(AuditLog.level == level)

    if search:
        s = search.strip()
        query = query.where(or_(
            AuditLog.action.ilike(f"%{s}%"),
            AuditLog.details.ilike(f"%{s}%"),
            AuditLog.resource_id.ilike(f"%{s}%")
        ))

    query = query.order_by(desc(AuditLog.timestamp)).offset(offset).limit(limit)
    rows = (await db.execute(query)).scalars().all()

    return [
        AdminAuditLogItem(
            id=log.id,
            timestamp=log.timestamp.isoformat() if log.timestamp else "",
            level=log.level,
            user_id=log.user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
        )
        for log in rows
    ]


class NepalQRSettingsRequest(BaseModel):
    qr_url: Optional[str] = None
    title: Optional[str] = "eSewa / Khalti / Fonepay Direct QR"
    account_name: Optional[str] = "Kali Store Nepal"
    account_id: Optional[str] = "98XXXXXXXX"
    instructions: Optional[str] = "Scan QR with eSewa/Khalti/Fonepay, transfer exact NPR amount, then submit your Tx Reference ID."
    coming_soon: Optional[bool] = True
    coming_soon_text: Optional[str] = "🚀 Nepal Store Direct Local Payment Gateway & Catalog Expansion is Coming Soon! Stay tuned as we roll out instant eSewa & Khalti automated API verification."


@router.get("/nepal-qr")
async def get_admin_nepal_qr_settings(db: AsyncSession = Depends(get_db)):
    """Get Nepal QR Code payment configuration & Coming Soon banner status for Admin dashboard."""
    keys = ["nepal_qr_url", "nepal_qr_title", "nepal_qr_account_name", "nepal_qr_account_id", "nepal_qr_instructions", "nepal_coming_soon", "nepal_coming_soon_text"]
    res = await db.execute(select(BotSettings).where(BotSettings.key.in_(keys)))
    settings = {s.key: s.value for s in res.scalars().all()}
    return {
        "qr_url": settings.get("nepal_qr_url") or "",
        "title": settings.get("nepal_qr_title") or "eSewa / Khalti / Fonepay Direct QR",
        "account_name": settings.get("nepal_qr_account_name") or "Kali Store Nepal",
        "account_id": settings.get("nepal_qr_account_id") or "9800000000",
        "instructions": settings.get("nepal_qr_instructions") or "Scan QR with eSewa/Khalti/Fonepay, transfer exact NPR amount, then submit your Tx Reference ID below.",
        "coming_soon": settings.get("nepal_coming_soon", "true").lower() == "true",
        "coming_soon_text": settings.get("nepal_coming_soon_text") or "🇳🇵 Nepal Store Direct Local Payment Gateway & Catalog Expansion is Coming Soon! Stay tuned as we roll out instant eSewa & Khalti automated API verification.",
    }


@router.post("/nepal-qr")
async def update_admin_nepal_qr_settings(
    payload: NepalQRSettingsRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    """Admin endpoint to upload/update Nepal QR image URL, account details, and Coming Soon banner."""
    mapping = {
        "nepal_qr_url": payload.qr_url or "",
        "nepal_qr_title": payload.title or "eSewa / Khalti / Fonepay Direct QR",
        "nepal_qr_account_name": payload.account_name or "",
        "nepal_qr_account_id": payload.account_id or "",
        "nepal_qr_instructions": payload.instructions or "",
        "nepal_coming_soon": "true" if payload.coming_soon is not False else "false",
        "nepal_coming_soon_text": payload.coming_soon_text or "🇳🇵 Nepal Store Direct Local Payment Gateway & Catalog Expansion is Coming Soon!",
    }
    for k, v in mapping.items():
        existing = (await db.execute(select(BotSettings).where(BotSettings.key == k))).scalar_one_or_none()
        if existing:
            existing.value = str(v)
        else:
            db.add(BotSettings(key=k, value=str(v)))
    await db.commit()
    return {"status": "success", "message": "Nepal Store & Coming Soon settings saved successfully!"}


# ─────────────────────────────────────────────────────────────────────────────
# 8. Complete Product & Category CRUD
# ─────────────────────────────────────────────────────────────────────────────

class CreateProductRequest(BaseModel):
    name: str
    category_id: int
    price: float
    cost_price: Optional[float] = 0.0
    warranty: Optional[str] = "24 Hours"
    note: Optional[str] = ""
    is_featured: Optional[bool] = False
    initial_keys: Optional[str] = None


class UpdateProductRequest(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    cost_price: Optional[float] = None
    category_id: Optional[int] = None
    warranty: Optional[str] = None
    note: Optional[str] = None
    is_featured: Optional[bool] = None


class AddKeysRequest(BaseModel):
    keys: str


@router.post("/products")
async def create_product(
    payload: CreateProductRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new local digital product."""
    prod = Goods(
        name=payload.name.strip(),
        category_id=payload.category_id,
        price=Decimal(str(payload.price)),
        cost_price=Decimal(str(payload.cost_price or 0)),
        warranty=payload.warranty,
        note=payload.note,
        is_featured=payload.is_featured or False,
    )
    db.add(prod)
    await db.flush()

    added_keys_count = 0
    if payload.initial_keys:
        lines = [line.strip() for line in payload.initial_keys.splitlines() if line.strip()]
        for val in lines:
            item_val = ItemValues(item_id=prod.id, value=val)
            db.add(item_val)
            added_keys_count += 1

    await db.commit()
    return {"status": "success", "product_id": prod.id, "added_keys": added_keys_count}


@router.put("/products/{product_id}")
async def update_product(
    product_id: int,
    payload: UpdateProductRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Update an existing product."""
    prod = (await db.execute(select(Goods).where(Goods.id == product_id))).scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    if payload.name is not None:
        prod.name = payload.name.strip()
    if payload.price is not None:
        prod.price = Decimal(str(payload.price))
    if payload.cost_price is not None:
        prod.cost_price = Decimal(str(payload.cost_price))
    if payload.category_id is not None:
        prod.category_id = payload.category_id
    if payload.warranty is not None:
        prod.warranty = payload.warranty
    if payload.note is not None:
        prod.note = payload.note
    if payload.is_featured is not None:
        prod.is_featured = payload.is_featured

    await db.commit()
    return {"status": "success", "message": "Product updated successfully"}


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: int,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a product and its unsold inventory."""
    prod = (await db.execute(select(Goods).where(Goods.id == product_id))).scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    await db.execute(ItemValues.__table__.delete().where(ItemValues.item_id == product_id))
    await db.delete(prod)
    await db.commit()
    return {"status": "success", "message": "Product deleted successfully"}


@router.post("/products/{product_id}/keys")
async def add_product_keys(
    product_id: int,
    payload: AddKeysRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Bulk upload license keys / digital accounts into product inventory."""
    prod = (await db.execute(select(Goods).where(Goods.id == product_id))).scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    lines = [line.strip() for line in payload.keys.splitlines() if line.strip()]
    if not lines:
        raise HTTPException(status_code=400, detail="No valid keys provided")

    for val in lines:
        db.add(ItemValues(item_id=prod.id, value=val))

    await db.commit()
    return {"status": "success", "added_count": len(lines)}


class CreateCategoryRequest(BaseModel):
    name: str


@router.post("/categories")
async def create_category(
    payload: CreateCategoryRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new product category."""
    name_str = payload.name.strip()
    if not name_str:
        raise HTTPException(status_code=400, detail="Category name cannot be empty")

    cat = Categories(name=name_str, is_active=True)
    db.add(cat)
    await db.commit()
    return {"status": "success", "category_id": cat.id}


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a category."""
    cat = (await db.execute(select(Categories).where(Categories.id == category_id))).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    await db.delete(cat)
    await db.commit()
    return {"status": "success", "message": "Category deleted successfully"}


# ─────────────────────────────────────────────────────────────────────────────
# 9. Promocode Management
# ─────────────────────────────────────────────────────────────────────────────

class CreatePromoCodeRequest(BaseModel):
    code: str
    discount_type: str
    discount_value: float
    max_uses: Optional[int] = 0


@router.get("/promocodes")
async def get_admin_promocodes(
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List all promocodes."""
    res = await db.execute(select(PromoCodes).order_by(desc(PromoCodes.created_at)))
    promos = res.scalars().all()
    return [
        {
            "id": p.id,
            "code": p.code,
            "discount_type": p.discount_type,
            "discount_value": float(p.discount_value),
            "max_uses": p.max_uses,
            "current_uses": p.current_uses,
            "is_active": p.is_active,
            "created_at": p.created_at.isoformat() if p.created_at else "",
        }
        for p in promos
    ]


@router.post("/promocodes")
async def create_promocode(
    payload: CreatePromoCodeRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new promocode."""
    code_clean = payload.code.strip().upper()
    if not code_clean:
        raise HTTPException(status_code=400, detail="Promocode cannot be empty")

    existing = (await db.execute(select(PromoCodes).where(PromoCodes.code == code_clean))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Promocode already exists")

    promo = PromoCodes(
        code=code_clean,
        discount_type=payload.discount_type,
        discount_value=Decimal(str(payload.discount_value)),
        max_uses=payload.max_uses or 0,
        is_active=True
    )
    db.add(promo)
    await db.commit()
    return {"status": "success", "promocode_id": promo.id}


@router.delete("/promocodes/{promo_id}")
async def delete_promocode(
    promo_id: int,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a promocode."""
    promo = (await db.execute(select(PromoCodes).where(PromoCodes.id == promo_id))).scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=404, detail="Promocode not found")

    await db.delete(promo)
    await db.commit()
    return {"status": "success", "message": "Promocode deleted"}


# ─────────────────────────────────────────────────────────────────────────────
# 10. Payment Approval / Rejection
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/payments/{payment_id}/approve")
async def approve_payment(
    payment_id: int,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Approve a pending payment and credit target user balance."""
    pmt = (await db.execute(select(Payments).where(Payments.id == payment_id))).scalar_one_or_none()
    if not pmt:
        raise HTTPException(status_code=404, detail="Payment record not found")

    if pmt.status == "succeeded":
        return {"status": "already_approved", "message": "Payment is already approved"}

    pmt.status = "succeeded"
    credited_amount = float(pmt.amount)

    # Extract possible customer email from user or note
    target_email = ""
    if pmt.user_id:
        usr = (await db.execute(select(User).where(User.telegram_id == pmt.user_id))).scalar_one_or_none()
        if usr:
            usr.balance += Decimal(str(credited_amount))
            op = Operations(
                user_id=usr.telegram_id,
                operation_value=Decimal(str(credited_amount)),
                operation_time=datetime.now(timezone.utc)
            )
            db.add(op)
            target_email = usr.email or ""

    audit = AuditLog(
        timestamp=datetime.now(timezone.utc),
        level="INFO",
        user_id=admin.telegram_id,
        action="admin_approve_payment",
        resource_type="Payment",
        resource_id=str(payment_id),
        details=f"Approved payment {pmt.external_id} of ${credited_amount} USD for user {pmt.user_id}"
    )
    db.add(audit)
    await db.commit()

    # Automatic Email Receipt to customer
    if target_email:
        from packages.services.email_service import send_order_delivery_email
        import asyncio
        asyncio.create_task(
            send_order_delivery_email(
                customer_email=target_email,
                product_name="Nepal QR Wallet Deposit / Order Verification",
                quantity=1,
                amount_str=f"NPR {int(credited_amount * 300):,} (${credited_amount:.2f} USD)",
                delivered_content=f"Payment verified & credited successfully!\nYour balance has been updated with NPR {int(credited_amount * 300):,}.\nYou can now access your products instantly in your Account Dashboard.",
                order_id=f"PMT-{payment_id}",
                tx_id=pmt.external_id.split("::")[0] if pmt.external_id else ""
            )
        )

    return {"status": "success", "message": f"Payment #{payment_id} approved. Credited NPR {int(credited_amount * 300):,} (${credited_amount:.2f} USD) to user balance."}


@router.post("/payments/{payment_id}/reject")
async def reject_payment(
    payment_id: int,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Reject a pending payment record."""
    pmt = (await db.execute(select(Payments).where(Payments.id == payment_id))).scalar_one_or_none()
    if not pmt:
        raise HTTPException(status_code=404, detail="Payment record not found")

    pmt.status = "failed"
    await db.commit()
    return {"status": "success", "message": f"Payment #{payment_id} rejected."}
