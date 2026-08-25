import httpx
import logging
import ipaddress
from typing import Optional, Dict
from datetime import datetime, timedelta
from fastapi import Request

logger = logging.getLogger(__name__)

# In-memory GeoIP cache: ip -> (data_dict, expiry_datetime)
_GEO_CACHE: Dict[str, tuple[dict, datetime]] = {}
CACHE_TTL = timedelta(hours=24)

# Well-known Nepal IP ranges/ASNs or test checks
NEPAL_COUNTRY_CODES = {"NP", "NPL"}


def get_client_ip(request: Request) -> str:
    """
    Extract the real client IP from incoming request headers,
    prioritizing reverse-proxy headers (Cloudflare, Caddy, Nginx).
    """
    # 1. Cloudflare header
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()

    # 2. X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # 3. X-Forwarded-For header (may contain comma-separated IPs, leftmost is client)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_candidate = forwarded_for.split(",")[0].strip()
        if client_candidate:
            return client_candidate

    # 4. Fallback to client host
    if request.client and request.client.host:
        return request.client.host.strip()

    return "127.0.0.1"


def is_private_or_loopback(ip: str) -> bool:
    """Check if an IP address is private, loopback, or reserved."""
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_link_local
    except ValueError:
        return False


async def lookup_ip_geo(ip: str, request_headers: Optional[dict] = None) -> dict:
    """
    Lookup country information for a given IP.
    Returns:
        {
            "ip": str,
            "country_code": str (e.g. 'NP', 'US'),
            "country_name": str,
            "is_nepal": bool,
            "city": Optional[str],
            "source": str
        }
    """
    now = datetime.utcnow()

    # 1. Check if Cloudflare header directly provides country code
    if request_headers:
        cf_country = request_headers.get("cf-ipcountry", "").upper().strip()
        if cf_country and len(cf_country) == 2 and cf_country != "XX":
            is_np = cf_country in NEPAL_COUNTRY_CODES
            return {
                "ip": ip,
                "country_code": cf_country,
                "country_name": "Nepal" if is_np else cf_country,
                "is_nepal": is_np,
                "city": None,
                "source": "cloudflare_header"
            }

        # Header override for testing if enabled
        test_country = request_headers.get("x-test-country", "").upper().strip()
        if test_country:
            is_np = test_country in NEPAL_COUNTRY_CODES
            return {
                "ip": ip,
                "country_code": test_country,
                "country_name": "Nepal" if is_np else test_country,
                "is_nepal": is_np,
                "city": "Test",
                "source": "test_header"
            }

    # 2. Check in-memory cache
    if ip in _GEO_CACHE:
        cached_data, expiry = _GEO_CACHE[ip]
        if now < expiry:
            return cached_data

    # 3. Handle private / local IPs (e.g. localhost during dev)
    if is_private_or_loopback(ip):
        res = {
            "ip": ip,
            "country_code": "LOCAL",
            "country_name": "Local Network",
            "is_nepal": False,
            "city": "Localhost",
            "source": "private_ip"
        }
        _GEO_CACHE[ip] = (res, now + timedelta(minutes=10))
        return res

    # 4. Remote Geo-IP lookup with fast fallback providers
    providers = [
        f"https://ipwho.is/{ip}",
        f"https://ipapi.co/{ip}/json/",
    ]

    for url in providers:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(url, headers={"User-Agent": "KaliDigitalStore-GeoService/1.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    # ipwho.is returns { "country_code": "NP", "country": "Nepal", "city": "Kathmandu", "success": true }
                    # ipapi.co returns { "country_code": "NP", "country_name": "Nepal", "city": "Kathmandu" }
                    country_code = (
                        data.get("country_code") or 
                        data.get("country_code_iso3") or 
                        data.get("countryCode") or 
                        ""
                    ).upper().strip()

                    country_name = data.get("country") or data.get("country_name") or country_code
                    city = data.get("city")
                    is_np = country_code in NEPAL_COUNTRY_CODES

                    result = {
                        "ip": ip,
                        "country_code": country_code or "UNKNOWN",
                        "country_name": country_name or "Unknown",
                        "is_nepal": is_np,
                        "city": city,
                        "source": "remote_lookup"
                    }
                    _GEO_CACHE[ip] = (result, now + CACHE_TTL)
                    return result
        except Exception as e:
            logger.warning(f"GeoIP provider {url} failed for IP {ip}: {e}")
            continue

    # Default fallback if lookup fails
    fallback_res = {
        "ip": ip,
        "country_code": "UNKNOWN",
        "country_name": "Unknown",
        "is_nepal": False,
        "city": None,
        "source": "fallback"
    }
    _GEO_CACHE[ip] = (fallback_res, now + timedelta(minutes=30))
    return fallback_res


async def is_nepal_client(request: Request) -> bool:
    """Convenience helper to check if a FastAPI request originates from Nepal."""
    ip = get_client_ip(request)
    geo = await lookup_ip_geo(ip, request.headers)
    return bool(geo.get("is_nepal", False))
