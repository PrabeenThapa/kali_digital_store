import json
import os
import time
import aiofiles

_GROUPS_FILE = "data/discussion_groups.json"

_DEFAULT_CONFIG = {
    "is_enabled": False,
    "interval_minutes": 1,
    "auto_message_text": (
        "🔥 <b>Welcome to KALI DIGITAL STORE!</b>\n\n"
        "🛍️ <b>Premium Digital Products & Instant Delivery!</b>\n"
        "✨ Coursera, Perplexity, Canva, ChatGPT, VPNs & More!\n\n"
        "👉 Tap below to explore latest items & exclusive deals!"
    ),
    "groups": []
}

_cached_config = None

async def get_discussion_config() -> dict:
    """Read the discussion groups configuration."""
    global _cached_config
    if _cached_config is not None:
        return _cached_config

    if not os.path.exists(_GROUPS_FILE):
        _cached_config = _DEFAULT_CONFIG.copy()
        return _cached_config

    try:
        async with aiofiles.open(_GROUPS_FILE, "r", encoding="utf-8") as f:
            data = json.loads(await f.read())
            _cached_config = {**_DEFAULT_CONFIG, **data}
            return _cached_config
    except Exception:
        return _DEFAULT_CONFIG.copy()

async def save_discussion_config(config: dict) -> None:
    """Save the discussion groups configuration."""
    global _cached_config
    os.makedirs(os.path.dirname(_GROUPS_FILE), exist_ok=True)
    async with aiofiles.open(_GROUPS_FILE, "w", encoding="utf-8") as f:
        await f.write(json.dumps(config, indent=4))
    _cached_config = config

async def set_broadcaster_enabled(enabled: bool) -> None:
    config = await get_discussion_config()
    config["is_enabled"] = enabled
    await save_discussion_config(config)

async def set_broadcaster_interval(minutes: int) -> None:
    config = await get_discussion_config()
    config["interval_minutes"] = max(1, minutes)
    await save_discussion_config(config)

async def update_auto_message(text: str) -> None:
    config = await get_discussion_config()
    config["auto_message_text"] = text.strip()
    await save_discussion_config(config)

async def add_discussion_group(target: str, name: str = "", chat_id: int | None = None) -> dict:
    config = await get_discussion_config()
    groups = config.get("groups", [])
    
    group_id = str(int(time.time() * 1000))
    new_group = {
        "id": group_id,
        "target": target.strip(),
        "chat_id": chat_id,
        "name": name.strip() or target.strip(),
        "enabled": True,
        "added_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    groups.append(new_group)
    config["groups"] = groups
    await save_discussion_config(config)
    return new_group

async def toggle_discussion_group(group_id: str) -> bool:
    config = await get_discussion_config()
    groups = config.get("groups", [])
    new_state = False
    for g in groups:
        if str(g.get("id")) == str(group_id):
            g["enabled"] = not g.get("enabled", True)
            new_state = g["enabled"]
            break
    config["groups"] = groups
    await save_discussion_config(config)
    return new_state

async def delete_discussion_group(group_id: str) -> None:
    config = await get_discussion_config()
    groups = [g for g in config.get("groups", []) if str(g.get("id")) != str(group_id)]
    config["groups"] = groups
    await save_discussion_config(config)
