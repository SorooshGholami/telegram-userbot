"""Userbot core: command registry, module autoloader, error handling."""
from __future__ import annotations

import asyncio
import functools
import importlib
import logging
import pkgutil
import re
from dataclasses import dataclass
from typing import Any, Callable

from telethon import TelegramClient, events
from telethon.errors import (
    ChatWriteForbiddenError,
    FloodWaitError,
    MessageNotModifiedError,
    PeerFloodError,
    UserPrivacyRestrictedError,
)

log = logging.getLogger("userbot.core")


@dataclass(slots=True)
class Command:
    pattern: str
    func: Callable[..., Any]
    usage: str
    desc: str
    group: str = "General"


REGISTRY: list[Command] = []


def command(pattern: str, usage: str = "", desc: str = "", group: str = "General"):
    """Register a command. Write the pattern without the prefix; it is added at load time."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        REGISTRY.append(
            Command(pattern=pattern, func=func, usage=usage or pattern, desc=desc, group=group)
        )
        return func

    return decorator


def safe(func: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap common Telegram errors so one broken command cannot take the userbot down."""

    @functools.wraps(func)
    async def wrapper(event: events.NewMessage.Event) -> None:
        try:
            await func(event)
        except MessageNotModifiedError:
            pass
        except FloodWaitError as exc:
            log.warning("FloodWait %ss in %s", exc.seconds, func.__name__)
            if exc.seconds < 60:
                await asyncio.sleep(exc.seconds + 1)
            else:
                await _report(event, f"Telegram asked us to wait {exc.seconds}s.")
        except PeerFloodError:
            await _report(
                event,
                "<b>PeerFloodError</b> - Telegram has flagged this account as a spammer.\n"
                "Stop all bulk sending for a few hours and talk to @SpamBot.",
            )
        except (UserPrivacyRestrictedError, ChatWriteForbiddenError):
            await _report(event, "The target's privacy settings do not allow this message.")
        except Exception as exc:  # noqa: BLE001 - a userbot should never crash
            log.exception("Error in %s", func.__name__)
            await _report(event, f"Error in <code>{func.__name__}</code>:\n<code>{exc!s:.300}</code>")

    return wrapper


async def _report(event: events.NewMessage.Event, text: str) -> None:
    try:
        await event.edit(text, parse_mode="html")
    except Exception:  # noqa: BLE001
        log.error("Failed to report error: %s", text)


async def resolve_peer(client: TelegramClient, raw: str):
    """Resolve any username, ID, or phone number Telegram can find.

    This mirrors what a human does when typing a username into the search bar and
    sending a message: Telegram permits it as long as the recipient's privacy
    settings allow messages from non-contacts, which is the default for most
    accounts. The real anti-spam boundary is volume and pace, not prior contact.

    Returns None when the target cannot be resolved.
    """
    try:
        return await client.get_entity(raw.strip())
    except Exception:  # noqa: BLE001
        return None


def load_modules(client: TelegramClient, prefix: str) -> int:
    """Import every file under modules/ and wire up its handlers."""
    import modules  # lazy import to avoid a circular dependency

    for info in pkgutil.iter_modules(modules.__path__):
        mod = importlib.import_module(f"modules.{info.name}")
        if hasattr(mod, "setup"):
            mod.setup(client)  # non-command handlers, e.g. auto-reply
        log.info("Loaded module: %s", info.name)

    esc = re.escape(prefix)
    for cmd in REGISTRY:
        client.add_event_handler(
            safe(cmd.func),
            events.NewMessage(
                outgoing=True,
                pattern=re.compile(rf"^{esc}{cmd.pattern}$", re.IGNORECASE | re.DOTALL),
            ),
        )
    return len(REGISTRY)
