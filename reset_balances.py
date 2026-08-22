import asyncio
from dotenv import load_dotenv
from sqlalchemy import update

# Load environment variables before importing database modules
load_dotenv(encoding='utf-8')

from packages.database.engine import Database
from packages.database.models.main import User

async def main():
    db = Database()
    async with db.session() as session:
        # Perform the update statement on the User table
        stmt = update(User).values(balance=0)
        result = await session.execute(stmt)
        print(f"Successfully reset balance to 0 for users. Rows affected: {result.rowcount}")

if __name__ == "__main__":
    asyncio.run(main())
