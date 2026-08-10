"""Sending: single messages, delayed messages, and rate-limited bulk delivery.

Design note: this module deliberately only sends to peers you already have a
dialog with. Group-member scraping and cold DMs are not implemented - they lead
to PeerFloodError and account bans, not to marketing results.
"""
from __future__ import annotations

import asyncio
import html
import random

from telethon.errors import FloodWaitError, PeerFloodError

from config import load_config
from core import command, resolve_peer

GROUP = "Sending"
_cfg = load_config()


async def _known_dialog_ids(client) -> set[int]:
    """Fetch the dialog list once. Repeated iter_dialogs calls invite FloodWait."""
    return {dialog.entity.id async for dialog in client.iter_dialogs() if dialog.entity}


async def _resolve_known_peer(client, raw: str, known: set[int] | None = None):
    """Return the target only if it already appears in your dialog list. Used by .bulk."""
    entity = await resolve_peer(client, raw)
    if entity is None:
        return None
    if known is None:
        known = await _known_dialog_ids(client)
    return entity if entity.id in known else None


async def _copy_to(client, entity, source) -> None:
    """Send an existing message to another peer, preserving media and formatting."""
    if source.media:
        await client.send_file(
            entity,
            source.media,
            caption=source.message or "",
            formatting_entities=source.entities,
        )
    else:
        await client.send_message(entity, source.message, formatting_entities=source.entities)


@command(
    r"send (\S+) ([\s\S]+)",
    usage=".send <@user|id> <text>",
    desc="Send a message to anyone Telegram can resolve",
    group=GROUP,
)
async def send_cmd(event) -> None:
    target_raw, text = event.pattern_match.group(1), event.pattern_match.group(2)

    entity = await resolve_peer(event.client, target_raw)
    if entity is None:
        await event.edit(
            "Couldn't resolve that target. It may not exist, or their privacy "
            "settings block messages from you."
        )
        return

    await event.client.send_message(entity, text)
    await event.edit(f"Sent to <code>{html.escape(target_raw)}</code>", parse_mode="html")


@command(
    r"sched (\d+)([smh]) ([\s\S]+)",
    usage=".sched <10m> <text>",
    desc="Send to this chat after a delay",
    group=GROUP,
)
async def sched_cmd(event) -> None:
    amount = int(event.pattern_match.group(1))
    unit = event.pattern_match.group(2)
    text = event.pattern_match.group(3)

    seconds = amount * {"s": 1, "m": 60, "h": 3600}[unit]
    if seconds > 86_400:
        await event.edit("Maximum delay is 24 hours.")
        return

    await event.edit(f"Scheduled to send in <b>{amount}{unit}</b>.", parse_mode="html")
    await asyncio.sleep(seconds)
    await event.client.send_message(event.chat_id, text)


@command(
    r"bulk",
    usage=".bulk (as a reply)",
    desc="Rate-limited bulk send to targets.txt",
    group=GROUP,
)
async def bulk_cmd(event) -> None:
    reply = await event.get_reply_message()
    if not reply:
        await event.edit("Reply to the message you want to send.")
        return

    try:
        with open("targets.txt", encoding="utf-8") as handle:
            raw_targets = [
                line.strip()
                for line in handle
                if line.strip() and not line.lstrip().startswith("#")
            ]
    except FileNotFoundError:
        await event.edit("<code>targets.txt</code> not found.", parse_mode="html")
        return

    if len(raw_targets) > _cfg.bulk_cap:
        await event.edit(
            f"You have {len(raw_targets)} targets but the safe cap is <b>{_cfg.bulk_cap}</b>.\n"
            "Shorten the list, or raise BULK_CAP in .env at your own risk.",
            parse_mode="html",
        )
        return

    status = await event.edit(f"Starting delivery to {len(raw_targets)} targets...")
    known = await _known_dialog_ids(event.client)  # fetched once, not per target
    sent = skipped = failed = 0

    for index, raw in enumerate(raw_targets, start=1):
        entity = await _resolve_known_peer(event.client, raw, known)
        if entity is None:
            skipped += 1
            continue

        try:
            await _copy_to(event.client, entity, reply)
            sent += 1
        except PeerFloodError:
            await status.edit(
                f"<b>Stopped at {index}/{len(raw_targets)}</b>\n"
                "Telegram flagged this account as a spammer. Stand down for a few hours.",
                parse_mode="html",
            )
            return
        except FloodWaitError as exc:
            if exc.seconds > 300:
                await status.edit(f"Stopped: FloodWait of {exc.seconds}s.")
                return
            await asyncio.sleep(exc.seconds + 2)
            failed += 1
        except Exception:  # noqa: BLE001
            failed += 1

        if index % 5 == 0:
            await status.edit(f"{index}/{len(raw_targets)} - delivered: {sent}")

        # Randomised delay: a machine-regular cadence is exactly what anti-spam looks for.
        await asyncio.sleep(random.uniform(_cfg.bulk_min_delay, _cfg.bulk_max_delay))

    await status.edit(
        f"<b>Done</b>\nDelivered: {sent}\nSkipped (no dialog): {skipped}\nErrors: {failed}",
        parse_mode="html",
    )
