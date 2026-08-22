"""
Reseller product sync service.

Fetches products from ForkPixel and CGPT APIs, upserts them into
the `reseller_products` table. Respects admin overrides: sell_price
and is_enabled are ONLY set on first insert, never overwritten on update.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update

from packages.config.config import EnvKeys
from packages.database.engine import Database
from packages.database.models.main import ResellerSource, ResellerProduct
from packages.services.pricing import calculate_sell_price

from .client import ForkPixelClient, CGPTClient, SafwanTigerClient, CanbosoClient, GGSomaClient

_log = logging.getLogger(__name__)
_source_locks: dict[int, asyncio.Lock] = {}


class ResellerSyncError(RuntimeError):
    """Raised when one reseller source cannot be synchronized."""


def _external_id(value: object) -> str:
    """Normalize API identifiers without turning ``None`` into a real ID."""
    return "" if value is None else str(value).strip()


async def _mark_source_synced(session, source_id: int, synced_at: datetime) -> None:
    """Persist sync status in the same transaction as the product changes."""
    await session.execute(
        update(ResellerSource)
        .where(ResellerSource.id == source_id)
        .values(last_synced=synced_at)
    )


async def ensure_sources_exist() -> None:
    """
    Insert ForkPixel and CGPT sources into `reseller_sources` if missing.
    Called once at startup before the first sync.
    """
    sources_to_ensure = []

    if EnvKeys.FORKPIXEL_API_KEY:
        sources_to_ensure.append({
            "name": "forkpixel",
            "base_url": EnvKeys.FORKPIXEL_BASE_URL,
            "api_key": EnvKeys.FORKPIXEL_API_KEY,
        })

    if EnvKeys.CGPT_API_KEY:
        sources_to_ensure.append({
            "name": "cgpt",
            "base_url": EnvKeys.CGPT_BASE_URL,
            "api_key": EnvKeys.CGPT_API_KEY,
        })

    if EnvKeys.SAFWAN_API_KEY:
        sources_to_ensure.append({
            "name": "safwan",
            "base_url": EnvKeys.SAFWAN_BASE_URL,
            "api_key": EnvKeys.SAFWAN_API_KEY,
        })

    if EnvKeys.CANBOSO_API_KEY:
        sources_to_ensure.append({
            "name": "canboso",
            "base_url": EnvKeys.CANBOSO_BASE_URL,
            "api_key": EnvKeys.CANBOSO_API_KEY,
        })

    if EnvKeys.GGSOMA_API_KEY:
        sources_to_ensure.append({
            "name": "ggsoma",
            "base_url": EnvKeys.GGSOMA_BASE_URL,
            "api_key": EnvKeys.GGSOMA_API_KEY,
        })

    if not sources_to_ensure:
        _log.info("No reseller API keys configured — skipping source setup.")
        return

    async with Database().session() as s:
        active_names = set()
        for src in sources_to_ensure:
            active_names.add(src["name"])
            existing = (await s.execute(
                select(ResellerSource).where(ResellerSource.name == src["name"])
            )).scalars().first()

            if existing:
                existing.is_active = True
                if src.get("api_key") and src["api_key"].strip():
                    existing.api_key = src["api_key"]
                if src.get("base_url") and src["base_url"].strip():
                    existing.base_url = src["base_url"]
            else:
                s.add(ResellerSource(
                    name=src["name"],
                    base_url=src["base_url"],
                    api_key=src["api_key"],
                    is_active=True,
                ))

        # Ensure any removed/unconfigured sources are disabled
        all_sources = (await s.execute(select(ResellerSource))).scalars().all()
        for src_obj in all_sources:
            if src_obj.name not in active_names:
                src_obj.is_active = False
                # Disable products from deactivated sources
                await s.execute(
                    update(ResellerProduct)
                    .where(ResellerProduct.source_id == src_obj.id)
                    .values(is_enabled=False, stock=0)
                )

        await s.commit()
    _log.info("Reseller sources ensured: %s", [s["name"] for s in sources_to_ensure])


async def _sync_forkpixel(source: ResellerSource) -> dict:
    """Sync ForkPixel products. Returns count of upserted rows."""
    client = ForkPixelClient(
        api_key=source.api_key,
        base_url=source.base_url,
        currency=EnvKeys.FORKPIXEL_CURRENCY,
    )
    products = await client.get_products()

    markup = float(EnvKeys.RESELLER_MARKUP_PERCENT)
    upserted = 0
    new_products = []
    added_stock = []
    now = datetime.now(timezone.utc)

    async with Database().session() as s:
        seen_ext_ids = set()
        for p in products:
            ext_id = _external_id(p.get("productId") or p.get("id"))
            name = str(p.get("name") or p.get("title") or "").strip()
            product_type = p.get("productType", "account")
            cost_usd = float(p.get("priceUsd") or (p.get("price", 0) / 25000))
            code = p.get("code")
            stock_raw = p.get("stock")
            stock = None if stock_raw == "preorder" else (stock_raw if isinstance(stock_raw, int) else None)
            description = p.get("category", "")

            if not ext_id or not name:
                continue

            # Strict filter: Only import Pixel Verify products from LahaStore / ForkPixel
            if "pixel" not in name.lower():
                continue

            existing = (await s.execute(
                select(ResellerProduct).where(
                    ResellerProduct.source_id == source.id,
                    ResellerProduct.external_id == ext_id,
                )
            )).scalars().first()

            if existing:
                old_stock = existing.stock or 0
                new_stock_val = stock or 0
                if new_stock_val > old_stock:
                    added_stock.append({
                        "name": name,
                        "added": new_stock_val - old_stock,
                        "current_stock": new_stock_val,
                        "price": calculate_sell_price(cost_usd, markup),
                        "source": "ForkPixel"
                    })
                # Update only non-admin fields
                existing.name = name
                existing.cost_price = cost_usd
                existing.product_type = product_type
                existing.external_code = code
                existing.stock = stock
                existing.description = description
                existing.last_synced = now
            else:
                new_stock_val = stock or 0
                if new_stock_val > 0:
                    added_stock.append({
                        "name": name,
                        "added": new_stock_val,
                        "current_stock": new_stock_val,
                        "price": calculate_sell_price(cost_usd, markup),
                        "source": "ForkPixel"
                    })
                s.add(ResellerProduct(
                    source_id=source.id,
                    external_id=ext_id,
                    external_code=code,
                    name=name,
                    description=description,
                    product_type=product_type,
                    cost_price=cost_usd,
                    markup_percent=markup,
                    stock=stock,
                    last_synced=now,
                ))
                new_products.append({"name": name, "price": calculate_sell_price(cost_usd, markup), "source": "ForkPixel"})
            upserted += 1
            seen_ext_ids.add(ext_id)

        if seen_ext_ids:
            await s.execute(
                update(ResellerProduct)
                .where(
                    ResellerProduct.source_id == source.id,
                    ResellerProduct.external_id.not_in(seen_ext_ids)
                )
                .values(stock=0, last_synced=now)
            )

        # Ensure any non-pixel items in the database from ForkPixel are zeroed out and disabled
        await s.execute(
            update(ResellerProduct)
            .where(
                ResellerProduct.source_id == source.id,
                ResellerProduct.name.not_ilike("%pixel%")
            )
            .values(stock=0, is_enabled=False, last_synced=now)
        )

        await _mark_source_synced(s, source.id, now)

    _log.info("ForkPixel (Pixel Verify Only) sync complete: %d products upserted.", upserted)
    return {"upserted": upserted, "new_products": new_products, "added_stock": added_stock}


async def _sync_cgpt(source: ResellerSource) -> dict:
    """Sync CGPT products. Returns count of upserted rows."""
    client = CGPTClient(api_key=source.api_key, base_url=source.base_url)
    products = await client.get_products()

    markup = float(EnvKeys.RESELLER_MARKUP_PERCENT)
    upserted = 0
    new_products = []
    added_stock = []
    now = datetime.now(timezone.utc)

    async with Database().session() as s:
        seen_ext_ids = set()
        for p in products:
            ext_id = _external_id(p.get("id"))
            name = str(p.get("name") or "").strip()
            product_type = p.get("product_type", "stock")
            cost_usd = float(p.get("your_unit_price", 0))
            code = None
            stock = p.get("stock")
            if isinstance(stock, str) and stock.isdigit():
                stock = int(stock)
            elif not isinstance(stock, int):
                stock = None
            description = p.get("description") or ""

            if not ext_id or not name:
                continue

            existing = (await s.execute(
                select(ResellerProduct).where(
                    ResellerProduct.source_id == source.id,
                    ResellerProduct.external_id == ext_id,
                )
            )).scalars().first()

            if existing:
                old_stock = existing.stock or 0
                new_stock_val = stock or 0
                if new_stock_val > old_stock:
                    added_stock.append({
                        "name": name,
                        "added": new_stock_val - old_stock,
                        "current_stock": new_stock_val,
                        "price": calculate_sell_price(cost_usd, markup),
                        "source": "CGPT"
                    })
                existing.name = name
                existing.cost_price = cost_usd
                existing.product_type = product_type
                existing.external_code = code
                existing.stock = stock
                existing.description = description
                existing.last_synced = now
            else:
                new_stock_val = stock or 0
                if new_stock_val > 0:
                    added_stock.append({
                        "name": name,
                        "added": new_stock_val,
                        "current_stock": new_stock_val,
                        "price": calculate_sell_price(cost_usd, markup),
                        "source": "CGPT"
                    })
                s.add(ResellerProduct(
                    source_id=source.id,
                    external_id=ext_id,
                    external_code=code,
                    name=name,
                    description=description,
                    product_type=product_type,
                    cost_price=cost_usd,
                    markup_percent=markup,
                    stock=stock,
                    last_synced=now,
                ))
                new_products.append({"name": name, "price": calculate_sell_price(cost_usd, markup), "source": "CGPT"})
            upserted += 1
            seen_ext_ids.add(ext_id)

        if seen_ext_ids:
            await s.execute(
                update(ResellerProduct)
                .where(
                    ResellerProduct.source_id == source.id,
                    ResellerProduct.external_id.not_in(seen_ext_ids)
                )
                .values(stock=0, last_synced=now)
            )

        await _mark_source_synced(s, source.id, now)

    _log.info("CGPT sync complete: %d products upserted.", upserted)
    return {"upserted": upserted, "new_products": new_products, "added_stock": added_stock}


async def _sync_safwan(source: ResellerSource) -> dict:
    """Sync SafwanTiger products. Returns count of upserted rows."""
    client = SafwanTigerClient(api_key=source.api_key, base_url=source.base_url)
    products = await client.get_products()

    markup = float(EnvKeys.RESELLER_MARKUP_PERCENT)
    upserted = 0
    new_products = []
    added_stock = []
    now = datetime.now(timezone.utc)

    async with Database().session() as s:
        seen_ext_ids = set()
        for p in products:
            ext_id = _external_id(p.get("id"))
            name = str(p.get("name") or "").strip()
            cost_usd = float(p.get("price", 0))
            unlimited = bool(p.get("unlimited_stock"))
            stock_raw = p.get("stock")
            stock = None if unlimited else (stock_raw if isinstance(stock_raw, int) else None)
            # Unlimited items are "account" (instant); limited-stock items are "stock" (instant)
            product_type = "account"
            description = p.get("description") or ""
            # Warranty info appended to description for the buyer
            warranty = p.get("warranty")
            if warranty and warranty != "NON":
                description = f"{description}\n\n🛡 Warranty: {warranty}"

            if not ext_id or not name:
                continue

            existing = (await s.execute(
                select(ResellerProduct).where(
                    ResellerProduct.source_id == source.id,
                    ResellerProduct.external_id == ext_id,
                )
            )).scalars().first()

            if existing:
                old_stock = existing.stock or 0
                new_stock_val = stock or 0
                if new_stock_val > old_stock:
                    added_stock.append({
                        "name": name,
                        "added": new_stock_val - old_stock,
                        "current_stock": new_stock_val,
                        "price": calculate_sell_price(cost_usd, markup),
                        "source": "SafwanTiger"
                    })
                existing.name = name
                existing.cost_price = cost_usd
                existing.product_type = product_type
                existing.stock = stock
                existing.description = description
                existing.last_synced = now
            else:
                new_stock_val = stock or 0
                if new_stock_val > 0:
                    added_stock.append({
                        "name": name,
                        "added": new_stock_val,
                        "current_stock": new_stock_val,
                        "price": calculate_sell_price(cost_usd, markup),
                        "source": "SafwanTiger"
                    })
                s.add(ResellerProduct(
                    source_id=source.id,
                    external_id=ext_id,
                    name=name,
                    description=description,
                    product_type=product_type,
                    cost_price=cost_usd,
                    markup_percent=markup,
                    stock=stock,
                    last_synced=now,
                ))
                new_products.append({"name": name, "price": calculate_sell_price(cost_usd, markup), "source": "SafwanTiger"})
            upserted += 1
            seen_ext_ids.add(ext_id)

        if seen_ext_ids:
            await s.execute(
                update(ResellerProduct)
                .where(
                    ResellerProduct.source_id == source.id,
                    ResellerProduct.external_id.not_in(seen_ext_ids)
                )
                .values(stock=0, last_synced=now)
            )

        await _mark_source_synced(s, source.id, now)

    _log.info("SafwanTiger sync complete: %d products upserted.", upserted)
    return {"upserted": upserted, "new_products": new_products, "added_stock": added_stock}


async def _sync_canboso(source: ResellerSource) -> dict:
    """Sync Canboso products. Returns count of upserted rows."""
    client = CanbosoClient(api_key=source.api_key, base_url=source.base_url)
    products = await client.get_products()

    markup = float(EnvKeys.RESELLER_MARKUP_PERCENT)
    upserted = 0
    new_products = []
    added_stock = []
    now = datetime.now(timezone.utc)

    async with Database().session() as s:
        seen_ext_ids = set()
        for p in products:
            # Canboso Buyer API (v2 & v1 fallback schema)
            ext_id = _external_id(p.get("productId") or p.get("_id"))
            name = str(p.get("name") or p.get("product_name") or "").strip()
            price_obj = p.get("price")
            if isinstance(price_obj, dict):
                cost_usd = float(price_obj.get("amount") or 0)
            else:
                cost_usd = float(p.get("usdPricing") or 0)

            avail_obj = p.get("availability")
            if isinstance(avail_obj, dict):
                available = avail_obj.get("available")
            else:
                stats = p.get("stats") or {}
                available = stats.get("available")

            stock = available if isinstance(available, int) else None
            product_type = p.get("productType") or ("preorder" if p.get("isSlotProduct") else "account")
            description = p.get("description") or ""

            if not ext_id or not name:
                continue

            existing = (await s.execute(
                select(ResellerProduct).where(
                    ResellerProduct.source_id == source.id,
                    ResellerProduct.external_id == ext_id,
                )
            )).scalars().first()

            if existing:
                old_stock = existing.stock or 0
                new_stock_val = stock or 0
                if new_stock_val > old_stock:
                    added_stock.append({
                        "name": name,
                        "added": new_stock_val - old_stock,
                        "current_stock": new_stock_val,
                        "price": calculate_sell_price(cost_usd, markup),
                        "source": "Canboso"
                    })
                existing.name = name
                existing.cost_price = cost_usd
                existing.product_type = product_type
                existing.stock = stock
                existing.description = description
                existing.last_synced = now
            else:
                new_stock_val = stock or 0
                if new_stock_val > 0:
                    added_stock.append({
                        "name": name,
                        "added": new_stock_val,
                        "current_stock": new_stock_val,
                        "price": calculate_sell_price(cost_usd, markup),
                        "source": "Canboso"
                    })
                s.add(ResellerProduct(
                    source_id=source.id,
                    external_id=ext_id,
                    name=name,
                    description=description,
                    product_type=product_type,
                    cost_price=cost_usd,
                    markup_percent=markup,
                    stock=stock,
                    last_synced=now,
                ))
                new_products.append({"name": name, "price": calculate_sell_price(cost_usd, markup), "source": "Canboso"})
            upserted += 1
            seen_ext_ids.add(ext_id)

        if seen_ext_ids:
            await s.execute(
                update(ResellerProduct)
                .where(
                    ResellerProduct.source_id == source.id,
                    ResellerProduct.external_id.not_in(seen_ext_ids)
                )
                .values(stock=0, last_synced=now)
            )

        await _mark_source_synced(s, source.id, now)

    _log.info("Canboso sync complete: %d products upserted.", upserted)
    return {"upserted": upserted, "new_products": new_products, "added_stock": added_stock}


async def _sync_ggsoma(source: ResellerSource) -> dict:
    """Sync GGSOMA products. Returns dict with upserted count, new products, and added stock."""
    client = GGSomaClient(api_key=source.api_key, base_url=source.base_url)
    products = await client.get_products()

    markup = float(EnvKeys.RESELLER_MARKUP_PERCENT)
    upserted = 0
    new_products = []
    added_stock = []
    now = datetime.now(timezone.utc)

    async with Database().session() as s:
        seen_ext_ids = set()
        for p in products:
            ext_id = _external_id(p.get("id"))
            name = str(p.get("name") or "").strip()
            pricing = p.get("pricing") or {}
            cost_usd = float(pricing.get("yourUnitPrice") or p.get("yourPrice") or p.get("catalogPrice") or 0)

            stock_info = p.get("stock") or {}
            stock_count = stock_info.get("count")
            stock = stock_count if isinstance(stock_count, int) else None

            flags = p.get("flags") or {}
            is_instant = flags.get("instantDelivery", True)
            product_type = "account" if is_instant else "preorder"
            description = p.get("description") or ""

            if not ext_id or not name:
                continue

            seen_ext_ids.add(ext_id)
            existing = (await s.execute(
                select(ResellerProduct).where(
                    ResellerProduct.source_id == source.id,
                    ResellerProduct.external_id == ext_id,
                )
            )).scalars().first()

            if existing:
                old_stock = existing.stock or 0
                new_stock_val = stock or 0
                if new_stock_val > old_stock:
                    added_stock.append({
                        "name": name,
                        "added": new_stock_val - old_stock,
                        "current_stock": new_stock_val,
                        "price": calculate_sell_price(cost_usd, markup),
                        "source": "GGSOMA"
                    })
                existing.name = name
                existing.cost_price = cost_usd
                existing.product_type = product_type
                existing.stock = stock
                existing.last_synced = now

                computed_sell = calculate_sell_price(cost_usd, markup)
                existing.markup_percent = markup
                existing.sell_price = computed_sell
            else:
                sell = calculate_sell_price(cost_usd, markup)
                new_prod = ResellerProduct(
                    source_id=source.id,
                    external_id=ext_id,
                    name=name,
                    cost_price=cost_usd,
                    sell_price=sell,
                    markup_percent=markup,
                    product_type=product_type,
                    stock=stock,
                    is_enabled=True,
                    last_synced=now,
                )
                s.add(new_prod)
                new_products.append({"name": name, "price": sell, "source": "GGSOMA"})

            upserted += 1

        if seen_ext_ids:
            await s.execute(
                update(ResellerProduct)
                .where(
                    ResellerProduct.source_id == source.id,
                    ResellerProduct.external_id.not_in(seen_ext_ids)
                )
                .values(stock=0, last_synced=now)
            )

        await _mark_source_synced(s, source.id, now)

    _log.info("GGSOMA sync complete: %d products upserted.", upserted)
    return {"upserted": upserted, "new_products": new_products, "added_stock": added_stock}


async def sync_source(source_id: int) -> dict:
    """Synchronize exactly one source, serializing concurrent requests for it."""
    lock = _source_locks.setdefault(source_id, asyncio.Lock())
    async with lock:
        async with Database().session() as s:
            source = await s.get(ResellerSource, source_id)

        if source is None:
            raise ResellerSyncError("Reseller source not found")

        handlers = {
            "forkpixel": _sync_forkpixel,
            "cgpt": _sync_cgpt,
            "safwan": _sync_safwan,
            "canboso": _sync_canboso,
            "ggsoma": _sync_ggsoma,
        }
        handler = handlers.get(source.name)
        if handler is None:
            raise ResellerSyncError(f"Unsupported reseller source: {source.name}")

        try:
            return await handler(source)
        except ResellerSyncError:
            raise
        except Exception as exc:
            raise ResellerSyncError(
                f"{source.name} product sync failed: {exc}"
            ) from exc


async def sync_all_sources() -> dict[str, dict | None]:
    """
    Sync all active reseller sources. Returns {source_name: products_upserted}.
    Safe to call repeatedly (idempotent upsert logic).

    A ``None`` result means that source failed while the remaining sources
    continued syncing.
    """
    results: dict[str, dict | None] = {}

    async with Database().session() as s:
        sources = (await s.execute(
            select(ResellerSource.id, ResellerSource.name)
            .where(ResellerSource.is_active == True)  # noqa: E712
        )).all()

    for source_id, source_name in sources:
        try:
            results[source_name] = await sync_source(source_id)
        except Exception as exc:
            _log.error("Error syncing source %s: %s", source_name, exc)
            results[source_name] = None

    return results
