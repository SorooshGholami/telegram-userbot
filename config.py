"""Userbot configuration, loaded from environment variables (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, slots=True)
class Config:
    api_id: int
    api_hash: str
    session: str
    prefix: str
    db_path: str
    bulk_min_delay: float
    bulk_max_delay: float
    bulk_cap: int
    notify_spool_dir: str
    notify_poll_interval: float
    notify_min_delay: float
    notify_max_delay: float


def load_config() -> Config:
    api_id = os.getenv("API_ID", "").strip()
    api_hash = os.getenv("API_HASH", "").strip()

    if not api_id.isdigit() or not api_hash:
        raise RuntimeError(
            "API_ID / API_HASH are not set. "
            "Get them from my.telegram.org > API development tools."
        )

    return Config(
        api_id=int(api_id),
        api_hash=api_hash,
        session=os.getenv("SESSION_NAME", "userbot"),
        prefix=os.getenv("PREFIX", "."),
        db_path=os.getenv("DB_PATH", "userbot.db"),
        bulk_min_delay=float(os.getenv("BULK_MIN_DELAY", "15")),
        bulk_max_delay=float(os.getenv("BULK_MAX_DELAY", "40")),
        bulk_cap=int(os.getenv("BULK_CAP", "50")),
        notify_spool_dir=os.getenv("NOTIFY_SPOOL_DIR", "notify_spool"),
        notify_poll_interval=float(os.getenv("NOTIFY_POLL_INTERVAL", "5")),
        notify_min_delay=float(os.getenv("NOTIFY_MIN_DELAY", "2")),
        notify_max_delay=float(os.getenv("NOTIFY_MAX_DELAY", "6")),
    )
