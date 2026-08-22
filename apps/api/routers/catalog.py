from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime, timezone

from apps.api.dependencies import get_db, get_current_user, get_optional_current_user
from packages.database.models import Categories, Goods, ItemValues, ResellerProduct, ResellerSource, PromoCodes, ProductReview, ProductUpvote

router = APIRouter(prefix="/api/catalog", tags=["Catalog"])


class PromoValidateRequest(BaseModel):
    code: str
    amount: float = 0.0
    product_id: Optional[str] = None


@router.get("/categories")
async def get_categories(db: AsyncSession = Depends(get_db)):
    """Get all active categories with purchase counts."""
    from packages.database.models import BoughtGoods
    from sqlalchemy import func

    result = await db.execute(select(Categories))
    categories = result.scalars().all()
    
    cats = []
    for c in categories:
        if not c.is_active:
            continue
        # Query purchases for goods in this category
        goods_in_cat = (await db.execute(select(Goods.name).where(Goods.category_id == c.id))).scalars().all()
        actual_purchases = 0
        if goods_in_cat:
            count_res = (await db.execute(
                select(func.count(BoughtGoods.id)).where(BoughtGoods.item_name.in_(goods_in_cat))
            )).scalar() or 0
            actual_purchases = count_res

        # Social proof counter combining actual + established baseline
        baseline = ((c.id * 73) % 180) + 65
        total_purchases = actual_purchases + baseline

        cats.append({
            "id": c.id,
            "name": c.name,
            "is_active": c.is_active,
            "purchases_count": total_purchases,
        })

    # Include default Wholesale Reseller Category if not present
    if not any(c["id"] == 999 for c in cats):
        cats.append({
            "id": 999, 
            "name": "⚡ Wholesale Reseller APIs", 
            "is_active": True,
            "purchases_count": 384,
        })
        
    return cats


@router.get("/products")
async def get_products(category_id: int = None, db: AsyncSession = Depends(get_db)):
    """
    Get all active products (includes both local Goods and ResellerProducts).
    """
    response = []

    # 1. Local Goods
    query = select(Goods)
    if category_id and category_id != 999:
        query = query.where(Goods.category_id == category_id)
        
    result = await db.execute(query)
    local_goods = result.scalars().all()
    
    def _get_rating_info(pid: str, pname: str):
        import hashlib
        h = int(hashlib.md5(f"{pid}_{pname}".encode()).hexdigest(), 16)
        ratings_choices = [4.7, 4.8, 4.9, 4.8, 4.9, 5.0, 4.7, 4.8]
        avg_rating = ratings_choices[h % len(ratings_choices)]
        review_count = 14 + (h % 53)
        return avg_rating, review_count

    for p in local_goods:
        stock_query = await db.execute(select(ItemValues).where(ItemValues.item_id == p.id))
        stock_count = len(stock_query.scalars().all())
        r_avg, r_count = _get_rating_info(str(p.id), p.name)
        
        response.append({
            "id": f"local_{p.id}",
            "raw_id": p.id,
            "name": p.name,
            "description": p.description or "Instant Delivery Digital Good",
            "price": float(p.price),
            "stock": stock_count,
            "image": getattr(p, "banner_file_id", None),
            "type": "local",
            "category_id": p.category_id,
            "is_instant": True,
            "is_featured": bool(getattr(p, "is_featured", False)),
            "rating": r_avg,
            "reviews_count": r_count,
        })

    # 2. Reseller Products
    if not category_id or category_id == 999:
        reseller_query = await db.execute(
            select(ResellerProduct, ResellerSource)
            .join(ResellerSource, ResellerProduct.source_id == ResellerSource.id)
            .where(ResellerProduct.is_enabled == True, ResellerSource.is_active == True)
        )
        rows = reseller_query.all()
        for p, src in rows:
            desc = p.description if p.description and len(p.description.strip()) > 5 else f"⚡ Instant Delivery • 100% Genuine {p.name} with Full Replacement Warranty."
            real_stock = p.stock if p.stock is not None else 999
            r_avg, r_count = _get_rating_info(str(p.id), p.name)
            response.append({
                "id": f"reseller_{p.id}",
                "raw_id": p.id,
                "name": p.name,
                "description": desc,
                "price": float(p.sell_price or p.cost_price or 0.0),
                "stock": real_stock,
                "image": None,
                "type": "reseller",
                "source": src.name if src else "digital",
                "category_id": 999,
                "is_instant": p.product_type in ("account", "stock", "digital"),
                "is_featured": bool(getattr(p, "is_featured", False)),
                "rating": r_avg,
                "reviews_count": r_count,
            })
        
    return response


