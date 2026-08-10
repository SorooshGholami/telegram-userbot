"""AFK mode: auto-reply to private messages and mentions while you are away."""
from __future__ import annotations

import html
import logging
import time

from telethon import TelegramClient, events

import storage
from config import load_config
from core import command

log = logging.getLogger("userbot.afk")

GROUP = "Automation"
_cfg = load_config()

_last_reply: dict[int, float] = {}
_own_replies: set[int] = set()  # IDs of auto-replies we sent ourselves
COOLDOWN = 120  # at most one auto-reply per chat within this window (seconds)
MARK = "\u200b"  # zero-width space marking our own auto-replies


def _human_delta(seconds: float) -> str:
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return f"{sec}s"


@command(r"afk(?: ([\s\S]+))?", usage=".afk [reason]", desc="Turn on auto-reply", group=GROUP)
async def afk_on(event) -> None:
    reason = event.pattern_match.group(1) or "Away from keyboard"
    storage.set_key("afk", {"since": time.time(), "reason": reason})
    _last_reply.clear()
    await event.edit(f"AFK enabled - <i>{html.escape(reason)}</i>", parse_mode="html")


@command(r"unafk", usage=".unafk", desc="Turn off auto-reply", group=GROUP)
async def afk_off(event) -> None:
    state = storage.get_key("afk")
    storage.del_key("afk")
    if state:
        away = _human_delta(time.time() - state["since"])
        await event.edit(f"Back - was away for {away}.")
    else:
        await event.edit("AFK was not enabled.")


def setup(client: TelegramClient) -> None:
    """Non-command handlers for this module."""

    @client.on(events.NewMessage(incoming=True))
    async def auto_reply(event: events.NewMessage.Event) -> None:
        state = storage.get_key("afk")
        if not state:
            return

        # Only private chats, or groups where you were mentioned.
        if not (event.is_private or event.mentioned):
            return

        sender = await event.get_sender()
        if sender is None or getattr(sender, "bot", False):
            return

        now = time.time()
        if now - _last_reply.get(event.chat_id, 0) < COOLDOWN:
            return
        _last_reply[event.chat_id] = now

        away = _human_delta(now - state["since"])
        try:
            sent = await event.reply(
                f"{MARK}<b>AFK</b> - {html.escape(state['reason'])}\n"
                f"<i>Away for {away}; I'll see this when I'm back.</i>",
                parse_mode="html",
            )
            _own_replies.add(sent.id)
        except Exception:  # noqa: BLE001 - an auto-reply must never kill the client
            log.exception("AFK auto-reply failed")

    @client.on(events.NewMessage(outgoing=True))
    async def auto_disable(event: events.NewMessage.Event) -> None:
        """Any message you type by hand means you are back - but not our own auto-replies."""
        # Our auto-reply is itself an outgoing message; it must not clear AFK.
        if event.id in _own_replies:
            _own_replies.discard(event.id)
            return

        text = (event.raw_text or "").strip()
        if text.startswith(MARK):
            return
        if text.startswith((f"{_cfg.prefix}afk", f"{_cfg.prefix}unafk")):
            return

        if storage.get_key("afk"):
            storage.del_key("afk")
            _own_replies.clear()
            _last_reply.clear()
