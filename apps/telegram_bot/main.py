import asyncio
import logging
import sys
import json
from pathlib import Path
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from packages.database.methods import check_category_cached
from apps.telegram_bot.handlers.admin.shop_management_states import init_stats_cache
from packages.config.config import EnvKeys
from apps.telegram_bot.handlers import register_all_handlers
from packages.database.models import register_models
from apps.telegram_bot.core.logging import configure_logging
from apps.telegram_bot.middleware import setup_rate_limiting, RateLimitConfig
from apps.telegram_bot.middleware.security import SecurityMiddleware, AuthenticationMiddleware
from apps.telegram_bot.middleware.force_join import ForceJoinMiddleware
from apps.telegram_bot.cache.manager import init_cache_manager, get_cache_manager
from apps.telegram_bot.cache.scheduler import CacheScheduler
from apps.telegram_bot.cache.storage import get_redis_storage
from packages.services import RecoveryManager, CleanupManager
from apps.telegram_bot.core.metrics import init_metrics, get_metrics, AnalyticsMiddleware
from packages.database.engine import Database as _Database

# Global variables for components
recovery_manager = None
cleanup_manager = None
admin_server = None
cache_scheduler = None
webhook_active = False

# Global middleware instances for access from handlers
security_middleware: SecurityMiddleware = None
auth_middleware: AuthenticationMiddleware = None
rate_limit_middleware = None
force_join_middleware = None


async def reseller_sync_loop(bot):
    """Background task to periodically sync reseller APIs."""
    from packages.services.reseller import sync_all_sources
    from apps.telegram_bot.utils.notify import notify_group
    
    interval = 120 # Auto-sync every 120 seconds
    while True:
        try:
            logging.info("Starting background reseller sync...")
            results = await sync_all_sources()
            logging.info(f"Background reseller sync complete: {results}")
            
            # Check for new products
            new_products = []
            added_stock = []
            for src, res in results.items():
                if res and "new_products" in res and res["new_products"]:
                    new_products.extend(res["new_products"])
                if res and "added_stock" in res and res["added_stock"]:
                    added_stock.extend(res["added_stock"])
                    
            if new_products:
                lines = [f"📦 <b>{p['name']}</b> - ${p['price']}" for p in new_products]
                msg = "🎉 <b>New Products Arrived!</b>\n\n" + "\n".join(lines) + "\n\n<i>Check them out in the shop!</i>"
                await notify_group(bot, msg)
                from apps.telegram_bot.utils.notify import broadcast_to_all_users
                await broadcast_to_all_users(bot, msg)
                
            if added_stock:
                from aiogram.utils.keyboard import InlineKeyboardBuilder
                from apps.telegram_bot.utils.menu_icons import get_menu_icons, format_icon_html
                icons = await get_menu_icons()
                header_icon = format_icon_html("notify_header", "💥", icons)
                added_icon = format_icon_html("notify_added", "➕", icons)
                stock_icon = format_icon_html("notify_stock", "📦", icons)
                price_icon = format_icon_html("notify_price", "💸", icons)
                buy_custom_id = icons.get("notify_buy_btn")

                me = await bot.get_me()
                for p in added_stock:
                    kb = InlineKeyboardBuilder()
                    safe_name = p['name'].replace(' ', '_')[:50]
                    if buy_custom_id:
                        kb.button(
                            text="Buy now",
                            url=f"https://t.me/{me.username}?start=item_{safe_name}",
                            icon_custom_emoji_id=str(buy_custom_id)
                        )
                    else:
                        kb.button(
                            text="🛒 Buy now",
                            url=f"https://t.me/{me.username}?start=item_{safe_name}"
                        )
                    
                    msg = (
                        f"{header_icon} <b>{p['name']}</b>\n"
                        f"{added_icon} Added: {p['added']}\n"
                        f"{stock_icon} Current stock: {p['current_stock']}\n"
                        f"{price_icon} Price: ${p['price']:.2f}"
                    )
                    await notify_group(bot, msg, reply_markup=kb.as_markup())
                    
                    from apps.telegram_bot.utils.notify import broadcast_to_all_users
                    await broadcast_to_all_users(bot, msg, reply_markup=kb.as_markup())
                    await asyncio.sleep(2.0)
                
        except Exception as e:
            logging.error(f"Error in background reseller sync task: {e}")
        await asyncio.sleep(interval)


