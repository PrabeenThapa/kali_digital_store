import re
from typing import Any
from sqlalchemy import func, select
from sqlalchemy import desc
from packages.database import Database
from packages.database.models import (
    Categories, Goods, User, BoughtGoods, ItemValues,
    ReferralEarnings, Operations
)
from packages.database.models.main import PromoCodes, Reviews


async def query_categories(offset: int = 0, limit: int = 10, count_only: bool = False) -> Any:
    """Query categories with pagination"""
    async with Database().session() as s:
        if count_only:
            return (await s.execute(select(func.count(Categories.id)))).scalar() or 0
        result = await s.execute(
            select(Categories.name)
            .order_by(Categories.name.asc())
            .offset(offset)
            .limit(limit)
        )
        return [row[0] for row in result.all()]


async def query_reseller_custom_categories() -> Any:
    """Query distinct custom categories set for reseller products"""
    from packages.database.models import ResellerProduct
    async with Database().session() as s:
        result = await s.execute(
            select(ResellerProduct.category_override)
            .where(ResellerProduct.category_override.isnot(None))
            .distinct()
        )
        return [row[0] for row in result.all()]


async def query_categories_with_stock(offset: int = 0, limit: int = 10, count_only: bool = False) -> Any:
    """
    Query categories with product count + total available stock codes.
    Used for user-facing browse screen and admin category lists.
    """
    if count_only:
        # We need the full union count. Easiest is to compute the full list.
        all_items = await _collect_all_products()
        dynamic_cats = {it.get("category") or "Other" for it in all_items}
        async with Database().session() as s:
            cat_result = await s.execute(select(Categories.name))
            db_cats = {r[0] for r in cat_result.all()}
        return len(dynamic_cats.union(db_cats))

    # Fetch all DB categories to ensure empty ones are shown
    async with Database().session() as s:
        cat_result = await s.execute(select(Categories.name, Categories.icon_custom_emoji_id, Categories.is_active))
        db_cats_data = {r.name: {"emoji": r.icon_custom_emoji_id, "is_active": r.is_active} for r in cat_result.all()}

    all_items = await _collect_all_products()
    
    # Initialize stats for DB cats
    stats = {cat: {"product_count": 0, "stock_codes": 0, "emoji": db_cats_data[cat]["emoji"], "is_active": db_cats_data[cat]["is_active"]} for cat in db_cats_data}
    
    # Process items and discover dynamic cats
    for it in all_items:
        cat = it.get("category") or "Other"
        if cat not in stats:
            stats[cat] = {"product_count": 0, "stock_codes": 0, "is_active": True}
        
        stats[cat]["product_count"] += 1
        if not it.get("is_infinity"):
            stock = it.get("stock") or 0
            stats[cat]["stock_codes"] += stock

    # Sort categories: DB ones first alphabetically, then dynamic ones alphabetically
    all_cats = sorted(stats.keys(), key=lambda c: (c == "Other", c.lower()))

    results = [
        {
            "name": cat,
            "product_count": stats[cat]["product_count"],
            "stock_codes": stats[cat]["stock_codes"],
            "icon_custom_emoji_id": stats[cat].get("emoji"),
            "is_active": stats[cat].get("is_active", True)
        }
        for cat in all_cats
    ]
    return results[offset: offset + limit]


