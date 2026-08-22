from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import bcrypt
import logging
import random
import datetime

from apps.api.dependencies import get_db
from apps.api.core.security import verify_telegram_authorization, create_access_token
from packages.database.methods.create import create_user
from packages.database.methods.read import check_user
from packages.database.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class TelegramLoginData(BaseModel):
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str

class EmailAuthData(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

@router.post("/telegram", response_model=TokenResponse)
async def login_via_telegram(data: TelegramLoginData, db: AsyncSession = Depends(get_db)):
    auth_data = data.model_dump(exclude_none=True)
    
    if not verify_telegram_authorization(auth_data):
        logger.warning(f"Failed Telegram auth attempt for ID {data.id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization data"
        )
        
    user = await check_user(data.id)
    if not user:
        user_name = data.username if data.username else data.first_name
        try:
            await create_user(
                telegram_id=data.id,
                username=user_name,
                first_name=data.first_name,
                last_name=data.last_name or ""
            )
        except Exception as e:
            logger.error(f"Error creating user during Telegram Auth: {e}")
            raise HTTPException(status_code=500, detail="Could not create user profile")
            
    access_token = create_access_token(data={"sub": str(data.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=TokenResponse)
async def register_email(data: EmailAuthData, db: AsyncSession = Depends(get_db)):
    # Check if email exists
    result = await db.execute(select(User).filter(User.email == data.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Generate a negative telegram_id for web-only users
    # To prevent collisions, loop until we find a free one
    while True:
        fake_id = -1 * random.randint(10000000, 99999999)
        if not await check_user(fake_id):
            break

    # Create user — note: Database().session() auto-commits on context exit,
    # so we must NOT call db.commit() manually here to avoid a double-commit error.
    try:
        new_user = User(
            telegram_id=fake_id,
            registration_date=datetime.datetime.now(datetime.timezone.utc),
            balance=0,
            role_id=1
        )
        new_user.email = data.email
        new_user.password_hash = get_password_hash(data.password)
        db.add(new_user)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating web user: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user account")

    access_token = create_access_token(data={"sub": str(fake_id)})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login_email", response_model=TokenResponse)
async def login_email(data: EmailAuthData, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.email == data.email))
    user = result.scalars().first()
    
    if not user or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        
    access_token = create_access_token(data={"sub": str(user.telegram_id)})
    return {"access_token": access_token, "token_type": "bearer"}


class TelegramIdLoginData(BaseModel):
    telegram_id: int
    password: str

@router.post("/login_telegram_id", response_model=TokenResponse)
async def login_telegram_id(data: TelegramIdLoginData, db: AsyncSession = Depends(get_db)):
    """
    Log in using a Telegram User ID + a password previously set via the bot
    (the 'Set up Website Login' flow in web_auth.py).
    """
    result = await db.execute(select(User).where(User.telegram_id == data.telegram_id))
    user = result.scalars().first()

    # Deliberately vague error to prevent user enumeration
    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram ID or password. Make sure you set a password via the bot first."
        )

    if not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram ID or password."
        )

    access_token = create_access_token(data={"sub": str(user.telegram_id)})
    return {"access_token": access_token, "token_type": "bearer"}


# ─────────────────────────────────────────────────────────────────────────────
# GGBuilder-style Telegram Instant Challenge Confirmation
# ─────────────────────────────────────────────────────────────────────────────

from packages.services.challenge_auth import (
    create_challenge,
    get_challenge,
    approve_challenge,
    deny_challenge,
)

@router.post("/challenge/create")
async def create_login_challenge():
    """Create an instant login challenge for Telegram verification."""
    data = create_challenge()
    return {
        "code": data["code"],
        "c": data["c"],
        "expires_in": data["expires_in"],
        "bot_username": "kali_store_bot",
    }


@router.get("/challenge/poll")
async def poll_login_challenge(
    code: str | None = None,
    c: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Poll the status of a login challenge from the web browser."""
    key = c or code
    if not key:
        raise HTTPException(status_code=400, detail="Missing challenge code or token")

    challenge = get_challenge(key)
    if not challenge:
        return {"status": "expired"}

    if challenge["status"] == "approved" and challenge["user_id"]:
        # Challenge approved via Telegram bot!
        user_id = challenge["user_id"]
        # Ensure user exists in DB
        user = (await db.execute(select(User).where(User.telegram_id == user_id))).scalar_one_or_none()
        if not user:
            # Create user if first time
            try:
                await create_user(telegram_id=user_id, username="", first_name="User", last_name="")
            except Exception as e:
                logger.warning(f"Failed to auto-create user {user_id} on challenge login: {e}")

        token = create_access_token(data={"sub": str(user_id)})
        return {
            "status": "approved",
            "access_token": token,
            "token_type": "bearer",
            "user_id": user_id,
        }

    if challenge["status"] == "denied":
        return {"status": "denied"}

    return {"status": "waiting"}


