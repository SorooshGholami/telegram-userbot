"""Entry point - Telethon userbot running on a personal Telegram account.

The first run asks for your phone number and login code interactively and
creates <SESSION_NAME>.session. That file grants full access to your account:
never upload or commit it.
"""
from __future__ import annotations

import asyncio
import logging

from telethon import TelegramClient

import storage
from config import load_config
from core import load_modules

log = logging.getLogger("userbot")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
    logging.getLogger("telethon").setLevel(logging.WARNING)

    cfg = load_config()
    storage.init(cfg.db_path)

    client = TelegramClient(
        cfg.session,
        cfg.api_id,
        cfg.api_hash,
        device_model="Userbot",
        system_version="Linux",
        app_version="1.0",
    )

    await client.start()  # prompts for phone and code on first run

    count = load_modules(client, cfg.prefix)
    me = await client.get_me()

    log.info(
        "Userbot online | %s (@%s) | %d commands | prefix '%s'",
        me.first_name,
        me.username or "-",
        count,
        cfg.prefix,
    )

    try:
        await client.run_until_disconnected()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Shutting down.")