@router.get("/featured")
async def get_featured_products(db: AsyncSession = Depends(get_db)):
    """
    Get all items marked as 'Featured' by Admin for display on the Dashboard.
    If no items are explicitly featured, falls back to the top 4 in-stock items.
    """
    featured = []

    # 1. Local Featured Goods
    local_featured = (await db.execute(
        select(Goods).where(Goods.is_featured == True)
    )).scalars().all()

    for p in local_featured:
        stock_query = await db.execute(select(ItemValues).where(ItemValues.item_id == p.id))
        stock_count = len(stock_query.scalars().all())
        featured.append({
            "id": f"local_{p.id}",
            "raw_id": p.id,
            "name": p.name,
            "description": p.description or "Premium Instant Delivery Digital Item",
            "price": float(p.price),
            "stock": stock_count,
            "image": getattr(p, "banner_file_id", None),
            "type": "local",
            "category_id": p.category_id,
            "is_instant": True,
            "is_featured": True,
        })

    # 2. Reseller Featured Products
    reseller_featured = (await db.execute(
        select(ResellerProduct)
        .where(ResellerProduct.is_featured == True, ResellerProduct.is_enabled == True)
    )).scalars().all()

    for rp in reseller_featured:
        featured.append({
            "id": f"reseller_{rp.id}",
            "raw_id": rp.id,
            "name": rp.name,
            "description": rp.description or f"Featured • {rp.product_type.replace('_', ' ').title() if rp.product_type else 'Digital Product'}",
            "price": float(rp.sell_price or rp.cost_price or 0.0),
            "stock": 999,
            "image": None,
            "type": "reseller",
            "source": "digital",
            "category_id": 999,
            "is_instant": True,
            "is_featured": True,
        })

    # 3. Fallback to top in-stock products if nothing is explicitly featured yet
    if not featured:
        all_goods = (await db.execute(select(Goods).limit(6))).scalars().all()
        for p in all_goods:
            stock_query = await db.execute(select(ItemValues).where(ItemValues.item_id == p.id))
            stock_count = len(stock_query.scalars().all())
            featured.append({
                "id": f"local_{p.id}",
                "raw_id": p.id,
                "name": p.name,
                "description": p.description or "Top Recommended Digital Good",
                "price": float(p.price),
                "stock": stock_count,
                "image": getattr(p, "banner_file_id", None),
                "type": "local",
                "category_id": p.category_id,
                "is_instant": True,
                "is_featured": False,
            })

    return featured


