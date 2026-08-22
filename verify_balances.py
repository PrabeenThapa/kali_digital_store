import asyncio
from dotenv import load_dotenv
from sqlalchemy import select

# Load environment variables before importing database modules
load_dotenv(encoding='utf-8')

from packages.database.engine import Database
from packages.database.models.main import User

async def main():
    db = Database()
    async with db.session() as session:
        # Check if there are any users with non-zero balance
        stmt = select(User).where(User.balance != 0)
        result = await session.execute(stmt)
        users_with_balance = result.scalars().all()
        if len(users_with_balance) == 0:
            print("Verification successful: All users have a balance of exactly 0.")
        else:
            print(f"Verification failed: Found {len(users_with_balance)} users with non-zero balance.")
            for user in users_with_balance:
                print(f"User {user.telegram_id}: balance = {user.balance}")

if __name__ == "__main__":
    asyncio.run(main())
