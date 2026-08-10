"""Chat utilities: purging, deleting, pinning, muting."""
from __future__ import annotations

import asyncio

from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights

from core import command

GROUP = "Chat"


@command(r"purge", usage=".purge (as a reply)", desc="Delete your messages from the reply to here", group=GROUP)
async def purge(event) -> None:
    reply = await event.get_reply_message()
    if not reply:
        await event.edit("Reply to the message you want to purge from.")
        return

    me = await event.client.get_me()
    ids: set[int] = {event.id}

    async for message in event.client.iter_messages(
        event.chat_id, min_id=reply.id - 1, reverse=True, limit=1000
    ):
        if message.sender_id == me.id:
            ids.add(message.id)

    await event.client.delete_messages(event.chat_id, list(ids))
    notice = await event.client.send_message(event.chat_id, f"Purged {len(ids)} messages.")
    await asyncio.sleep(3)
    await notice.delete()


@command(r"del", usage=".del (as a reply)", desc="Delete the replied message and the command", group=GROUP)
async def delete_msg(event) -> None:
    reply = await event.get_reply_message()
    if not reply:
        await event.edit("Reply to the message you want to delete.")
        return
    await reply.delete()
    await event.delete()


@command(r"pin(?: (loud))?", usage=".pin [loud] (as a reply)", desc="Pin a message", group=GROUP)
async def pin_msg(event) -> None:
    reply = await event.get_reply_message()
    if not reply:
        await event.edit("Reply to the message you want to pin.")
        return
    silent = event.pattern_match.group(1) is None
    await event.client.pin_message(event.chat_id, reply.id, notify=not silent)
    await event.edit("Pinned.")


@command(r"mute", usage=".mute (as a reply)", desc="Mute a user (supergroups only, needs admin)", group=GROUP)
async def mute_user(event) -> None:
    reply = await event.get_reply_message()
    if not reply or not reply.sender_id:
        await event.edit("Reply to the user's message.")
        return

    rights = ChatBannedRights(until_date=None, send_messages=True)
    await event.client(EditBannedRequest(event.chat_id, reply.sender_id, rights))
    await event.edit("Muted.")


@command(r"unmute", usage=".unmute (as a reply)", desc="Unmute a user", group=GROUP)
async def unmute_user(event) -> None:
    reply = await event.get_reply_message()
    if not reply or not reply.sender_id:
        await event.edit("Reply to the user's message.")
        return

    rights = ChatBannedRights(until_date=None, send_messages=False)
    await event.client(EditBannedRequest(event.chat_id, reply.sender_id, rights))
    await event.edit("Unmuted.")
