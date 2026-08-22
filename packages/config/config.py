import logging
import os
from abc import ABC
from typing import Final
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

_env_logger = logging.getLogger(__name__)


class EnvKeys(ABC):
    """Secure environment configuration with validation"""

    @staticmethod
    def _get_required(key: str) -> str:
        val = os.getenv(key)
        if not val:
            raise ValueError(f"Missing required environment variable: {key}")
        return val

    @staticmethod
    def _get_optional(key: str, default: str = "") -> str:
        val = os.getenv(key)
        return val if val and val.strip() else default

    # Telegram
    TOKEN: Final = os.getenv('TOKEN') or os.getenv('BOT_TOKEN') or _get_required('TOKEN')
    OWNER_ID: Final = int(_get_required('OWNER_ID'))

    # Database
    POSTGRES_DB: Final = _get_required("POSTGRES_DB")
    POSTGRES_USER: Final = _get_required("POSTGRES_USER")
    POSTGRES_PASSWORD: Final = _get_required("POSTGRES_PASSWORD")
    DB_PORT: Final = int(_get_optional("DB_PORT", "5432"))
    DB_DRIVER: Final = _get_optional("DB_DRIVER", "postgresql+asyncpg")
    POSTGRES_HOST: Final = _get_optional("POSTGRES_HOST", "localhost")

    # Redis
    REDIS_ENABLED: Final = _get_optional("REDIS_ENABLED", "1")
    REDIS_HOST: Final = _get_optional("REDIS_HOST", "localhost")
    REDIS_PORT: Final = int(_get_optional("REDIS_PORT", "6379"))
    REDIS_DB: Final = int(_get_optional("REDIS_DB", "0"))
    REDIS_PASSWORD: Final = _get_optional("REDIS_PASSWORD", "")

    # Payments
    TELEGRAM_PROVIDER_TOKEN: Final = _get_optional("TELEGRAM_PROVIDER_TOKEN", "")
    CRYPTO_PAY_TOKEN: Final = _get_optional("CRYPTO_PAY_TOKEN", "")
    STARS_PER_VALUE: Final = float(_get_optional("STARS_PER_VALUE", "0.91"))
    REFERRAL_PERCENT: Final = int(_get_optional("REFERRAL_PERCENT", "0"))
    REFERRAL_SIGNUP_BONUS: Final = _get_optional("REFERRAL_SIGNUP_BONUS", "0.1")
    PAY_CURRENCY: Final = _get_optional("PAY_CURRENCY", "RUB")
    PAYMENT_TIME: Final = int(_get_optional("PAYMENT_TIME", "1800"))
    MIN_AMOUNT: Final = int(_get_optional("MIN_AMOUNT", "20"))
    MAX_AMOUNT: Final = int(_get_optional("MAX_AMOUNT", "10000"))

    # Bybit Pay
    BYBIT_API_KEY: Final = _get_optional("BYBIT_API_KEY", "")
    BYBIT_API_SECRET: Final = _get_optional("BYBIT_API_SECRET", "")
    BYBIT_CHAIN: Final = _get_optional("BYBIT_CHAIN", "TRX")   # TRX=TRC20, ETH=ERC20, BSC=BEP20
    BYBIT_UID: Final = _get_optional("BYBIT_UID", "")          # Your Bybit UID for internal transfers
    BYBIT_MERCHANT_ID: Final = _get_optional("BYBIT_MERCHANT_ID", "")
    BYBIT_NOTIFY_URL: Final = _get_optional("BYBIT_NOTIFY_URL", "")

    # Binance Pay
    BINANCE_API_KEY: Final = _get_optional("BINANCE_API_KEY", "")
    BINANCE_API_SECRET: Final = _get_optional("BINANCE_API_SECRET", "")
    BINANCE_PAY_ID: Final = _get_optional("BINANCE_PAY_ID", "")  # Your Binance Pay ID for UID transfers

    # Admin Notification Bot (separate bot for payment approvals)
    NOTIFY_BOT_TOKEN: Final = _get_optional("NOTIFY_BOT_TOKEN", "")

    # Live Support — Forum supergroup (Topics enabled, bot is admin)
    SUPPORT_GROUP_ID: Final = int(_get_optional("SUPPORT_GROUP_ID", "0") or "0")

    # Alert Group (for general bot notifications like new users, payments)
    ALERT_GROUP_ID: Final = int(_get_optional("ALERT_GROUP_ID", "0") or "0")

    # Crypto Wallet Top-Up (BEP20 / TRC20)
    BEP20_WALLET: Final = _get_optional("BEP20_WALLET", "")
    TRC20_WALLET: Final = _get_optional("TRC20_WALLET", "")


    # Links / UI
    CHANNEL_URL: Final = _get_optional("CHANNEL_URL", "")
    CHANNEL_ID: Final = _get_optional("CHANNEL_ID", "")
    HELPER_ID: Final = _get_optional("HELPER_ID", "")
    RULES: Final = _get_optional("RULES", "")
    WEB_URL: Final = _get_optional("WEB_URL", "http://127.0.0.1:3000")  # e.g. https://yoursite.com

    # Locale & logs
    BOT_LOCALE: Final = _get_optional("BOT_LOCALE", "ru")
    BOT_LOGFILE: Final = _get_optional("BOT_LOGFILE", "logs/bot.log")
    BOT_AUDITFILE: Final = _get_optional("BOT_AUDITFILE", "logs/audit.log")
    LOG_TO_STDOUT: Final = _get_optional("LOG_TO_STDOUT", "1")
    LOG_TO_FILE: Final = _get_optional("LOG_TO_FILE", "1")
    DEBUG: Final = _get_optional("DEBUG", "0")
    REVIEWS_ENABLED: Final = _get_optional("REVIEWS_ENABLED", "1")

    # Web admin panel
    ADMIN_HOST: Final = _get_optional("ADMIN_HOST", _get_optional("MONITORING_HOST", "localhost"))
    ADMIN_PORT: Final = int(_get_optional("ADMIN_PORT", _get_optional("MONITORING_PORT", "9090")))
    ADMIN_USERNAME: Final = _get_optional("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: Final = _get_optional("ADMIN_PASSWORD", "admin")
    SECRET_KEY: Final = _get_optional("SECRET_KEY", "change-me-in-production")

    # Webhook
    WEBHOOK_ENABLED: Final = _get_optional("WEBHOOK_ENABLED", "0")
    WEBHOOK_URL: Final = _get_optional("WEBHOOK_URL", "")
    WEBHOOK_PATH: Final = _get_optional("WEBHOOK_PATH", "/webhook")
    WEBHOOK_SECRET: Final = _get_optional("WEBHOOK_SECRET", "")

    # Cleanup
    AUDIT_RETENTION_DAYS: Final = int(_get_optional("AUDIT_RETENTION_DAYS", "90"))
    PAYMENTS_RETENTION_DAYS: Final = int(_get_optional("PAYMENTS_RETENTION_DAYS", "90"))

    # ── Reseller APIs ──────────────────────────────────────────────────────────
    # ForkPixel Partner API  (https://forkpxelbot-production.up.railway.app/api/v1)
    FORKPIXEL_API_KEY: Final = _get_optional("FORKPIXEL_API_KEY", "")
    FORKPIXEL_BASE_URL: Final = _get_optional(
        "FORKPIXEL_BASE_URL", "https://forkpxelbot-production.up.railway.app/api/v1"
    )
    FORKPIXEL_SHOP_ID: Final = _get_optional("FORKPIXEL_SHOP_ID", "")
    FORKPIXEL_CURRENCY: Final = _get_optional("FORKPIXEL_CURRENCY", "usd")  # "usd" or "vnd"

    # CGPT Reseller API  (https://cgpt-active.pro/telegram/api)
    CGPT_API_KEY: Final = _get_optional("CGPT_API_KEY", "")
    CGPT_BASE_URL: Final = _get_optional(
        "CGPT_BASE_URL", "https://cgpt-active.pro/telegram/api"
    )

    # SafwanTiger Reseller API  (https://safwantigershopbot-production.up.railway.app/api)
    SAFWAN_API_KEY: Final = _get_optional(
        "SAFWAN_API_KEY", "stapi_25619395b079ce043546e72b5929a9652b6bae80007e6714cbe0cfec7eff89a3"
    )
    SAFWAN_BASE_URL: Final = _get_optional(
        "SAFWAN_BASE_URL", "https://safwantigershopbot-production.up.railway.app/api"
    )

    # Canboso Reseller API  (https://canboso.com/api)
    CANBOSO_API_KEY: Final = _get_optional(
        "CANBOSO_API_KEY", "tgb_286aee3c314ed61da656aab4a5267901916f7e9d48fdf70e"
    )
    CANBOSO_BASE_URL: Final = _get_optional(
        "CANBOSO_BASE_URL", "https://canboso.com/api/v2/telegram-buyer"
    )

    # GGSOMA Reseller API  (https://ggsoma.store/api/partner/v1)
    GGSOMA_API_KEY: Final = _get_optional(
        "GGSOMA_API_KEY", "sk_live_237f47e759584bd9ed9dce88c800c3adf102d886d7a7ae2ea5db2083d5d08190"
    )
    GGSOMA_BASE_URL: Final = _get_optional(
        "GGSOMA_BASE_URL", "https://ggsoma.store/api/partner/v1"
    )

    # Reseller global settings
    RESELLER_MARKUP_PERCENT: Final = float(_get_optional("RESELLER_MARKUP_PERCENT", "30"))
    RESELLER_SYNC_INTERVAL: Final = int(_get_optional("RESELLER_SYNC_INTERVAL", "1800"))  # seconds

    DATABASE_URL: Final = (
        f"postgresql+asyncpg://{POSTGRES_USER}:{quote_plus(POSTGRES_PASSWORD)}"
        f"@{POSTGRES_HOST}:{DB_PORT}/{POSTGRES_DB}"
    )

    # Startup validation
    if ADMIN_PASSWORD == "admin":
        _env_logger.warning(
            "SECURITY: ADMIN_PASSWORD is set to the default value 'admin'. "
            "Change it immediately via the ADMIN_PASSWORD env variable."
        )
    if SECRET_KEY == "change-me-in-production":
        _env_logger.warning(
            "SECURITY: SECRET_KEY is set to the default value. "
            "Set a strong random SECRET_KEY env variable for session security."
        )
    if int(MIN_AMOUNT) >= int(MAX_AMOUNT):
        _env_logger.warning(
            "CONFIG: MIN_AMOUNT (%s) >= MAX_AMOUNT (%s). "
            "Payment amounts will always be rejected.", MIN_AMOUNT, MAX_AMOUNT
        )
    if int(REFERRAL_PERCENT) < 0 or int(REFERRAL_PERCENT) > 99:
        _env_logger.warning(
            "CONFIG: REFERRAL_PERCENT=%s is outside the valid range [0, 99].",
            REFERRAL_PERCENT,
        )
