import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from collections import defaultdict

from apps.telegram_bot.core.logging import logger


class MetricsCollector:
    """Metrics collector for analytics and monitoring."""

    def __init__(self):
        self.events: Dict[str, int] = defaultdict(int)
        self.timings: Dict[str, List[float]] = defaultdict(list)
        self.errors: Dict[str, int] = defaultdict(int)
        self.conversions: Dict[str, Dict] = {}
        self.start_time = datetime.now()
        self.last_flush = datetime.now()

    def track_event(self, event_name: str, user_id: Optional[int] = None,
                    metadata: Optional[Dict] = None):
        """Track an event occurrence."""
        self.events[event_name] += 1

    def track_timing(self, operation: str, duration: float):
        """Track operation execution time."""
        self.timings[operation].append(duration)
        # Keep only the last 1000 measurements
        if len(self.timings[operation]) > 1000:
            self.timings[operation] = self.timings[operation][-1000:]

    def track_error(self, error_type: str, error_msg: str = None):
        """Track an error occurrence."""
        self.errors[error_type] += 1
        if error_msg:
            logger.error(f"Metric error [{error_type}]: {error_msg}")

    def track_conversion(self, funnel: str, step: str, user_id: int):
        """Track conversion funnel progress."""
        if funnel not in self.conversions:
            self.conversions[funnel] = defaultdict(set)
        self.conversions[funnel][step].add(user_id)

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Return a summary of all collected metrics."""
        uptime = (datetime.now() - self.start_time).total_seconds()

        avg_timings = {}
        for op, times in self.timings.items():
            if times:
                avg_timings[op] = {
                    "avg": sum(times) / len(times),
                    "min": min(times),
                    "max": max(times),
                    "count": len(times),
                }

        conversion_rates = {}
        for funnel, steps in self.conversions.items():
            if funnel == "purchase_funnel":
                view_shop = len(steps.get("view_shop", set()))
                view_item = len(steps.get("view_item", set()))
                purchase = len(steps.get("purchase", set()))
                conversion_rates[funnel] = {
                    "view_to_item": (view_item / view_shop * 100) if view_shop else 0,
                    "item_to_purchase": (purchase / view_item * 100) if view_item else 0,
                    "total": (purchase / view_shop * 100) if view_shop else 0,
                }

        return {
            "uptime_seconds": uptime,
            "events": dict(self.events),
            "timings": avg_timings,
            "errors": dict(self.errors),
            "conversions": conversion_rates,
            "timestamp": datetime.now().isoformat(),
        }

    def export_to_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []

        for event, count in self.events.items():
            clean = event.replace("-", "_").replace("/", "_").replace(" ", "_")
            lines.append(f'bot_events_total{{event="{clean}"}} {count}')

        for error, count in self.errors.items():
            clean = error.replace("-", "_").replace("/", "_").replace(" ", "_")
            lines.append(f'bot_errors_total{{type="{clean}"}} {count}')

        for op, times in self.timings.items():
            if times:
                avg_time = sum(times) / len(times)
                clean = op.replace("-", "_").replace("/", "_").replace(" ", "_")
                lines.append(f'bot_operation_duration_seconds{{operation="{clean}"}} {avg_time}')

        uptime = (datetime.now() - self.start_time).total_seconds()
        lines.append(f"bot_uptime_seconds {uptime}")

        return "\n".join(lines)


class AnalyticsMiddleware:
    """Middleware that records per-event metrics."""

    def __init__(self, metrics: MetricsCollector):
        self.metrics = metrics

    async def __call__(self, handler, event, data):
        start_time = time.time()
        user_id = None
        event_type = None

        try:
            if hasattr(event, "from_user") and event.from_user:
                user_id = event.from_user.id
        except AttributeError:
            pass

        try:
            text_value = getattr(event, "text", None)
            if text_value is not None and text_value != "":
                event_type = "message"
                if text_value.startswith("/"):
                    event_type = f"command_{text_value.split()[0][1:]}"
            elif hasattr(event, "data"):
                event_type = event.data.split("_")[0] if event.data else "unknown"
        except AttributeError:
            if hasattr(event, "data"):
                event_type = event.data.split("_")[0] if event.data else "unknown"

        if event_type:
            self.metrics.track_event(f"bot_{event_type}", user_id)

        try:
            result = await handler(event, data)
            duration = time.time() - start_time
            if event_type:
                self.metrics.track_timing(f"handler_{event_type}", duration)
            return result
        except Exception as e:
            self.metrics.track_error(type(e).__name__, str(e))
            raise


# ── Global singleton ──────────────────────────────────────────────────────── #

_metrics_collector: Optional[MetricsCollector] = None


def get_metrics() -> Optional[MetricsCollector]:
    """Return the global MetricsCollector instance (None if not initialised)."""
    return _metrics_collector


def init_metrics() -> MetricsCollector:
    """Initialise and return the global MetricsCollector."""
    global _metrics_collector
    _metrics_collector = MetricsCollector()
    logger.info("Metrics collector initialized")
    return _metrics_collector
