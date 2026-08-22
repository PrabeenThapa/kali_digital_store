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
async def health_check():
    return {"status": "ok", "message": "API is running."}

# Register Routers
from apps.api.routers import auth, catalog, user, support, payments, admin

app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(user.router)
app.include_router(support.router)
app.include_router(payments.router)
app.include_router(admin.router)