async def query_all_goods_with_stock(offset: int = 0, limit: int = 10, count_only: bool = False) -> Any:
    """Query ALL goods across all categories with stock count — for admin product browser."""
    async with Database().session() as s:
        if count_only:
            return (await s.execute(select(func.count(Goods.id)))).scalar() or 0

        stock_sq = (
            select(ItemValues.item_id, func.count(ItemValues.id).label("stock"))
            .where(ItemValues.is_infinity == False)  # noqa: E712
            .group_by(ItemValues.item_id)
            .subquery()
        )
        inf_sq = (
            select(ItemValues.item_id)
            .where(ItemValues.is_infinity == True)  # noqa: E712
            .distinct()
            .subquery()
        )

        result = await s.execute(
            select(
                Goods.id,
                Goods.name,
                Goods.price,
                Categories.name.label("category"),
                func.coalesce(stock_sq.c.stock, 0).label("stock"),
                inf_sq.c.item_id.isnot(None).label("is_infinity"),
            )
            .outerjoin(stock_sq, stock_sq.c.item_id == Goods.id)
            .outerjoin(inf_sq, inf_sq.c.item_id == Goods.id)
            .join(Categories, Categories.id == Goods.category_id)
            .order_by(Categories.name.asc(), Goods.name.asc())
            .offset(offset)
            .limit(limit)
        )
        return [
            {
                "id": r.id,
                "name": r.name,
                "price": float(r.price),
                "category": r.category,
                "stock": r.stock,
                "is_infinity": bool(r.is_infinity),
                "source": "local",
            }
            for r in result.all()
        ]

async def query_admin_all_products_flat(offset: int = 0, limit: int = 10, count_only: bool = False) -> Any:
    """Flat paginated list of ALL products (local + reseller) for admin overview."""
    from packages.database.models.main import ResellerProduct
    async with Database().session() as s:
        # 1. Collect local goods
        stock_sq = (
            select(ItemValues.item_id, func.count(ItemValues.id).label("stock"))
            .where(ItemValues.is_infinity == False)  # noqa: E712
            .group_by(ItemValues.item_id)
            .subquery()
        )
        inf_sq = (
            select(ItemValues.item_id)
            .where(ItemValues.is_infinity == True)  # noqa: E712
            .distinct()
            .subquery()
        )
        
        local_q = (
            select(
                Goods.id, Goods.name, Goods.price, Goods.is_featured,
                func.coalesce(stock_sq.c.stock, 0).label("stock"),
                inf_sq.c.item_id.isnot(None).label("is_infinity")
            )
            .outerjoin(stock_sq, stock_sq.c.item_id == Goods.id)
            .outerjoin(inf_sq, inf_sq.c.item_id == Goods.id)
        )
        local_rows = (await s.execute(local_q)).all()
        
        local_items = [
            {
                "source": "local",
                "id": r.id,
                "name": r.name,
                "price": float(r.price),
                "stock": r.stock,
                "is_infinity": bool(r.is_infinity),
                "is_featured": bool(getattr(r, "is_featured", False)),
            }
            for r in local_rows
        ]
        
        # 2. Collect reseller products (even disabled ones, since this is for admins)
        reseller_rows = (await s.execute(select(ResellerProduct))).scalars().all()
        reseller_items = [
            {
                "source": "resell",
                "id": r.id,
                "name": r.name,
                "price": r.effective_sell_price,
                "stock": r.stock,
                "is_infinity": False,
                "is_featured": bool(getattr(r, "is_featured", False)),
                "is_enabled": r.is_enabled,
            }
            for r in reseller_rows
        ]
        
        # 3. Combine and sort
        all_items = local_items + reseller_items
        all_items.sort(key=lambda x: x["name"].lower())
        
        if count_only:
            return len(all_items)
            
        return all_items[offset:offset + limit]


