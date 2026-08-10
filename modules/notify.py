"""Local notification queue - lets your own scripts trigger Telegram messages
without importing Telethon or touching the running client directly.

Other scripts drop a JSON file into the spool directory (see notify_client.py
at the project root for a zero-dependency helper) and this module picks it up
within NOTIFY_POLL_INTERVAL seconds and sends it using the already-authenticated
session.

Queue file format: {"target": "@username or id or phone", "text": "message"}
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import FloodWaitError, PeerFloodError

from config import load_config
from core import resolve_peer

log = logging.getLogger("userbot.notify")
_cfg = load_config()

# Anchor a relative spool path to the project directory, never the current working
# directory. Both this module and notify_client.py must land on the same folder even
# when a calling script runs from somewhere else entirely.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_configured = Path(_cfg.notify_spool_dir)
SPOOL_DIR = _configured if _configured.is_absolute() else _PROJECT_ROOT / _configured
FAILED_DIR = SPOOL_DIR / "failed"


def setup(client: TelegramClient) -> None:
    SPOOL_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)
    # Queue files carry recipient identifiers and message text - keep them private
    # regardless of the process umask.
    os.chmod(SPOOL_DIR, 0o700)
    os.chmod(FAILED_DIR, 0o700)

    # load_modules() is a plain function; it is called from async main() at runtime
    # but also from selftest.py, where no event loop exists. Only start the poller
    # when there is a loop to attach it to.
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        log.debug("No running event loop - notification poller not started.")
        return

    loop.create_task(_poll_loop(client))


async def _poll_loop(client: TelegramClient) -> None:
    log.info("Notification queue watching %s every %ss", SPOOL_DIR, _cfg.notify_poll_interval)
    while True:
        try:
            await _process_pending(client)
        except Exception:  # noqa: BLE001 - the poll loop must never die
            log.exception("Notification poll cycle failed")
        await asyncio.sleep(_cfg.notify_poll_interval)


async def _process_pending(client: TelegramClient) -> None:
    # Dotfiles are in-progress atomic writes from notify_client.py - never read those.
    files = sorted(p for p in SPOOL_DIR.glob("*.json") if not p.name.startswith("."))

    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Bad queue file %s: %s", path.name, exc)
            _quarantine(path, str(exc))
            continue

        target = str(payload.get("target", "")).strip()
        text = str(payload.get("text", "")).strip()
        if not target or not text:
            _quarantine(path, "missing 'target' or 'text'")
            continue

        entity = await resolve_peer(client, target)
        if entity is None:
            _quarantine(path, f"could not resolve target '{target}'")
            continue

        try:
            await client.send_message(entity, text)
            log.info("Notification sent to %s", target)
            path.unlink(missing_ok=True)
        except FloodWaitError as exc:
            # Transient, not a bad message. Leave the file queued and back off;
            # quarantining here would silently drop a perfectly valid notification.
            log.warning("FloodWait %ss - pausing this cycle, %s stays queued", exc.seconds, path.name)
            return
        except PeerFloodError:
            log.error("PeerFloodError - Telegram flagged this account. Halting this cycle.")
            return
        except Exception as exc:  # noqa: BLE001
            log.warning("Send to %s failed: %s", target, exc)
            _quarantine(path, str(exc))
            continue

        # A small randomised gap between queued sends, even at low daily volume -
        # a burst of perfectly back-to-back sends is still an unnatural pattern.
        await asyncio.sleep(random.uniform(_cfg.notify_min_delay, _cfg.notify_max_delay))


def _quarantine(path: Path, reason: str) -> None:
    """Move an unsendable file to failed/ and record why, for later inspection."""
    try:
        # Recreate the directory if it vanished. Without this, a permanently bad
        # file cannot be moved aside and gets retried on every poll cycle forever.
        FAILED_DIR.mkdir(parents=True, exist_ok=True)
        dest = FAILED_DIR / path.name
        path.replace(dest)
        dest.with_suffix(".error.txt").write_text(f"{time.ctime()}  {reason}\n", encoding="utf-8")
    except OSError:
        log.exception("Could not quarantine %s - deleting it to avoid a retry loop", path.name)
        path.unlink(missing_ok=True)
