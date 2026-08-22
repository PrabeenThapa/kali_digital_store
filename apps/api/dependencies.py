from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from packages.database.engine import Database
from packages.database.models import User, Role, Permission
from packages.config.config import EnvKeys
from apps.api.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/telegram")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="api/auth/telegram", auto_error=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session."""
    async with Database().session() as session:
        yield session

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_db)
) -> User:
    """Dependency to get the authenticated user from the JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
        
    sub_val = payload.get("sub")
    if sub_val is None:
        raise credentials_exception
    try:
        telegram_id = int(sub_val)
    except (ValueError, TypeError):
        raise credentials_exception
        
    # Fetch user from database
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
        
    return user

async def get_optional_current_user(
    token: str | None = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db)
) -> User | None:
    """Dependency to optionally get the authenticated user if token is present."""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        if not payload:
            return None
        sub_val = payload.get("sub")
        if not sub_val:
            return None
        telegram_id = int(sub_val)
        result = await db.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()
    except Exception:
        return None


async def get_current_admin_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency to ensure the current user is an admin or the owner."""
    # 1. Owner always has access
    if EnvKeys.OWNER_ID and current_user.telegram_id == EnvKeys.OWNER_ID:
        return current_user

    # 2. Check role in DB
    role_res = await db.execute(select(Role).where(Role.id == current_user.role_id))
    role = role_res.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    # Check role name or permissions bitmask
    if role.name in ("ADMIN", "OWNER") or Permission.has_any_admin_perm(role.permissions or 0):
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin privileges required",
    )
