from datetime import datetime, timezone, timedelta
from typing import Optional, List
from decimal import Decimal
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_, and_, update

from apps.api.dependencies import get_db, get_current_admin_user
from packages.database.models import (
    User, Role, Goods, Categories, ItemValues, BoughtGoods,
    Payments, Operations, AuditLog, ResellerProduct, ResellerOrder, BotSettings,
    PromoCodes, ResellerSource, ResellerTopUp
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

class UserPurchaseItem(BaseModel):
    id: int
    unique_id: int
    item_name: str
    price: float
    cost_price: float
    profit: float
    bought_datetime: str
    value: str
    source_type: str = "local"
    status: str = "delivered"

class AdminProductItem(BaseModel):
    id: str  # "local_1" or "reseller_5"
    raw_id: int
    name: str
    description: Optional[str] = ""
    category_id: int
    category_name: str
    price: float
    price_npr: Optional[float] = None
    cost_price: float
    stock: int
    is_featured: bool
    is_hot: bool
    is_bestseller: bool
    badge_text: Optional[str] = None
    is_active: bool
    auto_delivery: bool = True
    delivery_template: Optional[str] = None
    delivery_type: Optional[str] = "instant"
    account_type: Optional[str] = "preactivated"
    warranty: Optional[str] = None
    note: Optional[str] = None
    source_type: str  # "local" | "reseller"
    source_name: Optional[str] = None

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
    user_email: Optional[str] = None
    amount: float
    currency: str
    status: str
    created_at: str
    details: Optional[str] = None

class PendingNepalPaymentItem(BaseModel):
    id: int
    payment_id: int
    tx_id: str
    user_id: Optional[int]
    user_email: Optional[str]
    amount_usd: float
    amount_npr: float
    note: Optional[str]
    proof_image: Optional[str] = None
    created_at: str
    status: str

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

class CreateProductRequest(BaseModel):
    name: str
    category_id: int
    price: float
    price_npr: Optional[float] = None
    cost_price: Optional[float] = 0.0
    warranty: Optional[str] = "24 Hours"
    note: Optional[str] = ""
    description: Optional[str] = ""
    is_featured: Optional[bool] = False
    is_hot: Optional[bool] = False
    is_bestseller: Optional[bool] = False
    badge_text: Optional[str] = None
    auto_delivery: Optional[bool] = True
    delivery_template: Optional[str] = None
    delivery_type: Optional[str] = "instant"
    account_type: Optional[str] = "preactivated"
    initial_keys: Optional[str] = None

class UpdateProductRequest(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    price_npr: Optional[float] = None
    cost_price: Optional[float] = None
    category_id: Optional[int] = None
    warranty: Optional[str] = None
    note: Optional[str] = None
    description: Optional[str] = None
    is_featured: Optional[bool] = None
    is_hot: Optional[bool] = None
    is_bestseller: Optional[bool] = None
    badge_text: Optional[str] = None
    is_active: Optional[bool] = None
    auto_delivery: Optional[bool] = None
    delivery_template: Optional[str] = None
    delivery_type: Optional[str] = None
    account_type: Optional[str] = None

class BulkPriceChangeRequest(BaseModel):
    category_id: Optional[int] = None  # None = all categories
    product_ids: Optional[List[str]] = None  # Optional specific list of "local_X" / "reseller_Y"
    change_type: str  # "percentage" | "fixed_amount"
    change_value: float  # e.g. 10 for +10%, -5 for -5%, 0.50 for +$0.50
    round_to_nearest: Optional[float] = 0.25  # 0.25, 0.50, 1.0, or 0.01

class AddStockKeysRequest(BaseModel):
    keys: str  # Multiline string

class CreateCategoryRequest(BaseModel):
    name: str
    is_active: Optional[bool] = True

class UpdateCategoryRequest(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class StoreSettingsPayload(BaseModel):
    geo_filtering_enabled: Optional[bool] = True
    npr_exchange_rate: Optional[float] = 135.0
    nepal_qr_url: Optional[str] = ""
    nepal_qr_title: Optional[str] = "eSewa / Khalti / Fonepay Direct QR"
    nepal_qr_account_name: Optional[str] = "Kali Store Nepal"
    nepal_qr_account_id: Optional[str] = "9800000000"
    nepal_qr_instructions: Optional[str] = ""
    nepal_coming_soon: Optional[bool] = False
    nepal_coming_soon_text: Optional[str] = ""
    mantra_bar_text: Optional[str] = "॥ ॐ क्रीं कालिकायै नमः • दिव्य डिजिटल शक्ति एवं अचूक सुरक्षा ॥"
    hero_title: Optional[str] = "KALI DIGITAL STORE"
    hero_subtitle: Optional[str] = "Genuine ChatGPT Plus, Claude, Gemini, Canva Pro, JetBrains, VPNs, and Dev API tokens with instant cryptographic delivery and eternal warranty."
    announcement_banner_enabled: Optional[bool] = False
    announcement_banner_text: Optional[str] = ""
    announcement_banner_type: Optional[str] = "info"

class UploadQrPayload(BaseModel):
    image_data: str

class ResellerTopUpRequest(BaseModel):
    amount: float
    currency: Optional[str] = "USD"
    payment_method: Optional[str] = "USDT"
    note: Optional[str] = ""
    tx_hash: Optional[str] = ""
    update_balance: Optional[bool] = True

class ResellerTopUpItem(BaseModel):
    id: int
    source_id: int
    source_name: str
    amount: float
    currency: str
    payment_method: Optional[str] = None
    note: Optional[str] = None
    tx_hash: Optional[str] = None
    created_at: str

class ResellerSourceBalanceItem(BaseModel):
    id: int
    name: str
    balance: float
    currency: str
    is_active: bool
    last_synced: Optional[str] = None

class ResellerBudgetResponse(BaseModel):
    balances: List[ResellerSourceBalanceItem]
    total_balance_usd: float
    total_spent_usd: float
    total_loaded_usd: float
    orders_count: int
    topups: List[ResellerTopUpItem]


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
    total_local = (await db.scalar(select(func.count(Goods.id)))) or 0
    total_reseller = (await db.scalar(select(func.count(ResellerProduct.id)))) or 0
    total_products = total_local + total_reseller
    
    in_stock_local = (await db.scalar(
        select(func.count(func.distinct(Goods.id)))
        .join(ItemValues, ItemValues.item_id == Goods.id)
    )) or 0
    in_stock_reseller = (await db.scalar(
        select(func.count(ResellerProduct.id)).where(ResellerProduct.is_enabled == True)
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
        total_products=total_products,
        in_stock_products=in_stock_local + in_stock_reseller,
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

    op = Operations(
        user_id=user_id,
        operation_value=adj,
        operation_time=datetime.now(timezone.utc)
    )
    db.add(op)

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
    await db.commit()

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
    await db.commit()

    return {"status": "success", "is_blocked": target.is_blocked}


# ─────────────────────────────────────────────────────────────────────────────
# 3. Complete Flexible Product & Catalog Manager
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/products", response_model=List[AdminProductItem])
async def get_admin_products(
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    source_type: Optional[str] = None,  # "local", "reseller", or None (all)
    status_filter: Optional[str] = None,  # "active", "disabled", or None (all)
    badge_filter: Optional[str] = None,  # "featured", "hot", "bestseller"
    limit: int = Query(250, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    items = []

    # 1. Local Goods
    if not source_type or source_type == "local":
        local_q = (
            select(Goods, Categories.name.label("category_name"))
            .join(Categories, Goods.category_id == Categories.id)
        )
        if category_id and category_id != 999:
            local_q = local_q.where(Goods.category_id == category_id)
        if search:
            local_q = local_q.where(Goods.name.ilike(f"%{search.strip()}%"))
        if status_filter == "active":
            local_q = local_q.where(Goods.is_active == True)
        elif status_filter == "disabled":
            local_q = local_q.where(Goods.is_active == False)
        
        if badge_filter == "featured":
            local_q = local_q.where(Goods.is_featured == True)
        elif badge_filter == "hot":
            local_q = local_q.where(Goods.is_hot == True)
        elif badge_filter == "bestseller":
            local_q = local_q.where(Goods.is_bestseller == True)

        local_rows = (await db.execute(local_q.order_by(Goods.id))).all()
        for good, cat_name in local_rows:
            stock_count = (await db.scalar(
                select(func.count(ItemValues.id)).where(ItemValues.item_id == good.id)
            )) or 0
            items.append(AdminProductItem(
                id=f"local_{good.id}",
                raw_id=good.id,
                name=good.name,
                description=good.description or "",
                category_id=good.category_id,
                category_name=cat_name,
                price=float(good.price),
                price_npr=float(good.price_npr) if getattr(good, "price_npr", None) is not None else None,
                cost_price=float(good.cost_price or 0),
                stock=stock_count,
                is_featured=bool(getattr(good, "is_featured", False)),
                is_hot=bool(getattr(good, "is_hot", False)),
                is_bestseller=bool(getattr(good, "is_bestseller", False)),
                badge_text=getattr(good, "badge_text", None),
                is_active=bool(getattr(good, "is_active", True)),
                auto_delivery=bool(getattr(good, "auto_delivery", True)),
                delivery_template=getattr(good, "delivery_template", None),
                delivery_type=getattr(good, "delivery_type", "instant") or "instant",
                account_type=getattr(good, "account_type", "preactivated") or "preactivated",
                warranty=good.warranty,
                note=good.note,
                source_type="local",
                source_name="Local Store",
            ))

    # 2. Reseller Products
    if not source_type or source_type == "reseller":
        if not category_id or category_id == 999:
            res_q = (
                select(ResellerProduct, ResellerSource.name.label("source_name"))
                .outerjoin(ResellerSource, ResellerProduct.source_id == ResellerSource.id)
            )
            if search:
                res_q = res_q.where(ResellerProduct.name.ilike(f"%{search.strip()}%"))
            if status_filter == "active":
                res_q = res_q.where(ResellerProduct.is_enabled == True)
            elif status_filter == "disabled":
                res_q = res_q.where(ResellerProduct.is_enabled == False)

            if badge_filter == "featured":
                res_q = res_q.where(ResellerProduct.is_featured == True)
            elif badge_filter == "hot":
                res_q = res_q.where(ResellerProduct.is_hot == True)
            elif badge_filter == "bestseller":
                res_q = res_q.where(ResellerProduct.is_bestseller == True)

            res_rows = (await db.execute(res_q.order_by(ResellerProduct.id))).all()
            for rp, src_name in res_rows:
                items.append(AdminProductItem(
                    id=f"reseller_{rp.id}",
                    raw_id=rp.id,
                    name=rp.effective_name,
                    description=getattr(rp, "effective_description", None) or rp.description or "",
                    category_id=999,
                    category_name="Wholesale Reseller APIs",
                    price=float(rp.effective_sell_price),
                    price_npr=float(rp.price_npr) if getattr(rp, "price_npr", None) is not None else None,
                    cost_price=float(rp.cost_price or 0),
                    stock=rp.stock if rp.stock is not None else 999,
                    is_featured=bool(getattr(rp, "is_featured", False)),
                    is_hot=bool(getattr(rp, "is_hot", False)),
                    is_bestseller=bool(getattr(rp, "is_bestseller", False)),
                    badge_text=getattr(rp, "badge_text", None),
                    is_active=bool(getattr(rp, "is_enabled", True)),
                    auto_delivery=bool(getattr(rp, "auto_delivery", True)),
                    delivery_template=getattr(rp, "delivery_template", None),
                    delivery_type=getattr(rp, "delivery_type", "instant") or "instant",
                    account_type=getattr(rp, "account_type", "preactivated") or "preactivated",
                    warranty="24 Hours",
                    note=f"API Product ({rp.product_type})",
                    source_type="reseller",
                    source_name=src_name or "Reseller API",
                ))

    return items[offset:offset + limit]


@router.post("/products")
async def create_admin_product(
    payload: CreateProductRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new local digital product with full flexible options."""
    prod = Goods(
        name=payload.name.strip(),
        category_id=payload.category_id,
        price=Decimal(str(payload.price)),
        price_npr=Decimal(str(payload.price_npr)) if payload.price_npr and payload.price_npr > 0 else None,
        cost_price=Decimal(str(payload.cost_price or 0)),
        description=payload.description or f"100% Genuine {payload.name.strip()} with Instant Delivery.",
        warranty=payload.warranty,
        note=payload.note,
        is_featured=payload.is_featured or False,
        is_hot=payload.is_hot or False,
        is_bestseller=payload.is_bestseller or False,
        badge_text=payload.badge_text,
        is_active=True,
        auto_delivery=True if payload.auto_delivery is None else payload.auto_delivery,
        delivery_template=payload.delivery_template.strip() if payload.delivery_template else None,
        delivery_type=payload.delivery_type or "instant",
        account_type=payload.account_type or "preactivated",
    )
    db.add(prod)
    await db.flush()

    added_keys_count = 0
    if payload.initial_keys:
        lines = [line.strip() for line in payload.initial_keys.splitlines() if line.strip()]
        for val in lines:
            item_val = ItemValues(item_id=prod.id, value=val, is_infinity=False)
            db.add(item_val)
            added_keys_count += 1

    await db.commit()
    return {"status": "success", "product_id": f"local_{prod.id}", "added_keys": added_keys_count}


@router.patch("/products/{product_id}")
async def patch_admin_product(
    product_id: str,
    payload: UpdateProductRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Flexible single-item editor for price, NPR price, cost_price, name, active status, description, and badges.
    Supports both local items ('local_1' / '1') and reseller items ('reseller_5').
    """
    is_reseller = product_id.startswith("reseller_")
    
    if is_reseller:
        raw_id = int(product_id.replace("reseller_", ""))
        rp = (await db.execute(select(ResellerProduct).where(ResellerProduct.id == raw_id))).scalar_one_or_none()
        if not rp:
            raise HTTPException(status_code=404, detail="Reseller product not found")
        
        if payload.name is not None:
            rp.name_override = payload.name.strip()
        if payload.price is not None:
            rp.sell_price = Decimal(str(payload.price))
        if payload.price_npr is not None:
            rp.price_npr = Decimal(str(payload.price_npr)) if payload.price_npr > 0 else None
        if payload.is_featured is not None:
            rp.is_featured = payload.is_featured
        if payload.is_hot is not None:
            rp.is_hot = payload.is_hot
        if payload.is_bestseller is not None:
            rp.is_bestseller = payload.is_bestseller
        if payload.badge_text is not None:
            rp.badge_text = payload.badge_text.strip() if payload.badge_text else None
        if payload.is_active is not None:
            rp.is_enabled = payload.is_active
        if payload.auto_delivery is not None:
            rp.auto_delivery = payload.auto_delivery
        if payload.delivery_template is not None:
            rp.delivery_template = payload.delivery_template.strip() if payload.delivery_template else None
        if payload.delivery_type is not None:
            rp.delivery_type = payload.delivery_type
        if payload.account_type is not None:
            rp.account_type = payload.account_type
        if payload.description is not None:
            rp.description_override = payload.description.strip()
            rp.description = payload.description.strip()
            
        await db.commit()
        return {"status": "success", "message": "Reseller product updated successfully"}

    else:
        raw_id = int(product_id.replace("local_", "")) if product_id.startswith("local_") else int(product_id)
        prod = (await db.execute(select(Goods).where(Goods.id == raw_id))).scalar_one_or_none()
        if not prod:
            raise HTTPException(status_code=404, detail="Product not found")

        if payload.name is not None:
            prod.name = payload.name.strip()
        if payload.price is not None:
            prod.price = Decimal(str(payload.price))
        if payload.price_npr is not None:
            prod.price_npr = Decimal(str(payload.price_npr)) if payload.price_npr > 0 else None
        if payload.cost_price is not None:
            prod.cost_price = Decimal(str(payload.cost_price))
        if payload.category_id is not None:
            prod.category_id = payload.category_id
        if payload.warranty is not None:
            prod.warranty = payload.warranty
        if payload.note is not None:
            prod.note = payload.note
        if payload.description is not None:
            prod.description = payload.description.strip()
        if payload.is_featured is not None:
            prod.is_featured = payload.is_featured
        if payload.is_hot is not None:
            prod.is_hot = payload.is_hot
        if payload.is_bestseller is not None:
            prod.is_bestseller = payload.is_bestseller
        if payload.badge_text is not None:
            prod.badge_text = payload.badge_text.strip() if payload.badge_text else None
        if payload.is_active is not None:
            prod.is_active = payload.is_active
        if payload.auto_delivery is not None:
            prod.auto_delivery = payload.auto_delivery
        if payload.delivery_template is not None:
            prod.delivery_template = payload.delivery_template.strip() if payload.delivery_template else None
        if payload.delivery_type is not None:
            prod.delivery_type = payload.delivery_type
        if payload.account_type is not None:
            prod.account_type = payload.account_type

        await db.commit()
        return {"status": "success", "message": "Product updated successfully"}


@router.post("/products/{product_id}/toggle-active")
async def toggle_product_active(
    product_id: str,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """1-click toggle to enable or disable any item in the store."""
    if product_id.startswith("reseller_"):
        raw_id = int(product_id.replace("reseller_", ""))
        rp = (await db.execute(select(ResellerProduct).where(ResellerProduct.id == raw_id))).scalar_one_or_none()
        if not rp:
            raise HTTPException(status_code=404, detail="Reseller product not found")
        rp.is_enabled = not rp.is_enabled
        await db.commit()
        return {"status": "success", "is_active": rp.is_enabled}
    else:
        raw_id = int(product_id.replace("local_", "")) if product_id.startswith("local_") else int(product_id)
        prod = (await db.execute(select(Goods).where(Goods.id == raw_id))).scalar_one_or_none()
        if not prod:
            raise HTTPException(status_code=404, detail="Product not found")
        prod.is_active = not prod.is_active
        await db.commit()
        return {"status": "success", "is_active": prod.is_active}


@router.post("/products/{product_id}/toggle-badge")
async def toggle_product_badge(
    product_id: str,
    badge_type: str = Query(..., pattern="^(featured|hot|bestseller)$"),
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """1-click toggle for highlight badges (featured, hot, bestseller)."""
    if product_id.startswith("reseller_"):
        raw_id = int(product_id.replace("reseller_", ""))
        item = (await db.execute(select(ResellerProduct).where(ResellerProduct.id == raw_id))).scalar_one_or_none()
    else:
        raw_id = int(product_id.replace("local_", "")) if product_id.startswith("local_") else int(product_id)
        item = (await db.execute(select(Goods).where(Goods.id == raw_id))).scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Product not found")

    if badge_type == "featured":
        item.is_featured = not item.is_featured
        new_val = item.is_featured
    elif badge_type == "hot":
        item.is_hot = not item.is_hot
        new_val = item.is_hot
    elif badge_type == "bestseller":
        item.is_bestseller = not item.is_bestseller
        new_val = item.is_bestseller

    await db.commit()
    return {"status": "success", "badge": badge_type, "value": new_val}


@router.post("/products/bulk-price")
async def bulk_price_adjustment(
    payload: BulkPriceChangeRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk price adjust tool:
    Modifies prices for all products in a category or selected IDs by +/-% or +/-% fixed USD.
    """
    updated_count = 0

    # 1. Local Goods
    local_q = select(Goods)
    if payload.category_id and payload.category_id != 999:
        local_q = local_q.where(Goods.category_id == payload.category_id)
    
    local_prods = (await db.execute(local_q)).scalars().all()
    for p in local_prods:
        if payload.product_ids and f"local_{p.id}" not in payload.product_ids:
            continue
        
        current_p = float(p.price)
        if payload.change_type == "percentage":
            new_p = current_p * (1.0 + payload.change_value / 100.0)
        else:  # fixed_amount
            new_p = current_p + payload.change_value
        
        # Round to step
        step = payload.round_to_nearest or 0.25
        new_p = max(0.25, round(round(new_p / step) * step, 2))
        p.price = Decimal(str(new_p))
        updated_count += 1

    # 2. Reseller Products
    if not payload.category_id or payload.category_id == 999:
        res_q = select(ResellerProduct)
        res_prods = (await db.execute(res_q)).scalars().all()
        for rp in res_prods:
            if payload.product_ids and f"reseller_{rp.id}" not in payload.product_ids:
                continue
            
            current_p = float(rp.effective_sell_price)
            if payload.change_type == "percentage":
                new_p = current_p * (1.0 + payload.change_value / 100.0)
            else:
                new_p = current_p + payload.change_value
            
            step = payload.round_to_nearest or 0.25
            new_p = max(float(rp.cost_price or 0.25), round(round(new_p / step) * step, 2))
            rp.sell_price = Decimal(str(new_p))
            updated_count += 1

    await db.commit()
    return {"status": "success", "updated_products_count": updated_count}


@router.delete("/products/{product_id}")
async def delete_admin_product(
    product_id: str,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a product from the database."""
    if product_id.startswith("reseller_"):
        raw_id = int(product_id.replace("reseller_", ""))
        rp = (await db.execute(select(ResellerProduct).where(ResellerProduct.id == raw_id))).scalar_one_or_none()
        if not rp:
            raise HTTPException(status_code=404, detail="Reseller product not found")
        await db.delete(rp)
    else:
        raw_id = int(product_id.replace("local_", "")) if product_id.startswith("local_") else int(product_id)
        prod = (await db.execute(select(Goods).where(Goods.id == raw_id))).scalar_one_or_none()
        if not prod:
            raise HTTPException(status_code=404, detail="Product not found")
        await db.execute(ItemValues.__table__.delete().where(ItemValues.item_id == raw_id))
        await db.delete(prod)

    await db.commit()
    return {"status": "success", "message": "Product deleted successfully"}


@router.get("/products/{product_id}/stock")
async def get_product_stock_items(
    product_id: str,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """View individual stock credentials/keys for a local product."""
    if product_id.startswith("reseller_"):
        return {"items": [], "total_stock": 999, "is_reseller": True}

    raw_id = int(product_id.replace("local_", "")) if product_id.startswith("local_") else int(product_id)
    res = await db.execute(select(ItemValues).where(ItemValues.item_id == raw_id))
    rows = res.scalars().all()
    return {
        "items": [{"id": item.id, "value": item.value, "is_infinity": item.is_infinity} for item in rows],
        "total_stock": len(rows),
        "is_reseller": False
    }


@router.post("/products/{product_id}/stock")
async def add_product_stock_items(
    product_id: str,
    payload: AddStockKeysRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Bulk inject license keys or account credentials into product inventory."""
    if product_id.startswith("reseller_"):
        raise HTTPException(status_code=400, detail="Reseller products stock is managed via external APIs.")

    raw_id = int(product_id.replace("local_", "")) if product_id.startswith("local_") else int(product_id)
    prod = (await db.execute(select(Goods).where(Goods.id == raw_id))).scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    lines = [line.strip() for line in payload.keys.splitlines() if line.strip()]
    if not lines:
        raise HTTPException(status_code=400, detail="No valid keys provided")

    for val in lines:
        db.add(ItemValues(item_id=prod.id, value=val, is_infinity=False))

    await db.commit()
    return {"status": "success", "added_count": len(lines)}


@router.delete("/products/{product_id}/stock/{value_id}")
async def delete_single_stock_item(
    product_id: str,
    value_id: int,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a single key/credential from stock inventory."""
    val = (await db.execute(select(ItemValues).where(ItemValues.id == value_id))).scalar_one_or_none()
    if not val:
        raise HTTPException(status_code=404, detail="Stock item not found")

    await db.delete(val)
    await db.commit()
    return {"status": "success", "message": "Stock item removed"}


# ─────────────────────────────────────────────────────────────────────────────
# 4. Category Management
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


@router.post("/categories")
async def create_category(
    payload: CreateCategoryRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    name_str = payload.name.strip()
    if not name_str:
        raise HTTPException(status_code=400, detail="Category name cannot be empty")

    cat = Categories(name=name_str, is_active=payload.is_active if payload.is_active is not None else True)
    db.add(cat)
    await db.commit()
    return {"status": "success", "category_id": cat.id}


@router.patch("/categories/{category_id}")
async def update_category(
    category_id: int,
    payload: UpdateCategoryRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    cat = (await db.execute(select(Categories).where(Categories.id == category_id))).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    if payload.name is not None:
        cat.name = payload.name.strip()
    if payload.is_active is not None:
        cat.is_active = payload.is_active

    await db.commit()
    return {"status": "success", "message": "Category updated"}


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    cat = (await db.execute(select(Categories).where(Categories.id == category_id))).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    await db.delete(cat)
    await db.commit()
    return {"status": "success", "message": "Category deleted successfully"}


# ─────────────────────────────────────────────────────────────────────────────
# 5. Orders & Deliveries
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
# 6. Payments & Nepal QR Manual Approvals
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
    query = (
        select(Payments, User.email.label("user_email"))
        .outerjoin(User, Payments.user_id == User.telegram_id)
    )

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
    rows = (await db.execute(query)).all()

    return [
        AdminPaymentItem(
            id=p.id,
            provider=p.provider,
            external_id=p.external_id,
            user_id=p.user_id,
            user_email=user_email,
            amount=float(p.amount),
            currency=p.currency,
            status=p.status,
            created_at=p.created_at.isoformat() if p.created_at else "",
        )
        for p, user_email in rows
    ]


@router.get("/payments/pending-nepal", response_model=List[PendingNepalPaymentItem])
async def get_pending_nepal_payments(
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns all pending Nepal QR payment submissions with receipt proof images for review."""
    query = (
        select(Payments, User.email.label("user_email"))
        .outerjoin(User, Payments.user_id == User.telegram_id)
        .where(Payments.provider == "nepal_qr", Payments.status == "pending")
        .order_by(desc(Payments.created_at))
    )
    rows = (await db.execute(query)).all()

    items = []
    for pmt, user_email in rows:
        amount_usd = float(pmt.amount)
        amount_npr = round(amount_usd * 135.0, 2)
        tx_id = pmt.external_id.split("::")[0] if pmt.external_id else "N/A"
        
        items.append(PendingNepalPaymentItem(
            id=pmt.id,
            payment_id=pmt.id,
            tx_id=tx_id,
            user_id=pmt.user_id,
            user_email=user_email,
            amount_usd=amount_usd,
            amount_npr=amount_npr,
            note=pmt.external_id,
            created_at=pmt.created_at.isoformat() if pmt.created_at else "",
            status=pmt.status
        ))
    return items


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

    if target_email:
        from packages.services.email_service import send_order_delivery_email
        import asyncio
        asyncio.create_task(
            send_order_delivery_email(
                customer_email=target_email,
                product_name="Nepal QR Wallet Deposit / Order Verification",
                quantity=1,
                amount_str=f"NPR {int(credited_amount * 135):,} (${credited_amount:.2f} USD)",
                delivered_content=f"Payment verified & credited successfully!\nYour balance has been updated with NPR {int(credited_amount * 135):,}.\nYou can now access your products instantly in your Account Dashboard.",
                order_id=f"PMT-{payment_id}",
                tx_id=pmt.external_id.split("::")[0] if pmt.external_id else ""
            )
        )

    return {"status": "success", "message": f"Payment #{payment_id} approved. Credited NPR {int(credited_amount * 135):,} (${credited_amount:.2f} USD) to user balance."}


@router.post("/payments/{payment_id}/reject")
async def reject_payment(
    payment_id: int,
    reason: Optional[str] = Query("Payment rejected by admin review"),
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Reject a pending payment record."""
    pmt = (await db.execute(select(Payments).where(Payments.id == payment_id))).scalar_one_or_none()
    if not pmt:
        raise HTTPException(status_code=404, detail="Payment record not found")

    pmt.status = "failed"
    audit = AuditLog(
        timestamp=datetime.now(timezone.utc),
        level="WARNING",
        user_id=admin.telegram_id,
        action="admin_reject_payment",
        resource_type="Payment",
        resource_id=str(payment_id),
        details=f"Rejected payment {pmt.external_id}. Reason: {reason}"
    )
    db.add(audit)
    await db.commit()
    return {"status": "success", "message": f"Payment #{payment_id} rejected."}


@router.get("/users/{user_id}/purchases", response_model=List[UserPurchaseItem])
async def get_user_purchases(
    user_id: int,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve complete purchase history & delivered credentials for a specific user."""
    # 1. Query bought_goods
    bg_rows = (await db.execute(
        select(BoughtGoods)
        .where(BoughtGoods.buyer_id == user_id)
        .order_by(desc(BoughtGoods.bought_datetime))
    )).scalars().all()

    purchases = []
    for bg in bg_rows:
        p = float(bg.price)
        cp = float(bg.cost_price or 0)
        purchases.append(UserPurchaseItem(
            id=bg.id,
            unique_id=bg.unique_id,
            item_name=bg.item_name,
            price=p,
            cost_price=cp,
            profit=round(max(0.0, p - cp), 2),
            bought_datetime=bg.bought_datetime.isoformat() if bg.bought_datetime else "",
            value=bg.value or "",
            source_type="local",
            status="delivered"
        ))

    # 2. Check standalone reseller orders
    ro_rows = (await db.execute(
        select(ResellerOrder, ResellerProduct.name.label("prod_name"))
        .outerjoin(ResellerProduct, ResellerOrder.reseller_product_id == ResellerProduct.id)
        .where(ResellerOrder.user_id == user_id, ResellerOrder.bought_goods_id == None)
        .order_by(desc(ResellerOrder.created_at))
    )).all()

    for ro, prod_name in ro_rows:
        purchases.append(UserPurchaseItem(
            id=ro.id,
            unique_id=ro.id * 1000,
            item_name=prod_name or f"Reseller Order #{ro.id}",
            price=float(ro.charge_amount or 0),
            cost_price=float(ro.charge_amount or 0),
            profit=0.0,
            bought_datetime=ro.created_at.isoformat() if ro.created_at else "",
            value=ro.delivered_codes or (ro.error_message if ro.status == 'failed' else f"Status: {ro.status}"),
            source_type="reseller",
            status=ro.status
        ))

    return purchases


# ─────────────────────────────────────────────────────────────────────────────
# 7. Reseller API Budget & Wallet Tracking
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/resellers/budget", response_model=ResellerBudgetResponse)
async def get_reseller_budget(
    period: str = Query("all", description="all | day | week | month | custom"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get live reseller API wallet balances, total spend from orders,
    total loaded amounts, and top-up transactions filtered by time period.
    """
    now = datetime.now(timezone.utc)
    from_date = None
    to_date = None

    if period == "day":
        from_date = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    elif period == "week":
        from_date = now - timedelta(days=7)
    elif period == "month":
        from_date = now - timedelta(days=30)
    elif period == "custom":
        if start_date:
            try:
                from_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            except Exception:
                pass
        if end_date:
            try:
                to_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            except Exception:
                pass

    # 1. Fetch Reseller Sources & Balances
    sources = (await db.execute(select(ResellerSource).order_by(ResellerSource.id))).scalars().all()
    source_balances = []
    total_balance_usd = 0.0

    # Fetch total top-ups per source
    topup_totals_res = await db.execute(
        select(ResellerTopUp.source_id, func.coalesce(func.sum(ResellerTopUp.amount), 0.0))
        .group_by(ResellerTopUp.source_id)
    )
    topup_map = dict(topup_totals_res.all())

    # Fetch total spend per source
    spend_totals_res = await db.execute(
        select(ResellerOrder.source_id, func.coalesce(func.sum(ResellerOrder.charge_amount), 0.0))
        .where(ResellerOrder.status.in_(["delivered", "placed", "pending"]))
        .group_by(ResellerOrder.source_id)
    )
    spend_map = dict(spend_totals_res.all())

    for s in sources:
        loaded = float(topup_map.get(s.id, 0.0))
        spent = float(spend_map.get(s.id, 0.0))
        bal = max(0.0, loaded - spent)
        total_balance_usd += bal
        source_balances.append(ResellerSourceBalanceItem(
            id=s.id,
            name=s.name,
            balance=bal,
            currency="USD",
            is_active=bool(s.is_active),
            last_synced=s.last_synced.isoformat() if s.last_synced else None
        ))

    # 2. Query Reseller Orders Spend in Time Window
    order_q = select(ResellerOrder).where(ResellerOrder.status.in_(["delivered", "placed"]))
    if from_date:
        order_q = order_q.where(ResellerOrder.created_at >= from_date)
    if to_date:
        order_q = order_q.where(ResellerOrder.created_at <= to_date)

    orders_in_period = (await db.execute(order_q)).scalars().all()
    total_spent_usd = sum(float(o.charge_amount or 0.0) for o in orders_in_period)
    orders_count = len(orders_in_period)

    # 3. Query Top-up logs in Time Window
    topup_q = (
        select(ResellerTopUp, ResellerSource.name.label("source_name"))
        .join(ResellerSource, ResellerTopUp.source_id == ResellerSource.id)
    )
    if from_date:
        topup_q = topup_q.where(ResellerTopUp.created_at >= from_date)
    if to_date:
        topup_q = topup_q.where(ResellerTopUp.created_at <= to_date)

    topup_rows = (await db.execute(topup_q.order_by(desc(ResellerTopUp.created_at)))).all()
    topup_items = []
    total_loaded_usd = 0.0
    for tu, sname in topup_rows:
        amt = float(tu.amount)
        total_loaded_usd += amt
        topup_items.append(ResellerTopUpItem(
            id=tu.id,
            source_id=tu.source_id,
            source_name=sname,
            amount=amt,
            currency=tu.currency or "USD",
            payment_method=tu.payment_method,
            note=tu.note,
            tx_hash=tu.tx_hash,
            created_at=tu.created_at.isoformat() if tu.created_at else ""
        ))

    return ResellerBudgetResponse(
        balances=source_balances,
        total_balance_usd=round(total_balance_usd, 2),
        total_spent_usd=round(total_spent_usd, 2),
        total_loaded_usd=round(total_loaded_usd, 2),
        orders_count=orders_count,
        topups=topup_items
    )


@router.post("/resellers/{source_id}/topup")
async def record_reseller_topup(
    source_id: int,
    payload: ResellerTopUpRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Record an external API wallet deposit/top-up and update cached balance."""
    src = (await db.execute(select(ResellerSource).where(ResellerSource.id == source_id))).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail="Reseller source not found")

    topup = ResellerTopUp(
        source_id=src.id,
        amount=Decimal(str(payload.amount)),
        currency=payload.currency or "USD",
        payment_method=payload.payment_method or "USDT",
        note=payload.note or f"Manual deposit of ${payload.amount} recorded by Admin",
        tx_hash=payload.tx_hash or None,
    )
    db.add(topup)

    if payload.update_balance:
        current_bal = float(src.balance or 0.0)
        src.balance = Decimal(str(current_bal + payload.amount))

    await db.commit()
    return {"status": "success", "message": f"Recorded ${payload.amount:.2f} deposit for {src.name}"}


# ─────────────────────────────────────────────────────────────────────────────
# 8. Global Store Settings & Website Content
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/settings")
async def get_admin_store_settings(
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all global store configuration (Geo-filter, Exchange rate, Nepal QR, Website Announcements)."""
    keys = [
        "geo_filtering_enabled", "npr_exchange_rate",
        "nepal_qr_url", "nepal_qr_title", "nepal_qr_account_name",
        "nepal_qr_account_id", "nepal_qr_instructions",
        "nepal_coming_soon", "nepal_coming_soon_text",
        "mantra_bar_text", "hero_title", "hero_subtitle",
        "announcement_banner_enabled", "announcement_banner_text", "announcement_banner_type"
    ]
    res = await db.execute(select(BotSettings).where(BotSettings.key.in_(keys)))
    settings = {s.key: s.value for s in res.scalars().all()}

    return {
        "geo_filtering_enabled": settings.get("geo_filtering_enabled", "true").lower() == "true",
        "npr_exchange_rate": float(settings.get("npr_exchange_rate", "135.0")),
        "nepal_qr_url": settings.get("nepal_qr_url") or "",
        "nepal_qr_title": settings.get("nepal_qr_title") or "eSewa / Khalti / Fonepay Direct QR",
        "nepal_qr_account_name": settings.get("nepal_qr_account_name") or "Kali Store Nepal",
        "nepal_qr_account_id": settings.get("nepal_qr_account_id") or "9800000000",
        "nepal_qr_instructions": settings.get("nepal_qr_instructions") or "Scan QR with eSewa/Khalti/Fonepay, transfer exact NPR amount, then submit your Tx Reference ID below.",
        "nepal_coming_soon": settings.get("nepal_coming_soon", "false").lower() == "true",
        "nepal_coming_soon_text": settings.get("nepal_coming_soon_text") or "🇳🇵 Nepal Store Direct Local Payment Gateway & Catalog Expansion is Coming Soon!",
        "mantra_bar_text": settings.get("mantra_bar_text") or "॥ ॐ क्रीं कालिकायै नमः • दिव्य डिजिटल शक्ति एवं अचूक सुरक्षा ॥",
        "hero_title": settings.get("hero_title") or "KALI DIGITAL STORE",
        "hero_subtitle": settings.get("hero_subtitle") or "Genuine ChatGPT Plus, Claude, Gemini, Canva Pro, JetBrains, VPNs, and Dev API tokens with instant cryptographic delivery and eternal warranty.",
        "announcement_banner_enabled": settings.get("announcement_banner_enabled", "false").lower() == "true",
        "announcement_banner_text": settings.get("announcement_banner_text") or "",
        "announcement_banner_type": settings.get("announcement_banner_type") or "info",
    }


@router.post("/settings")
async def update_admin_store_settings(
    payload: StoreSettingsPayload,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Save global store configuration."""
    mapping = {
        "geo_filtering_enabled": "true" if payload.geo_filtering_enabled is not False else "false",
        "npr_exchange_rate": str(payload.npr_exchange_rate or 135.0),
        "nepal_qr_url": payload.nepal_qr_url or "",
        "nepal_qr_title": payload.nepal_qr_title or "eSewa / Khalti / Fonepay Direct QR",
        "nepal_qr_account_name": payload.nepal_qr_account_name or "",
        "nepal_qr_account_id": payload.nepal_qr_account_id or "",
        "nepal_qr_instructions": payload.nepal_qr_instructions or "",
        "nepal_coming_soon": "true" if payload.nepal_coming_soon else "false",
        "nepal_coming_soon_text": payload.nepal_coming_soon_text or "",
        "mantra_bar_text": payload.mantra_bar_text or "॥ ॐ क्रीं कालिकायै नमः • दिव्य डिजिटल शक्ति एवं अचूक सुरक्षा ॥",
        "hero_title": payload.hero_title or "KALI DIGITAL STORE",
        "hero_subtitle": payload.hero_subtitle or "",
        "announcement_banner_enabled": "true" if payload.announcement_banner_enabled else "false",
        "announcement_banner_text": payload.announcement_banner_text or "",
        "announcement_banner_type": payload.announcement_banner_type or "info",
    }
    for k, v in mapping.items():
        existing = (await db.execute(select(BotSettings).where(BotSettings.key == k))).scalar_one_or_none()
        if existing:
            existing.value = str(v)
        else:
            db.add(BotSettings(key=k, value=str(v)))

    await db.commit()
    return {"status": "success", "message": "Store configuration saved successfully"}


@router.post("/settings/upload-qr")
async def upload_qr_image(
    payload: UploadQrPayload,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Save an uploaded QR code image and configure it for the store."""
    data = payload.image_data.strip()
    if not data:
        raise HTTPException(status_code=400, detail="No image data provided")

    existing = (await db.execute(select(BotSettings).where(BotSettings.key == "nepal_qr_url"))).scalar_one_or_none()
    if existing:
        existing.value = data
    else:
        db.add(BotSettings(key="nepal_qr_url", value=data))

    await db.commit()
    return {"status": "success", "qr_url": data, "message": "QR Image uploaded and saved successfully"}


@router.get("/settings/public")
async def get_public_store_settings(db: AsyncSession = Depends(get_db)):
    """Public store settings for customer site (Sacred Mantra, Hero Banner, Announcements)."""
    keys = [
        "mantra_bar_text", "hero_title", "hero_subtitle",
        "announcement_banner_enabled", "announcement_banner_text", "announcement_banner_type",
        "nepal_coming_soon", "nepal_coming_soon_text", "nepal_qr_url", "nepal_qr_title"
    ]
    res = await db.execute(select(BotSettings).where(BotSettings.key.in_(keys)))
    settings = {s.key: s.value for s in res.scalars().all()}

    return {
        "mantra_bar_text": settings.get("mantra_bar_text") or "॥ ॐ क्रीं कालिकायै नमः • दिव्य डिजिटल शक्ति एवं अचूक सुरक्षा ॥",
        "hero_title": settings.get("hero_title") or "KALI DIGITAL STORE",
        "hero_subtitle": settings.get("hero_subtitle") or "Genuine ChatGPT Plus, Claude, Gemini, Canva Pro, JetBrains, VPNs, and Dev API tokens with instant cryptographic delivery and eternal warranty.",
        "announcement_banner_enabled": settings.get("announcement_banner_enabled", "false").lower() == "true",
        "announcement_banner_text": settings.get("announcement_banner_text") or "",
        "announcement_banner_type": settings.get("announcement_banner_type") or "info",
        "nepal_coming_soon": settings.get("nepal_coming_soon", "false").lower() == "true",
        "nepal_coming_soon_text": settings.get("nepal_coming_soon_text") or "",
        "nepal_qr_url": settings.get("nepal_qr_url") or "",
        "nepal_qr_title": settings.get("nepal_qr_title") or "eSewa / Khalti / Fonepay Direct QR",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 8. Promocodes & Security Audit
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
    promo = (await db.execute(select(PromoCodes).where(PromoCodes.id == promo_id))).scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=404, detail="Promocode not found")

    await db.delete(promo)
    await db.commit()
    return {"status": "success", "message": "Promocode deleted"}

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


# ─────────────────────────────────────────────────────────────────────────────
# Delivery Templates & 1-Click Auto-Fulfillment API
# ─────────────────────────────────────────────────────────────────────────────

class AutoFulfillOrderRequest(BaseModel):
    product_id: str
    product_name: str
    quantity: int = 1
    amount_str: str
    customer_email: str
    tx_id: Optional[str] = ""
    order_id: Optional[str] = ""

class UpdateGlobalDeliveryTemplateRequest(BaseModel):
    template: str
    global_auto_delivery_enabled: bool = True

@router.get("/settings/delivery-templates")
async def get_delivery_templates(
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetch global delivery template, auto delivery status, and available placeholders."""
    keys = ["global_auto_delivery_enabled", "global_delivery_template"]
    res = await db.execute(select(BotSettings).where(BotSettings.key.in_(keys)))
    settings = {s.key: s.value for s in res.scalars().all()}

    default_tpl = (
        "Hello {customer_email},\n\n"
        "Thank you for your order! Here are your digital credentials:\n\n"
        "{credentials}\n\n"
        "Product: {product_name} (x{quantity})\n"
        "Warranty: {warranty}\n"
        "Note: {note}\n\n"
        "Support Contact: {support_contact}"
    )

    return {
        "global_auto_delivery_enabled": settings.get("global_auto_delivery_enabled", "true").lower() == "true",
        "global_delivery_template": settings.get("global_delivery_template") or default_tpl,
        "available_placeholders": [
            {"tag": "{customer_email}", "desc": "Customer delivery email address"},
            {"tag": "{product_name}", "desc": "Name of the digital product"},
            {"tag": "{quantity}", "desc": "Number of licenses purchased"},
            {"tag": "{amount}", "desc": "Total order amount (NPR or USD)"},
            {"tag": "{credentials}", "desc": "Generated keys, accounts, or activation tokens"},
            {"tag": "{warranty}", "desc": "Product warranty period"},
            {"tag": "{note}", "desc": "Special product note / instructions"},
            {"tag": "{tx_id}", "desc": "Payment transaction reference code"},
            {"tag": "{support_contact}", "desc": "Telegram customer support link"},
        ]
    }


@router.post("/settings/delivery-templates")
async def update_delivery_templates(
    payload: UpdateGlobalDeliveryTemplateRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Update global auto delivery switch and default message template."""
    async def set_setting(k: str, v: str):
        s = (await db.execute(select(BotSettings).where(BotSettings.key == k))).scalar_one_or_none()
        if s:
            s.value = v
        else:
            db.add(BotSettings(key=k, value=v))

    await set_setting("global_auto_delivery_enabled", "true" if payload.global_auto_delivery_enabled else "false")
    await set_setting("global_delivery_template", payload.template.strip())
    await db.commit()
    return {"status": "success", "message": "Delivery template settings saved"}


@router.post("/orders/auto-fulfill")
async def admin_auto_fulfill_order(
    payload: AutoFulfillOrderRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    1-Click Auto Fulfill from Provider API or Local Stock:
    Executes provider purchase, generates credentials, and emails customer while emitting Telegram stages.
    """
    from packages.services.reseller.fulfillment import execute_auto_delivery_pipeline

    success, creds_or_err, final_status = await execute_auto_delivery_pipeline(
        product_id_str=payload.product_id,
        product_name=payload.product_name,
        quantity=payload.quantity,
        amount_str=payload.amount_str,
        customer_email=payload.customer_email,
        tx_id=payload.tx_id or "",
        order_id=payload.order_id or "",
    )

    if not success:
        raise HTTPException(status_code=400, detail=f"Fulfillment failed: {creds_or_err}")

    return {
        "status": "success",
        "message": f"Successfully fulfilled and delivered to {payload.customer_email}",
        "credentials": creds_or_err,
        "delivery_status": final_status,
    }

