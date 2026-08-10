"""Userbot self-test - run this before the first real launch.

    python selftest.py            # offline checks only
    python selftest.py --connect  # also connects to Telegram (read-only, sends nothing)
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import time

OK, BAD, WARN = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m", "\033[93mWARN\033[0m"
failures = 0


def check(label: str, passed: bool, hint: str = "", info: str = "", fatal: bool = True) -> bool:
    """hint is shown only on failure; info only on success."""
    global failures
    mark = OK if passed else (BAD if fatal else WARN)
    extra = info if passed else hint
    print(f" [{mark}] {label}" + (f"  - {extra}" if extra else ""))
    if not passed and fatal:
        failures += 1
    return passed


def section(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m")


# ---------- 1. Environment ----------
section("1. Runtime environment")
check(
    f"Python {sys.version_info.major}.{sys.version_info.minor}",
    sys.version_info >= (3, 10),
    hint="3.10 or newer required (dataclass slots)",
)

for pkg, fatal in (("telethon", True), ("dotenv", True), ("cryptg", False)):
    spec = importlib.util.find_spec(pkg)
    check(
        f"package: {pkg}",
        spec is not None,
        hint="install with: pip install -r requirements.txt",
        fatal=fatal,
    )

if failures:
    print("\nPrerequisites are missing. Stopping here.")
    sys.exit(1)

# ---------- 2. Configuration ----------
section("2. Configuration")
check(".env present", os.path.isfile(".env"), hint="cp .env.example .env")

try:
    from config import load_config

    cfg = load_config()
    check("API_ID / API_HASH loaded", True, info=f"api_id={cfg.api_id}")
    check(
        "API_HASH length",
        len(cfg.api_hash) == 32,
        hint=f"got {len(cfg.api_hash)} characters, expected 32",
    )
    check("command prefix", bool(cfg.prefix), info=f"'{cfg.prefix}'")
    check(
        "bulk delay is safe",
        cfg.bulk_min_delay >= 10,
        hint=f"{cfg.bulk_min_delay}s - below 10s risks PeerFlood",
        info=f"{cfg.bulk_min_delay}-{cfg.bulk_max_delay}s",
        fatal=False,
    )
    check(
        "notify queue settings",
        cfg.notify_poll_interval > 0 and cfg.notify_min_delay <= cfg.notify_max_delay,
        hint="check NOTIFY_POLL_INTERVAL / NOTIFY_MIN_DELAY / NOTIFY_MAX_DELAY",
        info=f"poll every {cfg.notify_poll_interval}s, gap {cfg.notify_min_delay}-{cfg.notify_max_delay}s",
    )
except Exception as exc:  # noqa: BLE001
    check("load configuration", False, hint=str(exc))
    sys.exit(1)

# ---------- 3. System clock ----------
section("3. System clock")
# MTProto rejects messages whose timestamps drift too far from the server's,
# so an unsynchronised clock shows up as confusing msg_id errors, not clock errors.
if shutil.which("timedatectl"):
    try:
        out = subprocess.run(
            ["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        check(
            "clock synchronised via NTP",
            out == "yes",
            hint="enable it: sudo timedatectl set-ntp true",
            fatal=False,
        )
    except Exception:  # noqa: BLE001
        check("clock check", False, hint="timedatectl did not respond", fatal=False)
else:
    check(
        "NTP status",
        False,
        hint="timedatectl unavailable; verify the clock some other way (e.g. chronyc tracking)",
        fatal=False,
    )

# ---------- 4. Storage ----------
section("4. Storage layer")
try:
    import storage

    storage.init(cfg.db_path)
    storage.set_key("__selftest", {"v": 1})
    ok = storage.get_key("__selftest") == {"v": 1}
    storage.del_key("__selftest")
    check("SQLite read/write", ok, info=cfg.db_path)
except Exception as exc:  # noqa: BLE001
    check("SQLite read/write", False, hint=str(exc))

try:
    import shutil as _shutil

    from notify_client import notify as _notify

    test_dir = f"/tmp/userbot-selftest-{os.getpid()}"
    os.environ["NOTIFY_SPOOL_DIR"] = test_dir
    queued = _notify("@selftest", "probe message")
    ok = queued.is_file() and queued.suffix == ".json"
    _shutil.rmtree(test_dir, ignore_errors=True)
    os.environ.pop("NOTIFY_SPOOL_DIR", None)
    check("notify_client queues a file", ok)
except Exception as exc:  # noqa: BLE001
    check("notify_client queues a file", False, hint=str(exc))

# ---------- 5. Modules and commands ----------
section("5. Modules and commands")
try:
    from telethon import TelegramClient

    from core import REGISTRY, load_modules

    client = TelegramClient(cfg.session, cfg.api_id, cfg.api_hash)
    count = load_modules(client, cfg.prefix)
    check("module autoload", count > 0, info=f"{count} commands registered")

    esc = re.escape(cfg.prefix)
    compiled = [
        (c.usage, re.compile(rf"^{esc}{c.pattern}$", re.IGNORECASE | re.DOTALL)) for c in REGISTRY
    ]

    conflicts = []
    for usage, _ in compiled:
        probe = usage.split(" ")[0]
        hits = [u for u, p in compiled if p.match(probe)]
        if len(hits) > 1:
            conflicts.append((probe, hits))
    check("command pattern conflicts", not conflicts, hint=str(conflicts), info="none")
except Exception as exc:  # noqa: BLE001
    check("module autoload", False, hint=repr(exc))

# ---------- 6. Connection (optional) ----------
if "--connect" in sys.argv:
    section("6. Telegram connection (read-only)")

    async def probe() -> None:
        await client.connect()
        try:
            authorized = await client.is_user_authorized()
            check(
                "session is valid",
                authorized,
                hint="run 'python userbot.py' manually once to log in",
            )
            if not authorized:
                return

            me = await client.get_me()
            print(f"        Account: {me.first_name} (@{me.username or '-'}) id {me.id}")

            users = groups = 0
            async for dialog in client.iter_dialogs(limit=200):
                users += dialog.is_user
                groups += dialog.is_group
            print(f"        {users} private chats, {groups} groups (first 200 dialogs)")

            start = time.perf_counter()
            await client.get_me()
            print(f"        Round-trip latency: {(time.perf_counter() - start) * 1000:.0f} ms")
        finally:
            await client.disconnect()

    try:
        asyncio.run(probe())
    except Exception as exc:  # noqa: BLE001
        check("connection", False, hint=repr(exc))
else:
    section("6. Connection")
    print("        Skipped - run 'python selftest.py --connect' to test for real")

# ---------- Result ----------
print()
if failures:
    print(f"\033[91m{failures} check(s) failed.\033[0m")
    sys.exit(1)
print("\033[92mAll checks passed. Next: python userbot.py\033[0m")
print("Try '.ping' then '.help' in Saved Messages.")