async def query_items_in_category(category_name: str, offset: int = 0, limit: int = 10,
                                  count_only: bool = False, sort: str = "name") -> Any:
    """Query items in category with stock counts for color-coded display."""
    async with Database().session() as s:
        cat_id = (await s.execute(
            select(Categories.id).where(Categories.name == category_name)
        )).scalar()
        if not cat_id:
            return 0 if count_only else []

        if count_only:
            count_result = await s.execute(
                select(func.count(Goods.id)).where(Goods.category_id == cat_id)
            )
            return count_result.scalar() or 0

        # Stock subquery: count non-infinity values per item
        stock_sq = (
            select(ItemValues.item_id, func.count(ItemValues.id).label("stock"))
            .where(ItemValues.is_infinity == False)  # noqa: E712
            .group_by(ItemValues.item_id)
            .subquery()
        )
        # Infinity flag subquery
        inf_sq = (
            select(ItemValues.item_id)
            .where(ItemValues.is_infinity == True)  # noqa: E712
            .distinct()
            .subquery()
        )

        order_col = Goods.price.asc() if sort == "price" else Goods.name.asc()

        result = await s.execute(
            select(
                Goods.name,
                func.coalesce(stock_sq.c.stock, 0).label("stock"),
                inf_sq.c.item_id.isnot(None).label("is_infinity"),
                Goods.price,
            )
            .outerjoin(stock_sq, stock_sq.c.item_id == Goods.id)
            .outerjoin(inf_sq, inf_sq.c.item_id == Goods.id)
            .where(Goods.category_id == cat_id)
            .order_by(order_col)
            .offset(offset)
            .limit(limit)
        )
        rows = result.all()
        return [
            {
                "name": r.name,
                "stock": r.stock,
                "is_infinity": bool(r.is_infinity),
                "price": float(r.price),
            }
            for r in rows
        ]


async def query_user_bought_items(user_id: int, offset: int = 0, limit: int = 10, count_only: bool = False) -> Any:
    """Query user's bought items with pagination"""
    async with Database().session() as s:
        if count_only:
            return (await s.execute(
                select(func.count()).select_from(BoughtGoods).where(BoughtGoods.buyer_id == user_id)
            )).scalar() or 0
        result = await s.execute(
            select(BoughtGoods)
            .where(BoughtGoods.buyer_id == user_id)
            .order_by(desc(BoughtGoods.bought_datetime))
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()


async def query_all_users(offset: int = 0, limit: int = 10, count_only: bool = False) -> Any:
    """Query all users with pagination"""
    async with Database().session() as s:
        if count_only:
            return (await s.execute(select(func.count(User.telegram_id)))).scalar() or 0
        result = await s.execute(
            select(User.telegram_id)
            .order_by(User.telegram_id.asc())
            .offset(offset)
            .limit(limit)
        )
        return [row[0] for row in result.all()]


async def query_items_in_position(item_name: str, offset: int = 0, limit: int = 10, count_only: bool = False) -> Any:
    """Query items in position with pagination"""
    async with Database().session() as s:
        item_id = (await s.execute(
            select(Goods.id).where(Goods.name == item_name)
        )).scalar()
        if not item_id:
            return 0 if count_only else []
        query = select(ItemValues.id).where(ItemValues.item_id == item_id)
        if count_only:
            count_result = await s.execute(select(func.count()).select_from(query.subquery()))
            return count_result.scalar() or 0
        result = await s.execute(
            query.order_by(ItemValues.id.asc()).offset(offset).limit(limit)
        )
        return [row[0] for row in result.all()]


async def query_user_referrals(user_id: int, offset: int = 0, limit: int = 10, count_only: bool = False) -> Any:
    """Query user's referrals with earnings info"""
    async with Database().session() as s:
        if count_only:
            return (await s.execute(
                select(func.count(User.telegram_id)).where(User.referral_id == user_id)
            )).scalar() or 0

        earnings_subq = (
            select(
                ReferralEarnings.referral_id,
                func.coalesce(func.sum(ReferralEarnings.amount), 0).label('total_earned')
            )
            .where(ReferralEarnings.referrer_id == user_id)
            .group_by(ReferralEarnings.referral_id)
            .subquery()
        )

        stmt = (
            select(
                User.telegram_id,
                User.registration_date,
                func.coalesce(earnings_subq.c.total_earned, 0).label('total_earned')
            )
            .outerjoin(earnings_subq, User.telegram_id == earnings_subq.c.referral_id)
            .where(User.referral_id == user_id)
            .order_by(desc(func.coalesce(earnings_subq.c.total_earned, 0)))
            .offset(offset)
            .limit(limit)
        )
        rows = (await s.execute(stmt)).all()

        return [
            {
                'telegram_id': row.telegram_id,
                'registration_date': row.registration_date,
                'total_earned': row.total_earned
            }
            for row in rows
        ]


async def query_referral_earnings_from_user(referrer_id: int, referral_id: int, offset: int = 0, limit: int = 10,
                                            count_only: bool = False) -> Any:
    """Query earnings from specific referral"""
    async with Database().session() as s:
        base = select(ReferralEarnings).where(
            ReferralEarnings.referrer_id == referrer_id,
            ReferralEarnings.referral_id == referral_id
        )
        if count_only:
            count_result = await s.execute(select(func.count()).select_from(base.subquery()))
            return count_result.scalar() or 0
        result = await s.execute(
            base.order_by(desc(ReferralEarnings.created_at)).offset(offset).limit(limit)
        )
        return result.scalars().all()


async def query_all_referral_earnings(referrer_id: int, offset: int = 0, limit: int = 10,
                                      count_only: bool = False) -> Any:
    """Query all referral earnings for user"""
    async with Database().session() as s:
        base = select(ReferralEarnings).where(
            ReferralEarnings.referrer_id == referrer_id
        )
        if count_only:
            count_result = await s.execute(select(func.count()).select_from(base.subquery()))
            return count_result.scalar() or 0
        result = await s.execute(
            base.order_by(desc(ReferralEarnings.created_at)).offset(offset).limit(limit)
        )
        return result.scalars().all()


async def query_promo_codes(offset: int = 0, limit: int = 10, count_only: bool = False) -> Any:
    """Query promo codes with pagination"""
    async with Database().session() as s:
        if count_only:
            return (await s.execute(select(func.count(PromoCodes.id)))).scalar() or 0
        result = await s.execute(
            select(PromoCodes)
            .order_by(desc(PromoCodes.created_at))
            .offset(offset)
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                'id': p.id, 'code': p.code, 'discount_type': p.discount_type,
                'discount_value': p.discount_value, 'max_uses': p.max_uses,
                'current_uses': p.current_uses, 'is_active': p.is_active,
                'expires_at': p.expires_at, 'created_at': p.created_at,
            }
            for p in rows
        ]



