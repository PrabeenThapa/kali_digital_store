import time
import secrets
import string
from typing import Optional, Dict, Any

# In-memory store for login challenges (can also fall back to Redis if available)
# Key: code (uppercase 8 alphanumeric chars) or token 'c'
_CHALLENGES: Dict[str, Dict[str, Any]] = {}

CHALLENGE_TTL_SECONDS = 300  # 5 minutes


def _cleanup_expired():
    now = time.time()
    expired_keys = [k for k, v in _CHALLENGES.items() if v["expires_at"] < now]
    for k in expired_keys:
        _CHALLENGES.pop(k, None)


def create_challenge() -> Dict[str, Any]:
    """Generate a new login challenge with a human-readable code and secure token."""
    _cleanup_expired()

    # Generate human code like SRTTQ6AE (8 chars uppercase without ambiguous chars 0, O, 1, I)
    alphabet = "".join(c for c in string.ascii_uppercase + string.digits if c not in "0O1I")
    code = "".join(secrets.choice(alphabet) for _ in range(8))
    
    # Generate secure random URL token
    token = secrets.token_urlsafe(32)

    now = time.time()
    challenge_data = {
        "code": code,
        "token": token,
        "status": "waiting",  # "waiting" | "approved" | "denied"
        "user_id": None,
        "created_at": now,
        "expires_at": now + CHALLENGE_TTL_SECONDS,
    }

    _CHALLENGES[code] = challenge_data
    _CHALLENGES[token] = challenge_data

    return {
        "code": code,
        "c": token,
        "expires_in": CHALLENGE_TTL_SECONDS,
    }


def get_challenge(code_or_token: str) -> Optional[Dict[str, Any]]:
    _cleanup_expired()
    key = (code_or_token or "").strip()
    return _CHALLENGES.get(key) or _CHALLENGES.get(key.upper())


def approve_challenge(code_or_token: str, user_id: int) -> bool:
    challenge = get_challenge(code_or_token)
    if not challenge:
        return False

    if challenge["status"] != "waiting" or challenge["expires_at"] < time.time():
        return False

    challenge["status"] = "approved"
    challenge["user_id"] = user_id
    return True


def deny_challenge(code_or_token: str) -> bool:
    challenge = get_challenge(code_or_token)
    if not challenge:
        return False

    challenge["status"] = "denied"
    return True
