import asyncio
import logging
from sqlalchemy import select, update, delete
from packages.database.engine import Database
from packages.database.models.main import ResellerSource, ResellerProduct
from packages.services.reseller.sync import sync_all_sources, ensure_sources_exist

logging.basicConfig(level=logging.INFO)

async def main():
    print("=== 1. Ensuring and Updating Reseller Sources ===")
    await ensure_sources_exist()

    async with Database().session() as s:
        # 1. Deactivate Safwan and other unknown sources
        sources = (await s.execute(select(ResellerSource))).scalars().all()
        for src in sources:
            if src.name not in ("canboso", "ggsoma", "cgpt", "forkpixel"):
                print(f"Deactivating source: {src.name}")
                src.is_active = False
            elif src.name == "forkpixel":
                src.base_url = "https://lahastore.up.railway.app/api/v1"
                src.api_key = "psk_mR1LKalJwXvnoYNMuUjORQC5H92QJZczoJHJCjFjoCkni3"
                src.is_active = True
            elif src.name == "canboso":
                src.base_url = "https://canboso.com/api/v2/telegram-buyer"
                src.api_key = "tgb_286aee3c314ed61da656aab4a5267901916f7e9d48fdf70e"
                src.is_active = True
            elif src.name == "ggsoma":
                src.base_url = "https://ggsoma.store/api/partner/v1"
                src.api_key = "sk_live_237f47e759584bd9ed9dce88c800c3adf102d886d7a7ae2ea5db2083d5d08190"
                src.is_active = True
            elif src.name == "cgpt":
                src.base_url = "https://cgpt-active.pro/telegram/api"
                src.api_key = "rsk_j40ii9jCjD3tgrXj-x-nYHm1UCNZW5tw"
                src.is_active = True
        
        await s.commit()

        # 2. Disable all products from inactive sources
        inactive_source_ids = [src.id for src in sources if not src.is_active]
        if inactive_source_ids:
            await s.execute(
                update(ResellerProduct)
                .where(ResellerProduct.source_id.in_(inactive_source_ids))
                .values(is_enabled=False, stock=0)
            )
            await s.commit()

        # 3. Disable all products from forkpixel that do NOT contain 'pixel'
        fp_source = (await s.execute(select(ResellerSource).where(ResellerSource.name == "forkpixel"))).scalars().first()
        if fp_source:
            await s.execute(
                update(ResellerProduct)
                .where(
                    ResellerProduct.source_id == fp_source.id,
                    ResellerProduct.name.not_ilike("%pixel%")
                )
                .values(is_enabled=False, stock=0)
            )
            await s.commit()

    print("\n=== 2. Running Live Sync for Approved Sellers (Canboso, GGSoma, CGPT, LahaStore Pixel) ===")
    results = await sync_all_sources()
    print("Sync results:", results)

    async with Database().session() as s:
        # Check counts
        active_products = (await s.execute(
            select(ResellerProduct, ResellerSource)
            .join(ResellerSource, ResellerProduct.source_id == ResellerSource.id)
            .where(ResellerProduct.is_enabled == True, ResellerSource.is_active == True)
        )).all()

        in_stock = [p for p, _ in active_products if (p.stock or 0) > 0 or p.stock is None]
        out_stock = [p for p, _ in active_products if p.stock == 0]

        print(f"\n=== 3. Catalog Status Summary ===")
        print(f"Total Active Products: {len(active_products)}")
        print(f"In Stock: {len(in_stock)}")
        print(f"Out of Stock (stock=0): {len(out_stock)}")

        print("\n--- Active Products List Sample ---")
        for p, src in active_products[:15]:
            print(f"- [{src.name.upper()}] {p.name} | Price: ${p.sell_price or p.cost_price} | Stock: {p.stock if p.stock is not None else 'Available'}")

if __name__ == "__main__":
    asyncio.run(main())