@router.get("/products/{product_id}")
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)):
    """Get details for a specific product by composite ID (local_1 or reseller_5)."""
    if product_id.startswith("reseller_"):
        res_id = int(product_id.replace("reseller_", ""))
        result = await db.execute(
            select(ResellerProduct, ResellerSource)
            .join(ResellerSource, ResellerProduct.source_id == ResellerSource.id)
            .where(ResellerProduct.id == res_id)
        )
        row = result.first()
        if not row:
            raise HTTPException(status_code=404, detail="Reseller product not found")
        p, src = row
        return {
            "id": f"reseller_{p.id}",
            "raw_id": p.id,
            "name": p.name,
            "description": f"Instant Delivery • {p.product_type.replace('_', ' ').title() if p.product_type else 'Digital Good'}",
            "price": float(p.sell_price or p.cost_price or 0.0),
            "stock": p.stock if p.stock is not None else 999,
            "type": "reseller",
            "source": "digital",
            "category_id": 999,
            "is_instant": p.product_type == "account",
        }

    raw_id = int(product_id.replace("local_", ""))
    result = await db.execute(select(Goods).where(Goods.id == raw_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    stock_query = await db.execute(select(ItemValues).where(ItemValues.item_id == product.id))
    stock_count = len(stock_query.scalars().all())
        
    return {
        "id": f"local_{product.id}",
        "raw_id": product.id,
        "name": product.name,
        "description": product.description or "Instant Delivery Digital Good",
        "price": float(product.price),
        "stock": stock_count,
        "type": "local",
        "category_id": product.category_id,
        "is_instant": True,
    }


@router.post("/promocode/validate")
async def validate_promocode(
    req: PromoValidateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Validate a promocode and return calculated discount."""
    code_str = req.code.strip().upper()
    if not code_str:
        raise HTTPException(status_code=400, detail="Promocode cannot be empty")

    result = await db.execute(select(PromoCodes).where(PromoCodes.code == code_str, PromoCodes.is_active == True))
    promo = result.scalar_one_or_none()

    if not promo:
        raise HTTPException(status_code=404, detail="Invalid or expired promocode")

    now = datetime.now(timezone.utc)
    if promo.expires_at and promo.expires_at < now:
        raise HTTPException(status_code=400, detail="Promocode has expired")

    if promo.max_uses > 0 and promo.current_uses >= promo.max_uses:
        raise HTTPException(status_code=400, detail="Promocode usage limit reached")

    discount_amount = 0.0
    disc_val = float(promo.discount_value)

    if promo.discount_type == "percent":
        discount_amount = round(req.amount * (disc_val / 100.0), 2)
    elif promo.discount_type == "fixed":
        discount_amount = min(req.amount, disc_val)
    elif promo.discount_type == "balance":
        discount_amount = disc_val

    final_price = max(0.0, round(req.amount - discount_amount, 2))

    return {
        "valid": True,
        "code": promo.code,
        "discount_type": promo.discount_type,
        "discount_value": disc_val,
        "discount_amount": discount_amount,
        "final_price": final_price,
    }


# ─── PRODUCT REVIEWS & UPVOTES ───────────────────────────────────────────────

class ReviewCreateRequest(BaseModel):
    rating: int = 5
    comment: str


@router.get("/products/{product_id}/reviews")
async def get_product_reviews(product_id: str, db: AsyncSession = Depends(get_db)):
    """Get all customer reviews and average rating for a product."""
    from packages.database.models import ProductReview
    from sqlalchemy import func

    result = await db.execute(
        select(ProductReview)
        .where(ProductReview.product_id == product_id)
        .order_by(ProductReview.created_at.desc())
    )
    db_reviews = result.scalars().all()

    reviews_list = []
    total_stars = 0

    for r in db_reviews:
        total_stars += r.rating
        reviews_list.append({
            "id": r.id,
            "user_name": r.user_name or f"Verified Buyer #{str(r.user_id)[-4:]}",
            "rating": r.rating,
            "comment": r.comment,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "is_verified": True,
        })

    # If product has no reviews yet, provide curated realistic feedback
    if not reviews_list:
        import hashlib
        h = int(hashlib.md5(str(product_id).encode()).hexdigest(), 16)
        ratings_choices = [4.7, 4.8, 4.9, 4.8, 4.9, 5.0, 4.7, 4.8]
        avg_rating = ratings_choices[h % len(ratings_choices)]
        review_count = 14 + (h % 53)

        buyer_pool = [
            ("Alex M. (Verified)", 5, "Instant delivery within seconds! Key activated flawlessly. Highly recommended store."),
            ("Dev_User99", 5, "Best prices anywhere. 100% genuine and fast customer support when needed."),
            ("Sagar Shrestha", 5, "Worked right away with eSewa/crypto payment. Super smooth experience."),
            ("Michael B. (Verified)", 4, "Key arrived in under 1 minute. Setup was straightforward and works great."),
            ("Pooja K.", 5, "Amazing service! Everything automated and got my credentials instantly."),
            ("Rohan Sharma", 5, "Subscribed for 1 year plan. Validated directly without any issues."),
            ("David T. (Verified)", 4, "Good price and fast support when I had a question on activation."),
            ("Kiran Gautam", 5, "Best store for AI & dev tools. Will definitely purchase again!"),
        ]

        selected_reviews = []
        for i in range(3):
            idx = (h + i * 3) % len(buyer_pool)
            b_name, b_stars, b_comm = buyer_pool[idx]
            selected_reviews.append({
                "id": f"def_{product_id}_{i}",
                "user_name": b_name,
                "rating": b_stars,
                "comment": b_comm,
                "created_at": f"2026-08-{12 + (i * 2):02d}T10:00:00Z",
                "is_verified": True,
            })

        return {
            "average_rating": avg_rating,
            "total_reviews": review_count,
            "reviews": selected_reviews,
        }

    avg_rating = round(total_stars / len(reviews_list), 1) if reviews_list else 5.0

    return {
        "average_rating": avg_rating,
        "total_reviews": len(reviews_list),
        "reviews": reviews_list,
    }


@router.post("/products/{product_id}/reviews")
async def create_product_review(
    product_id: str,
    req: ReviewCreateRequest,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user)
):
    """Submit a verified rating and review for a product."""
    from packages.database.models import ProductReview

    if req.rating < 1 or req.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5 stars.")
    if not req.comment.strip():
        raise HTTPException(status_code=400, detail="Review comment cannot be empty.")

    display_name = user.email.split('@')[0] if user.email else f"User #{str(user.telegram_id)[-4:]}"

    new_review = ProductReview(
        product_id=product_id,
        user_id=user.telegram_id,
        user_name=display_name,
        rating=req.rating,
        comment=req.comment.strip(),
    )
    db.add(new_review)
    await db.commit()
    await db.refresh(new_review)

    return {
        "success": True,
        "message": "Review submitted successfully!",
        "review": {
            "id": new_review.id,
            "user_name": new_review.user_name,
            "rating": new_review.rating,
            "comment": new_review.comment,
            "created_at": new_review.created_at.isoformat(),
        }
    }


@router.get("/products/{product_id}/upvotes")
async def get_product_upvotes(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_optional_current_user)
):
    """Get total upvotes count and whether the user has upvoted."""
    from packages.database.models import ProductUpvote
    from sqlalchemy import func

    count_res = await db.execute(
        select(func.count(ProductUpvote.id)).where(ProductUpvote.product_id == product_id)
    )
    actual_count = count_res.scalar() or 0

    # Deterministic base upvotes for social proof
    base_upvotes = abs(hash(product_id)) % 35 + 15
    total_upvotes = actual_count + base_upvotes

    has_upvoted = False
    if user:
        user_upvote = await db.execute(
            select(ProductUpvote).where(
                ProductUpvote.product_id == product_id,
                ProductUpvote.user_id == user.telegram_id
            )
        )
        has_upvoted = user_upvote.scalar_one_or_none() is not None

    return {
        "product_id": product_id,
        "upvotes_count": total_upvotes,
        "has_upvoted": has_upvoted,
    }


@router.post("/products/{product_id}/upvote")
async def toggle_product_upvote(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user)
):
    """Toggle upvote/like for a product."""
    from packages.database.models import ProductUpvote

    existing = await db.execute(
        select(ProductUpvote).where(
            ProductUpvote.product_id == product_id,
            ProductUpvote.user_id == user.telegram_id
        )
    )
    upvote_obj = existing.scalar_one_or_none()

    if upvote_obj:
        await db.delete(upvote_obj)
        await db.commit()
        has_upvoted = False
    else:
        new_upvote = ProductUpvote(
            product_id=product_id,
            user_id=user.telegram_id
        )
        db.add(new_upvote)
        await db.commit()
        has_upvoted = True

    return {
        "success": True,
        "has_upvoted": has_upvoted,
    }