async def query_user_operations_history(user_id: int, offset: int = 0, limit: int = 10,
                                        count_only: bool = False) -> Any:
    """Query user's full operations history (topups, purchases, referral bonuses) as UNION ALL"""
    from sqlalchemy import union_all, literal
    async with Database().session() as s:
        # 1. Top-ups (operations with positive value)
        topups = (
            select(
                Operations.id,
                literal('topup').label('type'),
                Operations.operation_value.label('amount'),
                Operations.operation_time.label('date'),
            )
            .where(Operations.user_id == user_id, Operations.operation_value > 0)
        )
        # 2. Purchases
        purchases = (
            select(
                BoughtGoods.id,
                literal('purchase').label('type'),
                (-BoughtGoods.price).label('amount'),
                BoughtGoods.bought_datetime.label('date'),
            )
            .where(BoughtGoods.buyer_id == user_id)
        )
        # 3. Referral earnings
        referrals = (
            select(
                ReferralEarnings.id,
                literal('referral').label('type'),
                ReferralEarnings.amount.label('amount'),
                ReferralEarnings.created_at.label('date'),
            )
            .where(ReferralEarnings.referrer_id == user_id)
        )

        combined = union_all(topups, purchases, referrals).subquery()

        if count_only:
            return (await s.execute(select(func.count()).select_from(combined))).scalar() or 0

        result = await s.execute(
            select(combined).order_by(combined.c.date.desc()).offset(offset).limit(limit)
        )
        return [
            {
                'id': row.id,
                'type': row.type,
                'amount': row.amount,
                'date': row.date,
            }
            for row in result.all()
        ]


