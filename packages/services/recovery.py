import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update, text

logger = logging.getLogger(__name__)


class RecoveryManager:
    """Disaster-recovery manager: retries pending payments and monitors system health."""

    def __init__(self, bot):
        self.bot = bot
        self.recovery_tasks: list[asyncio.Task] = []
        self.running = False

    async def start(self):
        """Launch background recovery tasks."""
        logger.info("Starting recovery manager...")
        self.running = True
        self.recovery_tasks.append(
            asyncio.create_task(self._safe_run(self.recover_pending_payments))
        )
        self.recovery_tasks.append(
            asyncio.create_task(self._safe_run(self.periodic_health_check))
        )

    async def stop(self):
        """Cancel and await all background tasks."""
        self.running = False
        for task in self.recovery_tasks:
            task.cancel()
        await asyncio.gather(*self.recovery_tasks, return_exceptions=True)
        logger.info("Recovery manager stopped")

    async def _safe_run(self, coro_func, *args):
        """Run a coroutine function in a loop, restarting after errors."""
        while self.running:
            try:
                await coro_func(*args)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Recovery task error: {e}", exc_info=True)
                await asyncio.sleep(30)

    async def recover_pending_payments(self):
        """Poll for pending CryptoPay invoices and finalise any that were paid."""
        from packages.database.engine import Database
        from packages.database.models import Payments, PaymentStatus, PaymentProvider

        while self.running:
            try:
                payment_copies = []
                async with Database().session() as s:
                    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
                    result = await s.execute(
                        select(Payments).where(
                            Payments.status == PaymentStatus.PENDING,
                            Payments.created_at < cutoff,
                            Payments.provider == PaymentProvider.CRYPTOPAY,
                        )
                    )
                    for p in result.scalars().all():
                        payment_copies.append({
                            "id": p.id,
                            "provider": p.provider,
                            "external_id": p.external_id,
                            "user_id": p.user_id,
                            "amount": p.amount,
                            "currency": p.currency,
                        })

                for pc in payment_copies:
                    await self._check_and_process_payment(pc)

            except Exception as e:
                logger.error(f"Error recovering payments: {e}")

            await asyncio.sleep(300)

    async def _check_and_process_payment(self, payment: dict | object):
        """Verify and finalise a single payment record."""
        from packages.database.methods.transactions import process_payment_with_referral
        from packages.config.config import EnvKeys
        from packages.services.payment import CryptoPayAPI
        from apps.telegram_bot.i18n import localize
        from packages.database.models import PaymentProvider

        if isinstance(payment, dict):
            p_id = payment.get("id")
            p_provider = payment.get("provider")
            p_external_id = payment.get("external_id")
            p_user_id = payment.get("user_id")
            p_amount = payment.get("amount")
            p_currency = payment.get("currency")
        else:
            p_id = getattr(payment, "id", None)
            p_provider = getattr(payment, "provider", None)
            p_external_id = getattr(payment, "external_id", None)
            p_user_id = getattr(payment, "user_id", None)
            p_amount = getattr(payment, "amount", None)
            p_currency = getattr(payment, "currency", None)

        try:
            if p_provider == PaymentProvider.CRYPTOPAY:
                crypto = CryptoPayAPI()
                info = await crypto.get_invoice(p_external_id)
                if info.get("status") == "paid":
                    success, _ = await process_payment_with_referral(
                        user_id=p_user_id,
                        amount=p_amount,
                        provider=p_provider,
                        external_id=p_external_id,
                        referral_percent=EnvKeys.REFERRAL_PERCENT,
                    )
                    if success:
                        logger.info(f"Recovered payment {p_external_id}")
                        try:
                            await self.bot.send_message(
                                p_user_id,
                                localize("payments.topped_simple", amount=p_amount, currency=p_currency),
                            )
                        except Exception as e:
                            logger.error(f"Failed to notify user {p_user_id}: {e}")
                elif info.get("status") in ["expired", "failed"]:
                    await self._mark_payment_failed(p_id)
        except Exception as e:
            logger.error(f"Error processing payment {p_id}: {e}")

    async def _mark_payment_failed(self, payment_id: int):
        """Set a payment's status to 'failed'."""
        from packages.database.engine import Database
        from packages.database.models import Payments, PaymentStatus

        async with Database().session() as s:
            await s.execute(
                update(Payments)
                .where(Payments.id == payment_id)
                .values(status=PaymentStatus.FAILED)
            )

    async def periodic_health_check(self):
        """Periodically verify database, Redis, and bot connectivity."""
        from packages.database.engine import Database

        while self.running:
            try:
                async with Database().session() as s:
                    await s.execute(text("SELECT 1"))

                from apps.telegram_bot.cache.manager import get_cache_manager
                cache = get_cache_manager()
                if cache:
                    await cache.check_health()
                    await cache.set("health:check", "ok", ttl=60)

                me = await self.bot.get_me()
                logger.debug(f"Health check passed: Bot @{me.username} is alive")

            except Exception as e:
                logger.error(f"Health check failed: {e}")

            await asyncio.sleep(60)
