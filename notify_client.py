#!/usr/bin/env python3
"""Zero-dependency helper for other scripts to queue a Telegram notification.

This does NOT talk to Telegram directly and does NOT need Telethon installed -
it just drops a JSON file into the userbot's spool directory. The running
userbot (modules/notify.py) picks it up within a few seconds and sends it
using its already-authenticated session. The userbot process must actually be
running (systemctl status userbot) for queued messages to go out; this script
only queues them.

From bash:
    python3 notify_client.py "@username" "Order #4821 just shipped."
    # or, if executable:
    ./notify_client.py "@username" "Order #4821 just shipped."

From Python:
    from notify_client import notify
    notify("@username", "Order #4821 just shipped.")

Target format: @username, a numeric user ID, or a phone number in
international format - anything Telegram can resolve, same as the .send
command.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _anchor(value: str) -> Path:
    """A relative spool path is relative to the project, never to the caller's cwd.

    Calling scripts run from anywhere - cron from /, a service from its own
    WorkingDirectory. Resolving "notify_spool" against the current directory would
    scatter queue files into folders the userbot never looks at.
    """
    path = Path(value)
    return path if path.is_absolute() else _HERE / path


def _spool_dir() -> Path:
    """Resolve the spool directory the same way the running userbot does."""
    env_value = os.getenv("NOTIFY_SPOOL_DIR")
    if env_value:
        return _anchor(env_value)

    # Minimal manual parse of .env - python-dotenv may not be installed in the
    # caller's environment, and this script is meant to work without it.
    env_file = _HERE / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("NOTIFY_SPOOL_DIR="):
                return _anchor(line.split("=", 1)[1].strip())

    return _HERE / "notify_spool"


def notify(target: str, text: str) -> Path:
    """Queue a message for delivery. Returns the path of the queued file.

    target: @username, numeric user ID, or phone number in international format.
    text:   message body.
    """
    if not target or not text:
        raise ValueError("both target and text are required")

    spool = _spool_dir()
    spool.mkdir(parents=True, exist_ok=True)
    os.chmod(spool, 0o700)

    name = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}.json"
    tmp_path = spool / f".{name}.tmp"
    final_path = spool / name

    payload = {"target": target, "text": text, "queued_at": time.time()}
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(final_path)  # atomic on the same filesystem - the poller never
    # sees a half-written file this way.
    return final_path


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <@user|id|phone> <message text>", file=sys.stderr)
        sys.exit(1)

    queued_path = notify(sys.argv[1], sys.argv[2])
    print(f"Queued: {queued_path.name}")