async def discussion_groups_broadcaster_loop(bot: Bot):
    """Background loop to periodically auto-post messages to active discussion groups."""
    from apps.telegram_bot.utils.discussion_groups import get_discussion_config
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    while True:
        try:
            config = await get_discussion_config()
            is_enabled = config.get("is_enabled", False)
            interval_minutes = max(1, config.get("interval_minutes", 1))
            groups = [g for g in config.get("groups", []) if g.get("enabled", True)]
            text = config.get("auto_message_text", "").strip()

            if is_enabled and groups and text:
                me = await bot.get_me()
                kb = InlineKeyboardBuilder()
                kb.button(text="🛒 Visit Shop Bot", url=f"https://t.me/{me.username}")

                for g in groups:
                    target = g.get("chat_id") or g.get("target")
                    if not target:
                        continue
                    try:
                        await bot.send_message(
                            chat_id=target,
                            text=text,
                            parse_mode="HTML",
                            reply_markup=kb.as_markup()
                        )
                        logging.info(f"Auto-posted message to group: {target}")
                    except Exception as e:
                        logging.warning(f"Could not auto-post to group {target}: {e}")

            await asyncio.sleep(interval_minutes * 60)
        except Exception as e:
            logging.error(f"Error in discussion groups broadcaster loop: {e}")
            await asyncio.sleep(60)


async def __on_start_up(dp: Dispatcher, bot: Bot) -> None:
    """Initialize bot on startup"""
    global recovery_manager, admin_server

    # Registration of handlers and models
    register_all_handlers(dp)
    await register_models()

    # Initialize reseller APIs
    from packages.services.reseller import ensure_sources_exist
    await ensure_sources_exist()
    _reseller_sync_task = asyncio.create_task(reseller_sync_loop(bot))
    _discussion_broadcaster_task = asyncio.create_task(discussion_groups_broadcaster_loop(bot))
    
    # Seed categories
    from apps.telegram_bot.utils.category_resolver import seed_known_categories
    await seed_known_categories()

    # Add security middleware (using global instances for handler access)
    global security_middleware, auth_middleware, force_join_middleware
    security_middleware = SecurityMiddleware()
    auth_middleware = AuthenticationMiddleware()
    force_join_middleware = ForceJoinMiddleware()
    await auth_middleware.load_blocked_users()

    # Setting Rate Limiting (shares auth_middleware's role cache)
    rate_config = RateLimitConfig(
        global_limit=30,
        global_window=60,
        ban_duration=300,
        admin_bypass=True,
        action_limits={
            'payment': (10, 60),  # 10 times per minute
            'shop_view': (60, 60),  # 60 times per minute
            'buy_item': (5, 60),  # 5 purchases per minute
            'top_up': (5, 300),  # 5 top-ups in 5 minutes
        }
    )
    global rate_limit_middleware
    rate_limit_middleware = setup_rate_limiting(dp, rate_config, auth_middleware=auth_middleware)

    # Initializing metrics
    metrics = init_metrics()
    analytics_middleware = AnalyticsMiddleware(metrics)

    # Middleware execution order (last registered executes first):
    # SecurityMiddleware -> AuthenticationMiddleware -> ForceJoinMiddleware -> AnalyticsMiddleware -> RateLimitMiddleware -> Handler
    dp.message.middleware(analytics_middleware)
    dp.callback_query.middleware(analytics_middleware)

    dp.message.middleware(force_join_middleware)
    dp.callback_query.middleware(force_join_middleware)

    dp.message.middleware(auth_middleware)
    dp.callback_query.middleware(auth_middleware)

    dp.message.middleware(security_middleware)
    dp.callback_query.middleware(security_middleware)

    logging.info("Security middleware initialized")

    storage = get_redis_storage()
    if isinstance(storage, RedisStorage):
        # Use the same Redis for caching
        await init_cache_manager(storage.redis)

        # Initialize the statistics cache
        init_stats_cache()

        # Warm up critical caches at startup
        await warm_up_critical_caches()

        logging.info("Cache system initialized and warmed up")

        # Start cache scheduler only when Redis is available
        global cache_scheduler
        cache_scheduler = CacheScheduler()
        await cache_scheduler.start()
    else:
        logging.warning("Redis not available - caching disabled")

    # Start the recovery system
    recovery_manager = RecoveryManager(bot)
    await recovery_manager.start()

    # Start the cleanup manager
    cleanup_manager = CleanupManager()
    await cleanup_manager.start()

    # Start the admin web server
    import uvicorn
    from apps.telegram_bot.web import create_admin_app

    admin_app = create_admin_app()
    config = uvicorn.Config(
        admin_app,
        host=EnvKeys.ADMIN_HOST,
        port=EnvKeys.ADMIN_PORT,
        log_level="warning",
    )
    admin_server = uvicorn.Server(config)
    _admin_server_task = asyncio.create_task(admin_server.serve())

    logging.info(f"Recovery and admin panel initialized on {EnvKeys.ADMIN_HOST}:{EnvKeys.ADMIN_PORT}")


