"""
Bybit Wallet/Deposit integration using the Bybit V5 API.

Flow:
  1. Bot fetches the USDT deposit address from Bybit API.
  2. User sends a unique amount (base + random cents) for identification.
  3. Bot polls deposit records to find a matching transaction.
  4. On match → credits the user's balance.
"""

import hashlib
import hmac
import time
import logging
import aiohttp
from typing import Optional
from urllib.parse import urlencode

from packages.config.config import EnvKeys

logger = logging.getLogger(__name__)


class BybitPayError(Exception):
    """Raised when the Bybit API returns an error response."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Bybit Error [{code}]: {message}")


class BybitPayAPI:
    """Async client for the Bybit V5 Wallet/Deposit API."""

    BASE_URL = "https://api.bybit.com"
    _timeout = aiohttp.ClientTimeout(total=30)
    _session: Optional[aiohttp.ClientSession] = None

    DEFAULT_COIN = "USDT"
    DEFAULT_CHAIN = "TRX"  # TRC20

    def __init__(self):
        self.api_key = EnvKeys.BYBIT_API_KEY
        self.api_secret = EnvKeys.BYBIT_API_SECRET

    # ── Session management ────────────────────────────────────────────────── #

    @classmethod
    def _get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession(timeout=cls._timeout)
        return cls._session

    @classmethod
    async def close_session(cls):
        if cls._session and not cls._session.closed:
            await cls._session.close()
            cls._session = None

    # ── HMAC-SHA256 signing ───────────────────────────────────────────────── #

    def _sign(self, timestamp: str, recv_window: str, query_string: str) -> str:
        payload = f"{timestamp}{self.api_key}{recv_window}{query_string}"
        return hmac.new(
            self.api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _auth_headers(self, query_string: str = "") -> dict:
        timestamp = str(int(time.time() * 1000))
        recv_window = "5000"
        signature = self._sign(timestamp, recv_window, query_string)
        return {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "X-BAPI-SIGN": signature,
        }

    # ── Core GET request ──────────────────────────────────────────────────── #

    async def _get(self, endpoint: str, params: dict) -> dict:
        query_string = urlencode(params)
        url = f"{self.BASE_URL}{endpoint}?{query_string}"
        headers = self._auth_headers(query_string)
        session = self._get_session()
        try:
            async with session.get(url, headers=headers) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except Exception as e:
            logger.error(f"Bybit GET error on {endpoint}: {e}")
            raise BybitPayError("HTTP_ERROR", str(e))

        ret_code = str(data.get("retCode", ""))
        ret_msg = data.get("retMsg", "Unknown error")
        if ret_code != "0":
            logger.error(f"Bybit API error {ret_code}: {ret_msg}")
            raise BybitPayError(code=ret_code, message=ret_msg)

        return data.get("result", {})

    # ── Public API methods ────────────────────────────────────────────────── #

    async def get_deposit_address(
        self,
        coin: str = DEFAULT_COIN,
        chain_type: str = DEFAULT_CHAIN,
    ) -> dict:
        """Return the deposit address for a coin/chain.

        First tries the Bybit API. If that fails (e.g. account not KYC'd or
        lacking deposit permission), falls back to the static wallet addresses
        configured in .env (TRC20_WALLET / BEP20_WALLET).
        """
        try:
            result = await self._get(
                "/v5/asset/deposit/query-address",
                {"coin": coin, "chainType": chain_type},
            )
            for chain in result.get("chains", []):
                if chain.get("chain", "").upper() == chain_type.upper():
                    return {
                        "address": chain.get("addressDeposit", ""),
                        "tag": chain.get("tagDeposit", ""),
                        "chain": chain_type,
                        "coin": coin,
                    }
            chains = result.get("chains", [])
            if chains:
                return {
                    "address": chains[0].get("addressDeposit", ""),
                    "tag": chains[0].get("tagDeposit", ""),
                    "chain": chains[0].get("chain", ""),
                    "coin": coin,
                }
        except BybitPayError as e:
            logger.warning(
                f"Bybit API deposit address failed ({e.code}: {e.message}). "
                f"Falling back to static wallet from env."
            )

        # ── Static wallet fallback ────────────────────────────────────────── #
        # Used when Bybit API lacks deposit permission (e.g. unverified account).
        # Unique-amount identification still works with any wallet address.
        chain_upper = chain_type.upper()
        if chain_upper == "TRX" and getattr(EnvKeys, "TRC20_WALLET", "").strip():
            return {
                "address": EnvKeys.TRC20_WALLET.strip(),
                "tag": "",
                "chain": "TRX",
                "coin": coin,
            }
        if chain_upper in ("ETH", "BSC") and getattr(EnvKeys, "BEP20_WALLET", "").strip():
            return {
                "address": EnvKeys.BEP20_WALLET.strip(),
                "tag": "",
                "chain": chain_upper,
                "coin": coin,
            }

        raise BybitPayError("NO_ADDRESS", f"No deposit address found for {coin}/{chain_type}")

    async def get_recent_deposits(self, coin: str = DEFAULT_COIN, limit: int = 20) -> list:
        """Return recent deposit records (status 3 = confirmed)."""
        result = await self._get(
            "/v5/asset/deposit/query-record",
            {"coin": coin, "limit": str(limit)},
        )
        return result.get("rows", [])

    async def find_matching_deposit(
        self,
        expected_amount: float,
        since_timestamp_ms: int,
        coin: str = DEFAULT_COIN,
        tolerance: float = 0.005,
    ) -> Optional[dict]:
        """Find a confirmed deposit matching the expected amount."""
        deposits = await self.get_recent_deposits(coin=coin, limit=50)
        for dep in deposits:
            if str(dep.get("status", "")) != "3":
                continue
            if int(dep.get("insertTime", 0)) < since_timestamp_ms:
                continue
            if abs(float(dep.get("amount", 0)) - expected_amount) <= tolerance:
                return dep
        return None

    async def get_internal_deposits(self, coin: str = DEFAULT_COIN, limit: int = 50) -> list:
        """Return internal deposit records (from other Bybit users via UID)."""
        result = await self._get(
            "/v5/asset/deposit/query-internal-record",
            {"coin": coin, "limit": str(limit)},
        )
        return result.get("rows", [])

    async def find_matching_internal_deposit(
        self,
        expected_amount: float,
        since_timestamp_ms: int,
        coin: str = DEFAULT_COIN,
        tolerance: float = 0.005,
    ) -> Optional[dict]:
        """Find a successful internal deposit matching the expected amount."""
        deposits = await self.get_internal_deposits(coin=coin, limit=50)
        for dep in deposits:
            if str(dep.get("status", "")) != "2":
                continue
            ts = int(dep.get("createdTime") or dep.get("insertTime") or 0)
            if ts < since_timestamp_ms:
                continue
            if abs(float(dep.get("amount", 0)) - expected_amount) <= tolerance:
                return dep
        return None

    async def find_internal_deposit_by_txid(
        self,
        tx_id: str,
        coin: str = DEFAULT_COIN,
        since_timestamp_ms: int = 0,
    ) -> Optional[dict]:
        """Look up a specific internal deposit by its tx ID / order ID.

        Bybit's internal-record endpoint returns rows with `txID` field.
        We scan the most recent 50 rows for a match and verify it occurred after `since_timestamp_ms`.
        """
        needle = (tx_id or "").strip()
        if not needle:
            return None
        deposits = await self.get_internal_deposits(coin=coin, limit=50)
        for dep in deposits:
            candidates = (
                str(dep.get("txID", "")),
                str(dep.get("orderId", "")),
                str(dep.get("id", "")),
            )
            if any(c and c == needle for c in candidates):
                if str(dep.get("status", "")) != "2":
                    return None
                ts = int(dep.get("createdTime") or dep.get("insertTime") or 0)
                if since_timestamp_ms > 0 and ts < since_timestamp_ms:
                    logger.warning(
                        f"Bybit tx {tx_id} rejected: deposit timestamp ({ts}) is older than timepoint ({since_timestamp_ms})"
                    )
                    return None
                return dep
        return None

    async def check_credentials(self) -> bool:
        """Verify the API key is valid."""
        try:
            await self.get_deposit_address()
            return True
        except BybitPayError:
            return False
