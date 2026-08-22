import hashlib
import hmac
import time
from typing import Optional, Dict, Any
import jwt
from packages.config.config import EnvKeys

import os

# JWT Settings
SECRET_KEY = os.getenv("JWT_SECRET") or getattr(EnvKeys, "SECRET_KEY", None) or EnvKeys.TOKEN
if SECRET_KEY == "change-me-in-production":
    SECRET_KEY = EnvKeys.TOKEN
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

def verify_telegram_authorization(auth_data: dict) -> bool:
    """
    Verifies the data received from the Telegram Login Widget.
    https://core.telegram.org/widgets/login#checking-authorization
    """
    if "hash" not in auth_data:
        return False
        
    received_hash = auth_data.pop("hash")
    
    # Sort data by key and format as key=value\n
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(auth_data.items()) if v is not None
    )
    
    # Generate secret key using SHA256 of the bot token
    secret_key = hashlib.sha256(EnvKeys.TOKEN.encode()).digest()
    
    # Calculate HMAC-SHA256 signature
    calculated_hash = hmac.new(
        secret_key, 
        data_check_string.encode(), 
        hashlib.sha256
    ).hexdigest()
    
    # Check if hash matches
    if hmac.compare_digest(calculated_hash, received_hash):
        # Prevent replay attacks (check if auth_date is within last 24h)
        auth_date = int(auth_data.get("auth_date", 0))
        if time.time() - auth_date > 86400:
            return False
        return True
        
    return False

def create_access_token(data: dict, expires_delta_minutes: Optional[int] = None) -> str:
    """Generate a JWT for the user."""
    to_encode = data.copy()
    
    expire_mins = expires_delta_minutes if expires_delta_minutes else ACCESS_TOKEN_EXPIRE_MINUTES
    expire = time.time() + (expire_mins * 60)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode a JWT to get the user payload."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
