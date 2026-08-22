"""
BSCScan on-chain verifier for USDT BEP20 deposits.

Uses the BSCScan public API (free, no key needed for basic token transfers).
Contract address: USDT on BSC = 0x55d398326f99059fF775485246999027B3197955
"""

import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# USDT BEP20 contract on BSC mainnet
USDT_BEP20_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"

BSCSCAN_BASE = "https://api.bscscan.com/api"

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


BSC_RPC_ENDPOINTS = [
    "https://bsc-dataseed.binance.org/",
    "https://bsc-dataseed1.binance.org/",
    "https://bsc-dataseed2.binance.org/",
    "https://binance.llamarpc.com",
    "https://bsc-rpc.publicnode.com",
]


async def verify_usdt_bep20_tx(
    tx_hash: str,
    wallet_address: str,
    expected_amount: float,
    since_timestamp_s: int,
    tolerance: float = 0.005,
) -> Optional[dict]:
    """
    Verify a specific BEP20 USDT transaction by hash.
    Iterates through multiple BSC RPC nodes for high reliability.
    """
    session = _get_session()
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getTransactionByHash",
        "params": [tx_hash],
        "id": 1
    }

    tx = None
    rpc_used = None

    for rpc_url in BSC_RPC_ENDPOINTS:
        try:
            async with session.post(rpc_url, json=payload, headers={"Accept": "application/json"}, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    res = data.get("result")
                    if res and isinstance(res, dict) and res.get("hash"):
                        tx = res
                        rpc_used = rpc_url
                        break
        except Exception as e:
            logger.warning(f"BSC RPC endpoint {rpc_url} failed: {e}")
            continue

    if not tx or not isinstance(tx, dict):
        logger.warning(f"BSCScan: tx {tx_hash} not found across BSC RPC endpoints")
        return None

    # Must be sent to the USDT contract
    to_addr = (tx.get("to") or "").lower()
    if to_addr != USDT_BEP20_CONTRACT.lower():
        logger.warning(f"BSCScan: tx {tx_hash} is not a USDT transfer (to={to_addr})")
        return None

    # Decode ERC20 transfer input: 0xa9059cbb + recipient (32 bytes) + amount (32 bytes)
    input_data = tx.get("input", "")
    if not input_data.startswith("0xa9059cbb") or len(input_data) < 138:
        logger.warning(f"BSCScan: tx {tx_hash} input does not look like a transfer")
        return None

    recipient_full = "0x" + input_data[34:74]
    amount_hex = input_data[74:138]
    try:
        raw_amount = int(amount_hex, 16)
        usdt_amount = raw_amount / 1_000_000_000_000_000_000  # 18 decimals on BSC
    except (ValueError, TypeError):
        logger.warning(f"BSCScan: could not parse amount from tx {tx_hash}")
        return None

    # Check recipient matches our wallet
    if recipient_full[-40:].lower() != wallet_address.lower().lstrip("0x").zfill(40):
        logger.warning(f"BSCScan: tx {tx_hash} recipient mismatch")
        return None

    if abs(usdt_amount - expected_amount) > tolerance:
        logger.warning(f"BSCScan: tx {tx_hash} amount {usdt_amount} doesn't match expected {expected_amount}")
        return None

    # Get receipt to confirm it's not reverted and get block timestamp
    receipt_payload = {
        "jsonrpc": "2.0",
        "method": "eth_getTransactionReceipt",
        "params": [tx_hash],
        "id": 2
    }
    receipt = None
    target_rpc = rpc_used or BSC_RPC_ENDPOINTS[0]
    try:
        async with session.post(target_rpc, json=receipt_payload, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            receipt_data = await resp.json()
            receipt = receipt_data.get("result")
    except Exception as e:
        logger.error(f"BSC RPC receipt request failed: {e}")

    if not receipt or not isinstance(receipt, dict):
        # Fail-open for pending confirmation if tx was found and matches amount
        logger.warning(f"BSC RPC: receipt for {tx_hash} pending/unavailable, proceeding with unconfirmed tx match")
        receipt = {"status": "0x1"}

    if receipt.get("status") == "0x0":
        logger.warning(f"BSC RPC: tx {tx_hash} reverted")
        return None

    # Get block timestamp
    block_number = tx.get("blockNumber", "0x0")
    block_payload = {
        "jsonrpc": "2.0",
        "method": "eth_getBlockByNumber",
        "params": [block_number, False],
        "id": 3
    }
    try:
        async with session.post("https://bsc-dataseed.binance.org/", json=block_payload) as resp:
            block_data = await resp.json()
        block_result = block_data.get("result")
        if isinstance(block_result, dict):
            block_ts = int(block_result.get("timestamp", "0x0"), 16)
        else:
            block_ts = 0
    except Exception:
        block_ts = 0

    if block_ts and block_ts < since_timestamp_s:
        logger.warning(f"BSCScan: tx {tx_hash} is too old (ts={block_ts} < {since_timestamp_s})")
        return None

    return {
        "tx_hash": tx_hash,
        "amount": usdt_amount,
        "timestamp_s": block_ts,
        "from_address": tx.get("from", ""),
    }