async def query_item_reviews(item_name: str, offset: int = 0, limit: int = 10,
                             count_only: bool = False) -> Any:
    """Query reviews for an item with pagination"""
    async with Database().session() as s:
        base = select(Reviews).where(Reviews.item_name == item_name)
        if count_only:
            count_q = select(func.count()).select_from(base.subquery())
            return (await s.execute(count_q)).scalar() or 0
        result = await s.execute(
            base.order_by(desc(Reviews.created_at)).offset(offset).limit(limit)
        )
        return [
            {
                'id': r.id, 'user_id': r.user_id, 'rating': r.rating,
                'text': r.text, 'created_at': r.created_at,
            }
            for r in result.scalars().all()
        ]


async def _collect_all_products(source_filter: str = None) -> list[dict]:
    """
    Build the merged list of all purchasable products (local goods + reseller),
    each with a resolved `category`. Shared by the flat list and category menu.

    Each item dict:
      name, price (USD float), stock (int | None), is_infinity (bool),
      source ("local" | "forkpixel" | "cgpt" | "safwan"), product_type,
      external_id, category
    """
    from packages.database.models.main import ResellerProduct, ResellerSource
    from apps.telegram_bot.utils.category_resolver import resolve_category

    async with Database().session() as s:
        # ── Local goods (with category name via FK) ────────────
        stock_sq = (
            select(ItemValues.item_id, func.count(ItemValues.id).label("stock"))
            .where(ItemValues.is_infinity == False)  # noqa: E712
            .group_by(ItemValues.item_id)
            .subquery()
        )
        inf_sq = (
            select(ItemValues.item_id)
            .where(ItemValues.is_infinity == True)  # noqa: E712
            .distinct()
            .subquery()
        )

        local_q = (
            select(
                Goods.name,
                Goods.price,
                func.coalesce(stock_sq.c.stock, 0).label("stock"),
                inf_sq.c.item_id.isnot(None).label("is_infinity"),
                Categories.name.label("category_name"),
                Goods.icon_custom_emoji_id,
                Categories.icon_custom_emoji_id.label("cat_emoji")
            )
            .outerjoin(stock_sq, stock_sq.c.item_id == Goods.id)
            .outerjoin(inf_sq, inf_sq.c.item_id == Goods.id)
            .outerjoin(Categories, Categories.id == Goods.category_id)
        )
        local_rows = (await s.execute(local_q)).all()
        
        cat_rows = (await s.execute(select(Categories.original_name, Categories.name, Categories.icon_custom_emoji_id))).all()
        orig_to_name = {r.original_name: r.name for r in cat_rows if r.original_name}
        name_to_emoji = {}
        import re
        for r in cat_rows:
            if r.name:
                name_to_emoji[r.name] = r.icon_custom_emoji_id
                clean = re.sub(r'^[^\w\s]+', '', r.name).strip()
                if clean and clean not in name_to_emoji:
                    name_to_emoji[clean] = r.icon_custom_emoji_id

        def _resolve_cat(orig: str) -> str:
            return orig_to_name.get(orig, orig)

        # Categorize local products by their actual category name if it exists,
        # otherwise fallback to resolve_category.
        local_items = [
            {
                "name": r.name,
                "price": float(r.price),
                "stock": r.stock,
                "is_infinity": bool(r.is_infinity),
                "source": "local",
                "product_type": "account",
                "external_id": None,
                "category": r.category_name or _resolve_cat(resolve_category(r.name)),
                "icon_custom_emoji_id": r.icon_custom_emoji_id or r.cat_emoji,
            }
            for r in local_rows
        ]

        # ── Reseller products ──────────────────────────────────
        reseller_q = (
            select(ResellerProduct)
            .where(ResellerProduct.is_enabled == True)  # noqa: E712
        )
        if source_filter:
            reseller_q = reseller_q.join(
                ResellerSource, ResellerSource.id == ResellerProduct.source_id
            ).where(ResellerSource.name == source_filter)

        reseller_rows = (await s.execute(reseller_q)).scalars().all()
        reseller_items = [
            {
                "name": r.effective_name,
                "price": r.effective_sell_price,
                "stock": r.stock,
                "is_infinity": False,
                "source": None,   # filled below
                "product_type": r.product_type,
                "external_id": r.external_id,
                "reseller_product_id": r.id,
                "source_id": r.source_id,
                "category": r.effective_category,
                "icon_custom_emoji_id": r.icon_custom_emoji_id or name_to_emoji.get(r.effective_category),
            }
            for r in reseller_rows
        ]

        # Resolve source names for reseller items
        source_id_to_name: dict[int, str] = {}
        if reseller_items:
            src_rows = (await s.execute(select(ResellerSource.id, ResellerSource.name))).all()
            source_id_to_name = {r.id: r.name for r in src_rows}
        for item in reseller_items:
            item["source"] = source_id_to_name.get(item.pop("source_id", 0), "reseller")

    return local_items + reseller_items


