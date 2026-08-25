from fastapi import APIRouter, Request
from packages.services.geo_service import get_client_ip, lookup_ip_geo

router = APIRouter(prefix="/api/geo", tags=["Geolocation"])

@router.get("")
@router.get("/lookup")
async def get_geolocation(request: Request):
    """
    Returns client IP, detected country, city, and whether the client is in Nepal.
    Used by the frontend to enforce region-specific views (e.g. hiding crypto for Nepal).
    """
    client_ip = get_client_ip(request)
    geo_data = await lookup_ip_geo(client_ip, request.headers)
    return geo_data