async def __on_shutdown(dp: Dispatcher, bot: Bot) -> None:
    """Initialize bot shutdown"""
    global recovery_manager, cleanup_manager, admin_server, webhook_active

    logging.info("Starting shutdown...")

    # Create a data directory if it does not exist
    Path("data").mkdir(exist_ok=True)

    # Saving metrics
    metrics = get_metrics()
    if metrics:
        summary = metrics.get_metrics_summary()
        with open("data/final_metrics.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    # Recovery Manager Stop
    if recovery_manager:
        await recovery_manager.stop()

    # Cleanup Manager Stop
    if cleanup_manager:
        await cleanup_manager.stop()

    # Delete webhook if it was active
    if webhook_active:
        try:
            await bot.delete_webhook()
        except Exception as e:
            logging.error(f"Failed to delete webhook: {e}")

    # Admin server stop
    if admin_server:
        admin_server.should_exit = True

    # Close CryptoPay shared HTTP session
    from packages.services.payment import CryptoPayAPI
    await CryptoPayAPI.close_session()

    # Close database engine
    await _Database().dispose()

    logging.info("Shutdown completed")


async def warm_up_critical_caches():
    """Warming of critical caches at startup"""
    from packages.database.methods.read import (
        get_user_count_cached,
        select_admins_cached
    )

    cache_manager = get_cache_manager()
    if not cache_manager:
        return

    try:
        # Warming up the base stats
        await get_user_count_cached()
        await select_admins_cached()

        # Warming up popular categories and products
        from packages.database.methods import query_categories
        categories = await query_categories(limit=5)
        for category in categories:
            await check_category_cached(category)

        logging.info("Critical caches warmed up successfully")
    except Exception as e:
        logging.error(f"Failed to warm up caches: {e}")


async def start_bot() -> None:
    """Start the bot with enhanced security and monitoring"""

    # Logging Configuration
    configure_logging(
        console=EnvKeys.LOG_TO_STDOUT == "1",
        debug=EnvKeys.DEBUG == "1"
    )

    # Logging level setting
    log_level = logging.DEBUG if EnvKeys.DEBUG == "1" else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Disconnect unnecessary logs from aiogram
    logging.getLogger("aiogram.dispatcher").setLevel(logging.WARNING)
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("aiogram.middlewares").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)

    # Checking critical environment variables
    if not EnvKeys.TOKEN:
        logging.critical("Bot token not set! Please set TOKEN environment variable.")
        sys.exit(1)

    if not EnvKeys.OWNER_ID:
        logging.critical("Owner ID not set! Please set OWNER_ID environment variable.")
        sys.exit(1)

    # Retrieve storage (Redis or Memory)
    storage = get_redis_storage() or MemoryStorage()
    if isinstance(storage, MemoryStorage):
        logging.warning(
            "Using MemoryStorage - FSM states will be lost on restart! "
            "Consider setting up Redis for production."
        )

    # Creating a dispatcher
    dp = Dispatcher(storage=storage)

    # Create and run the bot
    async with Bot(
            token=EnvKeys.TOKEN,
            default=DefaultBotProperties(
                parse_mode="HTML",
                link_preview_is_disabled=False,
                protect_content=False,
            ),
    ) as bot:
        # Getting information about the bot
        bot_info = await bot.get_me()
        logging.info(f"Starting bot: @{bot_info.username} (ID: {bot_info.id})")

        # Initialization at startup
        await __on_start_up(dp, bot)

        allowed_updates = dp.resolve_used_update_types()

        try:
            global webhook_active
            if EnvKeys.WEBHOOK_ENABLED == "1" and EnvKeys.WEBHOOK_URL:
                # Webhook mode
                webhook_path = EnvKeys.WEBHOOK_PATH or "/webhook"
                webhook_url = f"{EnvKeys.WEBHOOK_URL}{webhook_path}"

                await bot.set_webhook(
                    url=webhook_url,
                    secret_token=EnvKeys.WEBHOOK_SECRET or None,
                    allowed_updates=allowed_updates,
                )
                webhook_active = True
                logging.info(f"Webhook set: {webhook_url}")

                # Add webhook handler to admin app
                from starlette.requests import Request
                from starlette.responses import Response

                async def webhook_handler(request: Request) -> Response:
                    """Process incoming webhook updates"""
                    # Verify secret token
                    if EnvKeys.WEBHOOK_SECRET:
                        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
                        if token != EnvKeys.WEBHOOK_SECRET:
                            return Response(status_code=403)

                    body = await request.body()
                    from aiogram.types import Update
                    update = Update.model_validate_raw(body)
                    await dp.feed_update(bot=bot, update=update)
                    return Response(status_code=200)

                from starlette.routing import Route
                # We need to add the route to the admin app before it starts
                # The admin_server is already running, so we patch the app
                admin_server.config.app.routes.append(
                    Route(webhook_path, webhook_handler, methods=["POST"])
                )

                # Keep the process running
                await asyncio.Event().wait()
            else:
                # Polling mode
                await dp.start_polling(
                    bot,
                    allowed_updates=allowed_updates,
                    handle_signals=True,
                )
        except Exception as e:
            logging.error(f"Bot error: {e}")
            raise
        finally:
            # Correctly closing connections (called once, whether normal or abnormal exit)
            await __on_shutdown(dp, bot)

            if cache_scheduler:
                await cache_scheduler.stop()

            if isinstance(storage, RedisStorage):
                await storage.close()
                logging.info("Redis connection closed")
