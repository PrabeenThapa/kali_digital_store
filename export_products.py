import asyncio
import os
from dotenv import load_dotenv
load_dotenv(".env")
# Ensure POSTGRES_HOST uses localhost since we are running outside Docker
os.environ["POSTGRES_HOST"] = "localhost"

from sqlalchemy import select
from packages.database.engine import Database
from packages.database.models import Goods, ResellerProduct

async def main():
    text = ""
    async with Database().session() as session:
        # Get standard goods
        goods_result = await session.execute(select(Goods))
        goods = goods_result.scalars().all()
        for item in goods:
            text += f"📦 {item.name} 💵${item.price}\n"
            
        # Get reseller products
        reseller_result = await session.execute(select(ResellerProduct).where(ResellerProduct.is_enabled == True))
        reseller_products = reseller_result.scalars().all()
        for rp in reseller_products:
            price = rp.effective_sell_price
            text += f"🌐 {rp.name} 💵${price}\n"

    text += "\n⬇️ ⬇️ ⬇️\n"
    text += "⭐Global Bot Accepts Binance and BEP20 :\n"
    text += "🪙 @kali_store_bot\n\n"
    text += "🎉 🎉 🎉\n"
    text += "⭐Please click expand below to see all items\n"
    text += "⬇️ ⬇️ ⬇️\n"
    
    with open("products_list.txt", "w", encoding="utf-8") as f:
        f.write(text)

if __name__ == "__main__":
    asyncio.run(main())
