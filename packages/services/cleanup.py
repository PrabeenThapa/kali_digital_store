import asyncio
import logging
from datetime import datetime, timedelta, timezone, time as dt_time

from sqlalchemy import delete

logger = logging.getLogger(__name__)


class CleanupManager:
    """Periodically removes old audit-log entries and expired payment records."""

    def __init__(self):
        self.tasks: list[asyncio.Task] = []
        self.running = False

    async def start(self):
        logger.info("Starting cleanup manager...")
        self.running = True
        self.tasks.append(asyncio.create_task(self._safe_run(self.daily_cleanup)))

    async def stop(self):
        self.running = False
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("Cleanup manager stopped")

    async def _safe_run(self, coro_func):
        while self.running:
            try:
                await coro_func()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Cleanup task error: {e}", exc_info=True)
                await asyncio.sleep(30)

    async def daily_cleanup(self):
        """Run once a day at 04:00 UTC, pruning old records."""
        while self.running:
            now = datetime.now(timezone.utc)
            target = datetime.combine(now.date(), dt_time(4, 0), tzinfo=timezone.utc)
            if now >= target:
                target += timedelta(days=1)
            await asyncio.sleep((target - now).total_seconds())

            try:
                from packages.database.engine import Database
                from packages.database.models.main import AuditLog, Payments
                from packages.config.config import EnvKeys
                from packages.database.methods.audit import log_audit

                audit_cutoff = datetime.now(timezone.utc) - timedelta(days=EnvKeys.AUDIT_RETENTION_DAYS)
                payments_cutoff = datetime.now(timezone.utc) - timedelta(days=EnvKeys.PAYMENTS_RETENTION_DAYS)

                async with Database().session() as s:
                    audit_result = await s.execute(
                        delete(AuditLog).where(AuditLog.timestamp < audit_cutoff)
                    )
                    payments_result = await s.execute(
                        delete(Payments).where(
                            Payments.status.in_(["pending", "failed"]),
                            Payments.created_at < payments_cutoff,
                        )
                    )

                await log_audit(
                    "daily_cleanup",
                    details=(
                        f"audit_deleted={audit_result.rowcount}, "
                        f"payments_deleted={payments_result.rowcount}"
                    ),
                )
                logger.info(
                    f"Daily cleanup: audit={audit_result.rowcount}, "
                    f"payments={payments_result.rowcount}"
                )

            except Exception as e:
                logger.error(f"Daily cleanup failed: {e}", exc_info=True)