async def query_all_products_flat(
    offset: int = 0, limit: int = 10, count_only: bool = False,
    sort: str = "price", source_filter: str = None, category: str = None,
    search_name: str = None,
) -> Any:
    """
    Flat paginated list of ALL purchasable products — local goods + reseller products.
    Optionally filtered to a single `category` or by `search_name` (substring match).
    """
    all_items = await _collect_all_products(source_filter=source_filter)

    def _avail_key(item: dict) -> int:
        if item.get("is_infinity"):
            return 0
        ptype = item.get("product_type", "")
        stock = item.get("stock") or 0
        if stock > 0:
            return 0
        if ptype in ("preorder", "team_invite"):
            return 1
        return 2

    # Filter out items that are out of stock
    all_items = [it for it in all_items if _avail_key(it) != 2]

    if category:
        all_items = [it for it in all_items if it.get("category") == category]

    if search_name:
        needle = search_name.lower()
        all_items = [it for it in all_items if needle in it["name"].lower()]

    if sort == "price":
        all_items.sort(key=lambda x: x["price"])
    else:
        all_items.sort(key=lambda x: x["name"].lower())

    # Sort by availability: in-stock first, then preorder

    all_items.sort(key=_avail_key)

    if count_only:
        return len(all_items)

    return all_items[offset: offset + limit]


async def query_product_categories(include_disabled: bool = False) -> list[tuple[str, int, float, str]]:
    """
    Return [(category_label, product_count, min_price, icon_custom_emoji_id)] for all purchasable products,
    sorted with 'Other' last. Used to build the shop category menu.
    """
    all_items = await _collect_all_products()
    
    # Query category custom emojis and active status directly from DB
    cat_emoji_map = {}
    disabled_cats = set()
    async with Database().session() as s:
        c_rows = (await s.execute(select(Categories.name, Categories.icon_custom_emoji_id, Categories.is_active))).all()
        for r in c_rows:
            if r.name:
                if not r.is_active:
                    disabled_cats.add(r.name)
                cat_emoji_map[r.name] = r.icon_custom_emoji_id
                clean = re.sub(r'^[^\w\s]+', '', r.name).strip()
                if clean and clean not in cat_emoji_map:
                    cat_emoji_map[clean] = r.icon_custom_emoji_id
                    if not r.is_active:
                        disabled_cats.add(clean)

    def _avail_key(item: dict) -> int:
        if item.get("is_infinity"):
            return 0
        ptype = item.get("product_type", "")
        stock = item.get("stock") or 0
        if stock > 0:
            return 0
        if ptype in ("preorder", "team_invite"):
            return 1
        return 2

    # Filter out out of stock items and items from disabled categories
    if not include_disabled:
        all_items = [it for it in all_items if _avail_key(it) != 2 and (it.get("category") or "Other") not in disabled_cats]
    else:
        all_items = [it for it in all_items if _avail_key(it) != 2]

    stats: dict[str, dict] = {}
    for it in all_items:
        cat = it.get("category") or "Other"
        if cat not in stats:
            # Prioritize category's own custom emoji, fallback to item's custom emoji
            cat_emoji = cat_emoji_map.get(cat) or it.get("icon_custom_emoji_id")
            stats[cat] = {"count": 0, "min_price": float('inf'), "emoji": cat_emoji, "stock": 0, "is_inf": False}
        
        if not stats[cat]["emoji"] and it.get("icon_custom_emoji_id"):
            stats[cat]["emoji"] = it.get("icon_custom_emoji_id")

        stats[cat]["count"] += 1
        price = it.get("price") or 0.0
        if price < stats[cat]["min_price"]:
            stats[cat]["min_price"] = price
            
        stock = it.get("stock")
        if it.get("is_infinity") or stock is None:
            stats[cat]["is_inf"] = True
        elif stock > 0:
            stats[cat]["stock"] += stock

    def _sort_key(pair: tuple[str, int, float, str]):
        label = pair[0]
        return (label == "Other", label.lower())

    results = [(k, v["count"], v["min_price"] if v["min_price"] != float('inf') else 0.0, v["emoji"]) for k, v in stats.items()]
    return sorted(results, key=_sort_key)


