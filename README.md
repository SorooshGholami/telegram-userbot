# Telegram Userbot (Telethon)

[![CI](https://github.com/SorooshGholami/telegram-userbot/actions/workflows/ci.yml/badge.svg)](https://github.com/SorooshGholami/telegram-userbot/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A modular userbot that runs on **your own Telegram account**, not a BotFather bot. You type commands prefixed with `.` in your *own* messages; the userbot edits the message in place and replaces it with the result. It also exposes a local queue so your other scripts can push notifications through the account.

> **Read [SECURITY.md](SECURITY.md) before your first run.** The session file this creates is equivalent to full access to your Telegram account. Never commit it, and never commit `.env`.

Target platform: any Linux with Python 3.10 or newer - desktop or VPS.

---

## Requirements

| | |
|---|---|
| Python | 3.10+ (`slots=True` on dataclasses) |
| System packages | `git`, `python3`, `python3-venv`, `python3-pip` |
| Credentials | `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org) → API development tools |
| Network | Outbound access to Telegram data centres |

On Debian/Ubuntu, `python3-venv` ships as a separate package and its absence is the most common setup failure:

```bash
sudo apt install git python3 python3-venv python3-pip
```

---

## Quick start

```bash
git clone https://github.com/SorooshGholami/telegram-userbot.git
cd telegram-userbot
bash install.sh             # venv, dependencies, and a .env copied from .env.example
nano .env                   # fill in API_ID and API_HASH - selftest fails without them
source .venv/bin/activate
python selftest.py          # health check, no network calls
python userbot.py           # first run: asks for phone number and login code
```

Then, in Saved Messages, send `.ping` followed by `.help`.

> **`userbot.session` is equivalent to full access to your account.** Anyone holding that file logs in without a phone number or code. It is covered by `.gitignore`, along with `.env` and `userbot.db`. Keep its permissions at `600` and never copy it to a shared machine.

---

## Notifications from your own scripts

For a Python or bash script to push a Telegram message through this account, without importing Telethon or talking to a live client:

```bash
python3 notify_client.py "@username" "Order #4821 just shipped."
```

```python
from notify_client import notify
notify("@username", "Order #4821 just shipped.")
```

This does not send anything by itself - it drops a small JSON file into `notify_spool/`. The running userbot polls that directory (`NOTIFY_POLL_INTERVAL`, default 5s) and sends each message using its own already-logged-in session, with a small randomised gap between deliveries (`NOTIFY_MIN_DELAY` / `NOTIFY_MAX_DELAY`, default 2–6s).

**Why a file queue instead of an HTTP API:** a Telethon session only tolerates one active connection. An HTTP server would need to either share the running client (extra plumbing for no real benefit at this volume) or spin up a second client per request (session conflicts, and a slower, heavier round trip for something as simple as "send this text"). A queue directory needs no port, no auth token, and both `notify_client.py` and the userbot already share the one client that is already connected.

**Why this only makes sense at low volume:** the userbot resolves targets exactly like `.send` does - any username or ID Telegram can find, not only people you have already messaged, mirroring what a human does by typing a username and hitting send. That is fine for occasional messages to a handful of new people a day. It stops being fine the moment it turns into an automated stream to many strangers - that pattern is what Telegram's anti-spam system is built to catch, regardless of which tool is doing the sending. If your volume grows past a personal, occasional scale, a proper Bot API bot - which Telegram explicitly designs for automated, higher-volume notifications - is the right tool, not a personal account.

Delivery requires the userbot process to actually be running (`systemctl status userbot`); `notify_client.py` only queues, it does not send. Permanently undeliverable messages (unresolvable target, blocked, malformed file) move to `notify_spool/failed/` with the reason recorded alongside, rather than disappearing silently. Transient conditions are treated differently: on a `FloodWait` the queue simply pauses and the message stays put, so a temporary rate limit never costs you a valid notification.

---

## Commands

| Group | Command | What it does |
|---|---|---|
| Basic | `.ping` | Round-trip latency |
| | `.help [command]` | List commands, or details for one |
| | `.id` | Your ID, the chat ID, or the replied user's ID |
| | `.info` | Details about the replied user |
| | `.me` | Account summary and dialog counts |
| Sending | `.send @user text` | Send to anyone Telegram can resolve |
| | `.sched 10m text` | Delayed send (`s` / `m` / `h`) |
| | `.bulk` | Rate-limited bulk send from `targets.txt`, known dialogs only |
| Automation | `.afk [reason]` | Auto-reply while away |
| | `.unafk` | Turn it off (any manual message also does) |
| Chat | `.purge` | Delete your messages from the reply up to now |
| | `.del` | Delete the replied message |
| | `.pin [loud]` | Pin a message |
| | `.mute` / `.unmute` | Mute a user (needs admin rights) |
| Tools | `.save <name>` / `.get` / `.notes` / `.delnote` | Quick notes |
| | `.dl` | Download media from a replied message |
| | `.up <path>` | Upload a file from the host |

`.bulk` reads `targets.txt`, which is yours and is not committed. Start from the template:

```bash
cp targets.txt.example targets.txt
```

---

## Running it permanently (systemd)

The recommended path. `install.sh --service` renders a unit file with your actual user and directory baked in, so there is nothing to edit by hand:

```bash
bash install.sh --service
```

**Log in interactively first.** systemd has no terminal, so it cannot type your login code; without an existing session the service fails on every restart.

```bash
source .venv/bin/activate && python userbot.py    # enter phone + code, then Ctrl+C
sudo cp systemd/userbot.rendered.service /etc/systemd/system/userbot.service
sudo systemctl daemon-reload
sudo systemctl enable --now userbot
```

Day-to-day:

```bash
systemctl status userbot        # is it alive
journalctl -u userbot -f        # follow logs
journalctl -u userbot -n 200    # last 200 lines
sudo systemctl restart userbot  # after editing modules
```

The unit ships with `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict` and `ProtectHome=read-only`; the only writable path is the project directory. It also gives up after 5 crashes in 5 minutes — an endless reconnect loop looks like abuse from Telegram's side.

### Without systemd

```bash
bash run.sh     # nohup in the background, logs to userbot.log
bash stop.sh    # SIGTERM
```

`run.sh` refuses to start when no session file exists (a background process cannot prompt for a login code — it would hang silently) and refuses to start a second copy.

---

## What is deliberately not included, and why

**Group-member scraping, cold DMs, and mass group-adding.** These are popular userbot modules with a predictable outcome: a few dozen messages in you hit `PeerFloodError`, then restrictions on messaging strangers, and on repeat, a permanent ban on your number. They also breach Telegram's terms of service. An account you have spent years building is not worth that trade.

**What exists instead:** `.bulk` only delivers to peers already in your dialog list, with a randomised 15–40 second delay, a cap of 50 targets per run, and an immediate stop on `PeerFloodError`. That is enough to notify your clients or a team. It is not enough to spam.

---

## Adding a module

Create a file under `modules/`:

```python
from core import command

@command(r"echo ([\s\S]+)", usage=".echo <text>", desc="Repeat text", group="Tools")
async def echo(event):
    await event.edit(event.pattern_match.group(1))
```

Loading is automatic — no manual registration. For non-command handlers (reacting to incoming messages, for example), define `setup(client)` in the same file; see `modules/afk.py`. Restart the service afterwards.

---

## Operational notes

**Clock synchronisation.** MTProto rejects messages whose timestamps drift too far from the server's, and it surfaces as confusing `msg_id is too low/high` errors rather than anything mentioning time. `selftest.py` checks this. If it warns:

```bash
sudo timedatectl set-ntp true
```

**Backups.** Two files hold all your state: `userbot.session` and `userbot.db`. Back them up together, encrypted. Restoring the session elsewhere gives that machine your account.

**Updating.**

```bash
git pull
source .venv/bin/activate && pip install -U -r requirements.txt
sudo systemctl restart userbot
```

**Log growth.** Under systemd, `journalctl` rotates automatically. Under `run.sh`, `userbot.log` grows without bound — truncate or rotate it periodically.

---

## Test status and known limitations

**Verified on every push, without a Telegram connection** ([CI](.github/workflows/ci.yml), Python 3.10–3.13): every file byte-compiles, all 21 commands autoload, zero regex pattern conflicts, storage layer read/write, and the notify queue writes a spool file. `selftest.py` runs the same checks locally.

**Not verified:** no real Telegram API call is executed in CI. Start your first real run with `.ping` and `.help` in Saved Messages — not with `.bulk`.

| Item | Limitation |
|---|---|
| `.sched` | A pending send is lost on restart (held in memory, not the database) |
| `.mute` / `.unmute` | Supergroups and channels only, not basic groups |
| `.purge` | Caps at 1000 messages per run |
| `.up` | Reads any path the service user can read; `ProtectHome=read-only` narrows this under systemd |
| Session | First login must be interactive |

---

## Project layout

```
userbot.py                 entry point
core.py                    command registry, module autoloader, error handling
config.py                  .env loader
storage.py                 SQLite (key/value + notes)
selftest.py                pre-flight health check
notify_client.py           zero-dependency helper: your scripts call this to queue a message
modules/                   every file here is autoloaded
  basic.py                 ping, help, id, info, me
  sender.py                send, sched, bulk
  notify.py                watches notify_spool/ and delivers queued messages
  afk.py                   auto-reply
  chattools.py             purge, del, pin, mute, unmute
  tools.py                 save/get/notes, dl, up
install.sh                 venv + dependencies (--service renders a systemd unit)
run.sh / stop.sh           background launch without systemd
systemd/userbot.service    unit template, filled in by install.sh --service
.env.example               template for the credentials file
targets.txt.example        template for the .bulk target list
.github/workflows/ci.yml   compile, autoload, pattern-conflict and queue checks
```

Created at runtime and kept out of git by `.gitignore`:

```
.env                       your credentials
targets.txt                your .bulk target list
userbot.session            login session - full account access
userbot.db                 notes and key/value state
notify_spool/              queued and failed notifications
userbot.log                only when started via run.sh
```

## About the credentials in `.env`

`API_ID` and `API_HASH` identify the **application**, not the account. Leaking them does not grant access to your Telegram account. The real risk is that if someone else spams using the same credentials, Telegram may block the `api_id` itself, which would break every client you run on it. Telegram also offers no straightforward way to revoke and reissue them.

The genuinely critical file remains `userbot.session`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: modules are autoloaded, `python selftest.py` must pass, and scraping / cold-DM / mass-add features are out of scope.

## Licence

MIT - see [LICENSE](LICENSE).

## Disclaimer

Automating a personal Telegram account carries risk that no amount of code can remove. Sending at machine pace or volume triggers Telegram's anti-spam systems and can get the account restricted or banned, whatever tool is used. This project caps and randomises its bulk paths for that reason. You are responsible for how you use it and for staying within Telegram's terms of service.
