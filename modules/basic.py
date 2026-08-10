"""Basic commands: ping, help, id, info, account overview."""
from __future__ import annotations

import html
import time

from telethon.tl.types import Channel, Chat, User

from core import REGISTRY, command

GROUP = "Basic"


@command(r"ping", usage=".ping", desc="Measure round-trip latency", group=GROUP)
async def ping(event) -> None:
    start = time.perf_counter()
    msg = await event.edit("Pinging...")
    elapsed = (time.perf_counter() - start) * 1000
    await msg.edit(f"<b>Pong</b> - <code>{elapsed:.0f} ms</code>", parse_mode="html")


@command(r"help(?: (\w+))?", usage=".help [command]", desc="List commands", group=GROUP)
async def help_cmd(event) -> None:
    query = event.pattern_match.group(1)

    if query:
        for cmd in REGISTRY:
            if cmd.usage.lstrip(".").startswith(query.lower()):
                await event.edit(
                    f"<code>{html.escape(cmd.usage)}</code>\n{html.escape(cmd.desc)}",
                    parse_mode="html",
                )
                return
        await event.edit("No such command.")
        return

    groups: dict[str, list[str]] = {}
    for cmd in REGISTRY:
        groups.setdefault(cmd.group, []).append(
            f"  <code>{html.escape(cmd.usage)}</code> - {html.escape(cmd.desc)}"
        )

    parts = ["<b>Userbot commands</b>"]
    for name, items in groups.items():
        parts.append(f"\n<b>{html.escape(name)}</b>\n" + "\n".join(items))

    await event.edit("\n".join(parts), parse_mode="html")


@command(r"id", usage=".id", desc="Show my ID, this chat, or the replied user", group=GROUP)
async def id_cmd(event) -> None:
    lines = [f"Chat: <code>{event.chat_id}</code>"]

    reply = await event.get_reply_message()
    if reply and reply.sender_id:
        lines.append(f"Replied sender: <code>{reply.sender_id}</code>")
        if reply.media:
            lines.append(f"Message ID: <code>{reply.id}</code>")
    else:
        me = await event.client.get_me()
        lines.append(f"Me: <code>{me.id}</code>")

    await event.edit("\n".join(lines), parse_mode="html")


@command(r"info", usage=".info", desc="Details about the replied user", group=GROUP)
async def info_cmd(event) -> None:
    reply = await event.get_reply_message()
    if not reply or not reply.sender_id:
        await event.edit("Reply to someone's message.")
        return

    entity = await event.client.get_entity(reply.sender_id)

    if isinstance(entity, User):
        name = html.escape(" ".join(filter(None, [entity.first_name, entity.last_name])) or "-")
        lines = [
            f"<b>{name}</b>",
            f"ID: <code>{entity.id}</code>",
            f"Username: @{entity.username}" if entity.username else "Username: none",
            f"Bot: {'yes' if entity.bot else 'no'}",
            f"In my contacts: {'yes' if entity.contact else 'no'}",
            f"Restricted: {'yes' if entity.restricted else 'no'}",
        ]
    elif isinstance(entity, (Chat, Channel)):
        lines = [f"<b>{html.escape(entity.title)}</b>", f"ID: <code>{entity.id}</code>"]
    else:
        lines = ["Unknown entity type."]

    await event.edit("\n".join(lines), parse_mode="html")


@command(r"me", usage=".me", desc="Account summary and dialog counts", group=GROUP)
async def me_cmd(event) -> None:
    await event.edit("Collecting...")
    me = await event.client.get_me()

    users = groups = channels = 0
    async for dialog in event.client.iter_dialogs():
        if dialog.is_user:
            users += 1
        elif dialog.is_group:
            groups += 1
        else:
            channels += 1

    await event.edit(
        f"<b>{html.escape(me.first_name or '')}</b> - <code>{me.id}</code>\n"
        f"Private chats: <b>{users}</b>\n"
        f"Groups: <b>{groups}</b>\n"
        f"Channels: <b>{channels}</b>",
        parse_mode="html",
    )