async def query_featured_items() -> list[dict]:
    """
    Return featured products from both local goods and reseller products.
    Each item has: name, price, stock, is_infinity, source, category, icon_custom_emoji_id.
    """
    from packages.database.models.main import ResellerProduct, Categories

    featured = []

    async with Database().session() as s:
        cat_rows = (await s.execute(select(Categories.original_name, Categories.name, Categories.icon_custom_emoji_id))).all()
        name_to_emoji = {}
        for r in cat_rows:
            if r.name:
                name_to_emoji[r.name] = r.icon_custom_emoji_id
                clean = re.sub(r'^[^\w\s]+', '', r.name).strip()
                if clean and clean not in name_to_emoji:
                    name_to_emoji[clean] = r.icon_custom_emoji_id

        # Local featured goods
        stock_sq = (
            select(ItemValues.item_id, func.count(ItemValues.id).label("stock"))
            .where(ItemValues.is_infinity == False)  # noqa: E712
            .group_by(ItemValues.item_id)
            .subquery()
        )
        inf_sq = (
            select(ItemValues.item_id)
            .where(ItemValues.is_infinity == True)  # noqa: E712
            .distinct()
            .subquery()
        )
        local_q = (
            select(
                Goods.name,
                Goods.price,
                func.coalesce(stock_sq.c.stock, 0).label("stock"),
                inf_sq.c.item_id.isnot(None).label("is_infinity"),
                Categories.name.label("category_name"),
                Goods.icon_custom_emoji_id,
                Categories.icon_custom_emoji_id.label("cat_emoji"),
            )
            .outerjoin(stock_sq, stock_sq.c.item_id == Goods.id)
            .outerjoin(inf_sq, inf_sq.c.item_id == Goods.id)
            .outerjoin(Categories, Categories.id == Goods.category_id)
            .where(Goods.is_featured == True)  # noqa: E712
        )
        for r in (await s.execute(local_q)).all():
            stock = r.stock if not r.is_infinity else None
            cat_name = r.category_name or resolve_category(r.name)
            emoji_id = r.icon_custom_emoji_id or r.cat_emoji or name_to_emoji.get(cat_name)
            featured.append({
                "name": r.name,
                "price": float(r.price),
                "stock": stock,
                "is_infinity": bool(r.is_infinity),
                "source": "local",
                "category": cat_name,
                "icon_custom_emoji_id": emoji_id,
            })

        # Reseller featured products
        reseller_q = (
            select(ResellerProduct)
            .where(ResellerProduct.is_featured == True)  # noqa: E712
            .where(ResellerProduct.is_enabled == True)  # noqa: E712
        )
        for r in (await s.execute(reseller_q)).scalars().all():
            cat_name = r.effective_category
            emoji_id = r.icon_custom_emoji_id or name_to_emoji.get(cat_name)
            featured.append({
                "name": r.effective_name,
                "price": r.effective_sell_price,
                "stock": r.stock,
                "is_infinity": False,
                "source": "reseller",
                "category": cat_name,
                "icon_custom_emoji_id": emoji_id,
            })

    return featured
