"""
TronGrid blockchain verifier for USDT TRC20 deposits.

Replaces Bybit deposit-records API which requires special account permissions.
TronGrid is free, requires no authentication for standard queries, and gives
real-time on-chain data.

Contract addresses
  Mainnet USDT TRC20: TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t
"""

import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# USDT TRC20 contract on Tron mainnet
USDT_TRC20_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

# TronGrid public endpoint (no key needed for basic queries)
TRONGRID_BASE = "https://api.trongrid.io"

_session: Optional[aiohttp.ClientSession] = None
_timeout = aiohttp.ClientTimeout(total=20)


def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(timeout=_timeout)
    return _session


async def close_session() -> None:
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None


async def find_usdt_trc20_transfer(
    wallet_address: str,
    expected_amount: float,
    since_timestamp_ms: int,
    tolerance: float = 0.005,
    limit: int = 40,
) -> Optional[dict]:
    """
    Search recent USDT TRC20 transfers TO `wallet_address` and return the first
    one matching `expected_amount` ± `tolerance` that arrived after
    `since_timestamp_ms`.

    Returns a dict with keys: tx_hash, amount, timestamp_ms, from_address
    or None if no matching transfer is found yet.
    """
    url = (
        f"{TRONGRID_BASE}/v1/accounts/{wallet_address}/transactions/trc20"
        f"?contract_address={USDT_TRC20_CONTRACT}"
        f"&limit={limit}"
        f"&only_confirmed=true"
    )
    session = _get_session()
    try:
        async with session.get(url, headers={"Accept": "application/json"}) as resp:
            if resp.status != 200:
                body = await resp.text()
                logger.error(f"TronGrid HTTP {resp.status}: {body[:200]}")
                return None
            data = await resp.json()
    except Exception as e:
        logger.error(f"TronGrid request failed: {e}")
        return None

    transfers = data.get("data", [])
    for tx in transfers:
        # Only look at incoming transfers (to == our wallet)
        to_addr = tx.get("to", "")
        if to_addr.upper() != wallet_address.upper():
            continue

        # Timestamp check — TronGrid gives block_timestamp in ms
        block_ts = tx.get("block_timestamp", 0)
        if block_ts < since_timestamp_ms:
            continue

        # Amount — TronGrid returns value in smallest unit (6 decimals for USDT)
        raw_value = tx.get("value", "0")
        try:
            usdt_amount = int(raw_value) / 1_000_000
        except (ValueError, TypeError):
            continue

        if abs(usdt_amount - expected_amount) <= tolerance:
            return {
                "tx_hash": tx.get("transaction_id", ""),
                "amount": usdt_amount,
                "timestamp_ms": block_ts,
                "from_address": tx.get("from", ""),
            }

    return None
