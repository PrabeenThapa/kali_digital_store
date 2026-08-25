from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from packages.database.engine import Database
from packages.database.models.main import register_models
from packages.config.config import EnvKeys

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up API, initializing database models...")
    await register_models()
    yield
    # Shutdown: drain the async connection pool cleanly
    logger.info("Shutting down API, disposing database pool...")
    await Database().dispose()
        
app = FastAPI(
    title="Digital Commerce API",
    description="API for the premium Next.js SaaS web platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS config for the Next.js frontend
import os

cors_origins_env = os.getenv("CORS_ORIGINS", "")
if cors_origins_env:
    allowed_origins = [orig.strip() for orig in cors_origins_env.split(",") if orig.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://.*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.get("/health")
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "API is running."}


from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.dependencies import get_db

@app.get("/api/settings/public")
async def get_public_settings_root(db: AsyncSession = Depends(get_db)):
    from packages.database.models.main import BotSettings
    from sqlalchemy import select

    keys = [
        "mantra_bar_text", "hero_title", "hero_subtitle",
        "announcement_banner_enabled", "announcement_banner_text", "announcement_banner_type",
        "nepal_coming_soon", "nepal_coming_soon_text", "nepal_qr_url", "nepal_qr_title", "npr_exchange_rate"
    ]
    res = await db.execute(select(BotSettings).where(BotSettings.key.in_(keys)))
    settings = {s.key: s.value for s in res.scalars().all()}

    return {
        "mantra_bar_text": settings.get("mantra_bar_text") or "॥ ॐ क्रीं कालिकायै नमः • दिव्य डिजिटल शक्ति एवं अचूक सुरक्षा ॥",
        "hero_title": settings.get("hero_title") or "KALI DIGITAL STORE",
        "hero_subtitle": settings.get("hero_subtitle") or "Genuine ChatGPT Plus, Claude, Gemini, Canva Pro, JetBrains, VPNs, and Dev API tokens with instant cryptographic delivery and eternal warranty.",
        "announcement_banner_enabled": settings.get("announcement_banner_enabled", "false").lower() == "true",
        "announcement_banner_text": settings.get("announcement_banner_text") or "",
        "announcement_banner_type": settings.get("announcement_banner_type") or "info",
        "nepal_coming_soon": settings.get("nepal_coming_soon", "false").lower() == "true",
        "nepal_coming_soon_text": settings.get("nepal_coming_soon_text") or "",
        "nepal_qr_url": settings.get("nepal_qr_url") or "",
        "nepal_qr_title": settings.get("nepal_qr_title") or "eSewa / Khalti / Fonepay Direct QR",
        "npr_exchange_rate": float(settings.get("npr_exchange_rate", "135.0")),
    }


# Register Routers
from apps.api.routers import auth, catalog, user, support, payments, admin, geo

app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(user.router)
app.include_router(support.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(geo.router)

