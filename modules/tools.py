"""Quick notes plus media download and upload."""
from __future__ import annotations

import html
import os
import time

import storage
from core import command

GROUP = "Tools"
DOWNLOAD_DIR = "downloads"


@command(r"save (\w+)(?: ([\s\S]+))?", usage=".save <name> [text]", desc="Save a note", group=GROUP)
async def save_note(event) -> None:
    name = event.pattern_match.group(1)
    text = event.pattern_match.group(2)

    if not text:
        reply = await event.get_reply_message()
        if not reply or not reply.raw_text:
            await event.edit("Provide text, or reply to a text message.")
            return
        text = reply.raw_text

    storage.save_note(name, text)
    await event.edit(f"Saved as <code>{html.escape(name)}</code>", parse_mode="html")


@command(r"get (\w+)", usage=".get <name>", desc="Recall a note", group=GROUP)
async def get_note(event) -> None:
    name = event.pattern_match.group(1)
    text = storage.get_note(name)
    await event.edit(text if text else "No such note.")


@command(r"notes", usage=".notes", desc="List saved notes", group=GROUP)
async def list_notes(event) -> None:
    names = storage.list_notes()
    if not names:
        await event.edit("No notes saved.")
        return
    await event.edit(
        "<b>Notes</b>\n" + "\n".join(f"- <code>{html.escape(n)}</code>" for n in names),
        parse_mode="html",
    )


@command(r"delnote (\w+)", usage=".delnote <name>", desc="Delete a note", group=GROUP)
async def delete_note(event) -> None:
    ok = storage.del_note(event.pattern_match.group(1))
    await event.edit("Deleted." if ok else "Not found.")


@command(r"dl", usage=".dl (as a reply)", desc="Download media from the replied message", group=GROUP)
async def download(event) -> None:
    reply = await event.get_reply_message()
    if not reply or not reply.media:
        await event.edit("Reply to a message containing a file.")
        return

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    status = await event.edit("Downloading...")
    started = time.perf_counter()

    path = await reply.download_media(file=DOWNLOAD_DIR)
    size_mb = os.path.getsize(path) / 1024 / 1024

    await status.edit(
        f"<code>{html.escape(str(path))}</code>\n"
        f"{size_mb:.1f} MB in {time.perf_counter() - started:.1f}s",
        parse_mode="html",
    )


@command(r"up (.+)", usage=".up <path>", desc="Upload a file from the host", group=GROUP)
async def upload(event) -> None:
    path = event.pattern_match.group(1).strip()
    if not os.path.isfile(path):
        await event.edit("File not found.")
        return

    await event.edit("Uploading...")
    await event.client.send_file(event.chat_id, path, force_document=True)
    await event.delete()
