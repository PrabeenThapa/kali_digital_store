"""
Binance Pay Transaction Service
Polls GET /sapi/v1/pay/transactions to detect incoming USDT payments automatically.
"""
import asyncio
import hashlib
import hmac
import logging
import time
from decimal import Decimal
from urllib.parse import urlencode

import aiohttp

from packages.config.config import EnvKeys

logger = logging.getLogger(__name__)

BINANCE_API_BASE = "https://api.binance.com"
PAY_TRANSACTIONS_ENDPOINT = "/sapi/v1/pay/transactions"
POLL_INTERVAL_SECONDS = 30
POLL_TIMEOUT_SECONDS = 900   # 15 minutes


def _sign(params: dict, secret: str) -> str:
    """HMAC-SHA256 sign the query string."""
    query = urlencode(params)
    return hmac.new(
        secret.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def get_pay_transactions(
    start_ms: int,
    end_ms: int,
    limit: int = 50,
) -> list[dict]:
    """
    Fetch incoming Binance Pay transactions between start_ms and end_ms.
    Returns list of transaction dicts (empty list on error).
    """
    api_key = EnvKeys.BINANCE_API_KEY
    secret = EnvKeys.BINANCE_API_SECRET

    if not api_key or not secret:
        logger.warning("Binance API key/secret not configured — cannot poll Pay transactions.")
        return []

    params = {
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": limit,
        "timestamp": int(time.time() * 1000),
        "recvWindow": 10000,
    }
    params["signature"] = _sign(params, secret)

    headers = {"X-MBX-APIKEY": api_key}
    url = f"{BINANCE_API_BASE}{PAY_TRANSACTIONS_ENDPOINT}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning(f"Binance Pay API {resp.status}: {body[:200]}")
                    return []
                data = await resp.json()
                if data.get("code") != "000000":
                    logger.warning(f"Binance Pay API error: {data.get('message', data)}")
                    return []
                return data.get("data", [])
    except Exception as e:
        logger.error(f"Binance Pay API request failed: {e}")
        return []


async def find_payment(
    unique_amount: Decimal,
    currency: str,
    claim_time_ms: int,
    remark_code: str | None = None,
    timeout_s: int = POLL_TIMEOUT_SECONDS,
    poll_interval_s: int = POLL_INTERVAL_SECONDS,
) -> dict | None:
    """
    Poll Binance Pay transactions every poll_interval_s seconds for up to timeout_s.
    Returns the matching transaction dict if found, or None on timeout.

    Strict verification rules:
      - transStatus == "SUCCESS"
      - currency == expected currency
      - amount == unique_amount (EXACT Decimal match to 2dp - no more, no less)
      - transactionTime >= claim_time_ms
      - remark_code in transaction remark/memo/note (if remark_code provided)
    """
    deadline = time.time() + timeout_s
    target_dec = Decimal(str(unique_amount)).quantize(Decimal("0.01"))

    while time.time() < deadline:
        end_ms = int(time.time() * 1000)
        txns = await get_pay_transactions(start_ms=claim_time_ms, end_ms=end_ms)

        for txn in txns:
            if txn.get("transStatus") != "SUCCESS":
                continue
            if txn.get("currency", "").upper() != currency.upper():
                continue

            try:
                txn_amount = Decimal(str(txn.get("amount", 0))).quantize(Decimal("0.01"))
            except (TypeError, ValueError):
                continue

            # Strict amount check: must match target exactly (no more, no less)
            if txn_amount != target_dec:
                logger.info(f"Binance Pay amount mismatch: expected {target_dec}, got {txn_amount}. Rejecting match.")
                continue

            # Verify remarks if remark_code is provided
            if remark_code:
                txn_str = str(txn).upper()
                target_remark = str(remark_code).strip().upper()
                if target_remark not in txn_str:
                    logger.info(f"Binance Pay remark mismatch: expected '{target_remark}' in txn data. Rejecting match.")
                    continue

            logger.info(f"Binance Pay match verified: transId={txn.get('transId')}, amount={txn_amount}, remark={remark_code}")
            return txn

        logger.debug(f"Binance Pay: no verified match yet for {target_dec} {currency} (remark={remark_code}), sleeping {poll_interval_s}s...")
        await asyncio.sleep(poll_interval_s)

    return None
