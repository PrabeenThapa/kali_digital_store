"""
Reseller API HTTP clients.

ForkPixelClient — Partner API
    Base URL : https://forkpxelbot-production.up.railway.app/api/v1
    Auth     : X-API-Key header

CGPTClient — Reseller API
    Base URL : https://cgpt-active.pro/telegram/api
    Auth     : Authorization: Bearer rsk_xxx

CanbosoClient — Canboso Reseller API
    Base URL : https://canboso.com/api
    Auth     : X-API-Key header
"""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30)


# ────────────────────────────────────────────────────────────────
#  ForkPixel Client
# ────────────────────────────────────────────────────────────────

class ForkPixelClient:
    """Async HTTP client for the ForkPixel Partner API."""

    def __init__(self, api_key: str, base_url: str, currency: str = "usd"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.currency = currency  # "usd" or "vnd"
        self._headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    async def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        async with aiohttp.ClientSession(headers=self._headers, timeout=_DEFAULT_TIMEOUT) as s:
            async with s.get(url, params=params) as resp:
                data = await resp.json(content_type=None)
                if not resp.ok:
                    raise RuntimeError(f"ForkPixel GET {path} → {resp.status}: {data}")
                return data

    async def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        async with aiohttp.ClientSession(headers=self._headers, timeout=_DEFAULT_TIMEOUT) as s:
            async with s.post(url, json=payload) as resp:
                data = await resp.json(content_type=None)
                if not resp.ok:
                    raise RuntimeError(f"ForkPixel POST {path} → {resp.status}: {data}")
                return data

    async def get_products(self) -> list[dict]:
        """Return all active products from the ForkPixel store.

        The endpoint is paginated.  The previous implementation only read
        page one, which silently left larger catalogs partially synced.
        """
        page_size = 200
        page = 1
        products: list[dict] = []
        seen_keys: set[str] = set()

        while True:
            data = await self._get(
                "/products", params={"limit": page_size, "page": page}
            )
            batch = data.get("products") or []
            if not isinstance(batch, list) or not batch:
                break

            new_items = []
            for product in batch:
                # Prefer a stable API id; repr is a safe fallback for the
                # occasional legacy response without one.
                key = str(product.get("productId") or product.get("id") or repr(product))
                if key not in seen_keys:
                    seen_keys.add(key)
                    new_items.append(product)
            if not new_items:
                break
            products.extend(new_items)

            pagination = data.get("pagination") or data.get("meta") or {}
            total_pages = (
                pagination.get("totalPages")
                or pagination.get("total_pages")
                or data.get("totalPages")
                or data.get("total_pages")
            )
            has_next = pagination.get("hasNext", pagination.get("has_next"))
            if has_next is False or (total_pages and page >= int(total_pages)):
                break
            # Without metadata, a short page is the conventional end marker.
            if not total_pages and has_next is not True and len(batch) < page_size:
                break
            page += 1

        return products

    async def get_balance(self) -> dict:
        """Return current wallet balances."""
        return await self._get("/balance")

    async def place_order(
        self,
        *,
        code: str | None = None,
        product_id: int | None = None,
        qty: int = 1,
        shop_order_id: str | None = None,
    ) -> dict:
        """
        Purchase stock items. Returns the full order response including
        `order.accounts` for instant delivery.
        """
        payload: dict[str, Any] = {"qty": qty, "currency": self.currency}
        if code:
            payload["code"] = code
        elif product_id is not None:
            payload["productId"] = product_id
        else:
            raise ValueError("Either code or product_id must be provided")
        if shop_order_id:
            payload["shopOrderId"] = shop_order_id
        return await self._post("/orders", payload)

    async def get_order(self, order_code: str) -> dict:
        """Retrieve a specific order by order code."""
        return await self._get(f"/orders/{order_code}")

    # ── Gemini Task API (gateway) ──────────────────────────────

    async def get_gemini_prices(self) -> dict:
        """Return Gemini task prices + balance via /gateway."""
        return await self._post("/gateway", {"action": "get_balance", "psk_key": self.api_key})

    async def submit_gemini_task(
        self,
        *,
        email: str,
        password: str,
        task_type: str = "full",
        twofa: str | None = None,
    ) -> dict:
        """Submit a Gemini account upgrade task."""
        payload = {
            "action": "submit_task",
            "psk_key": self.api_key,
            "email": email,
            "password": password,
            "task_type": task_type,
            "currency": self.currency,
        }
        if twofa:
            payload["twofa"] = twofa
        return await self._post("/gateway", payload)

    async def get_gemini_task_status(self, task_id: str) -> dict:
        """Query the status of a submitted Gemini task."""
        return await self._post(
            "/gateway", {"action": "get_status", "psk_key": self.api_key, "task_id": task_id}
        )

    async def cancel_gemini_task(self, task_id: str) -> dict:
        """Cancel a pending/running Gemini task (refunds balance)."""
        return await self._post(
            "/gateway", {"action": "cancel_task", "psk_key": self.api_key, "task_id": task_id}
        )


# ────────────────────────────────────────────────────────────────
#  CGPT Reseller Client
# ────────────────────────────────────────────────────────────────

class CGPTClient:
    """Async HTTP client for the CGPT Reseller API."""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        async with aiohttp.ClientSession(headers=self._headers, timeout=_DEFAULT_TIMEOUT) as s:
            async with s.get(url, params=params) as resp:
                data = await resp.json(content_type=None)
                if not resp.ok:
                    raise RuntimeError(f"CGPT GET {path} → {resp.status}: {data}")
                return data

    async def _post(self, path: str, payload: dict, extra_headers: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        headers = dict(self._headers)
        if extra_headers:
            headers.update(extra_headers)
        async with aiohttp.ClientSession(headers=headers, timeout=_DEFAULT_TIMEOUT) as s:
            async with s.post(url, json=payload) as resp:
                data = await resp.json(content_type=None)
                if not resp.ok:
                    raise RuntimeError(f"CGPT POST {path} → {resp.status}: {data}")
                return data

    async def get_me(self) -> dict:
        """Return reseller profile and current balance."""
        return await self._get("/v1/me")

    async def get_products(self) -> list[dict]:
        """Return all available products."""
        data = await self._get("/v1/products")
        return data.get("products", [])

    async def get_product(self, product_id: int) -> dict:
        """Return a single product by ID."""
        return await self._get(f"/v1/products/{product_id}")

    async def place_order(
        self,
        *,
        product_id: int,
        quantity: int = 1,
        inputs: dict | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        """
        Place an order. Returns full OrderResponse including delivered_codes
        for instant stock items, or empty list for preorder/team_invite.
        """
        payload: dict[str, Any] = {"product_id": product_id, "quantity": quantity}
        if inputs:
            payload["inputs"] = inputs
        extra = {}
        if idempotency_key:
            extra["Idempotency-Key"] = idempotency_key
        return await self._post("/v1/orders", payload, extra_headers=extra)

    async def get_order(self, order_id: int) -> dict:
        """Retrieve order details by order_id."""
        return await self._get(f"/v1/orders/{order_id}")

    async def list_orders(self, limit: int = 20, cursor: int = None) -> dict:
        """List recent orders with cursor-based pagination."""
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self._get("/v1/orders", params=params)

    async def resubmit_inputs(self, order_id: int, inputs: dict) -> dict:
        """Re-submit corrected buyer inputs for a team_invite order that was input_rejected."""
        return await self._post(f"/v1/orders/{order_id}/inputs", {"inputs": inputs})


# ────────────────────────────────────────────────────────────────
#  SafwanTiger Reseller Client
# ────────────────────────────────────────────────────────────────

class SafwanTigerClient:
    """Async HTTP client for the SafwanTiger Reseller Product API.

    Base URL : https://safwantigershopbot-production.up.railway.app/api
    Auth     : Authorization: Bearer stapi_xxx
    Prices are already in USD (USDT).
    """

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        async with aiohttp.ClientSession(headers=self._headers, timeout=_DEFAULT_TIMEOUT) as s:
            async with s.get(url, params=params) as resp:
                data = await resp.json(content_type=None)
                if not resp.ok:
                    raise RuntimeError(f"SafwanTiger GET {path} → {resp.status}: {data}")
                return data

    async def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        async with aiohttp.ClientSession(headers=self._headers, timeout=_DEFAULT_TIMEOUT) as s:
            async with s.post(url, json=payload) as resp:
                data = await resp.json(content_type=None)
                if not resp.ok:
                    raise RuntimeError(f"SafwanTiger POST {path} → {resp.status}: {data}")
                return data

    async def get_products(self) -> list[dict]:
        """Return all products from the SafwanTiger store."""
        data = await self._get("/products")
        return data.get("products", [])

    async def get_balance(self) -> dict:
        """Return current wallet balance."""
        return await self._get("/balance")

    async def place_order(
        self,
        *,
        product_id: int,
        quantity: int = 1,
        request_id: str | None = None,
    ) -> dict:
        """
        Place an order. Returns delivered items in JSON.
        Wallet balance is deducted only when the order is completed.
        """
        payload: dict[str, Any] = {"product_id": product_id, "quantity": quantity}
        if request_id:
            payload["request_id"] = request_id
        return await self._post("/order", payload)


# ────────────────────────────────────────────────────────────────
#  Canboso Reseller Client
# ────────────────────────────────────────────────────────────────

class CanbosoClient:
    """Async HTTP client for the Canboso "Buyer API" (v1.2.0).

    Base URL : https://canboso.com/api/telegram-buyer
    Auth     : buyer key sent as the `key` query/body param (NOT a header)
    Prices are in USD (`usdPricing` field); wallet is prepaid.

    Endpoints:
        GET  /products  ?key=...
        GET  /balance   ?key=...
        POST /purchase   {key, product_id, quantity}
    """

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._headers = {"Content-Type": "application/json"}

    async def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        query = {"key": self.api_key, **(params or {})}
        async with aiohttp.ClientSession(headers=self._headers, timeout=_DEFAULT_TIMEOUT) as s:
            async with s.get(url, params=query) as resp:
                data = await resp.json(content_type=None)
                if not resp.ok or not data.get("success", True):
                    raise RuntimeError(f"Canboso GET {path} → {resp.status}: {data}")
                return data

    async def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        body = {"key": self.api_key, **payload}
        async with aiohttp.ClientSession(headers=self._headers, timeout=_DEFAULT_TIMEOUT) as s:
            async with s.post(url, json=body) as resp:
                data = await resp.json(content_type=None)
                if not resp.ok or not data.get("success", True):
                    raise RuntimeError(f"Canboso POST {path} → {resp.status}: {data}")
                return data

    async def get_products(self) -> list[dict]:
        """Return all products for this buyer key."""
        data = await self._get("/products")
        return data.get("products", [])

    async def get_balance(self) -> dict:
        """Return current wallet balance."""
        return await self._get("/balance")

    async def place_order(
        self,
        *,
        product_id: str,
        quantity: int = 1,
        customer_email: str | None = None,
        slot_months: int | None = None,
    ) -> dict:
        """
        Purchase `product_id` using the prepaid wallet balance.
        `customer_email` + `slot_months` are only required for the
        synthetic `slot_chatgpt_business` product.
        """
        payload: dict[str, Any] = {"product_id": product_id, "quantity": quantity}
        if customer_email:
            payload["customer_email"] = customer_email
        if slot_months:
            payload["slot_months"] = slot_months
        return await self._post("/purchase", payload)


# ────────────────────────────────────────────────────────────────
#  GGSOMA Reseller Client
# ────────────────────────────────────────────────────────────────

class GGSomaClient:
    """Async HTTP client for the GGSOMA Partner API.

    Base URL : https://ggsoma.store/api/partner/v1
    Auth     : Bearer YOUR_API_KEY
    """

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        async with aiohttp.ClientSession(headers=self._headers, timeout=_DEFAULT_TIMEOUT) as s:
            async with s.get(url, params=params) as resp:
                data = await resp.json(content_type=None)
                if not resp.ok:
                    raise RuntimeError(f"GGSOMA GET {path} → {resp.status}: {data}")
                return data

    async def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        async with aiohttp.ClientSession(headers=self._headers, timeout=_DEFAULT_TIMEOUT) as s:
            async with s.post(url, json=payload) as resp:
                data = await resp.json(content_type=None)
                if not resp.ok or (isinstance(data, dict) and data.get("ok") is False):
                    raise RuntimeError(f"GGSOMA POST {path} → {resp.status}: {data}")
                return data

    async def get_products(self) -> list[dict]:
        """Return all products for this partner key."""
        data = await self._get("/catalog/products")
        if isinstance(data, dict):
            return data.get("data", [])
        return []

    async def get_balance(self) -> dict:
        """Return current partner wallet balance."""
        return await self._get("/usage")

    async def place_order(
        self,
        *,
        product_id: int | str,
        quantity: int = 1,
        external_order_id: str | None = None,
    ) -> dict:
        """Purchase product using the partner wallet balance."""
        try:
            p_id = int(product_id)
        except (ValueError, TypeError):
            p_id = str(product_id)

        payload: dict[str, Any] = {
            "productId": p_id,
            "quantity": quantity,
        }
        if external_order_id:
            payload["externalOrderId"] = str(external_order_id)

        return await self._post("/orders", payload)
