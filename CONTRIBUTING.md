# Contributing

## Getting set up

```bash
git clone <your-fork-url> && cd telegram-userbot
bash install.sh
source .venv/bin/activate
cp .env.example .env      # add your own API_ID / API_HASH
python selftest.py
```

You need your own credentials from [my.telegram.org](https://my.telegram.org) → API development tools. Never commit them.

## Adding a module

Every file under `modules/` is autoloaded. A module registers commands with the `@command` decorator and, optionally, a `setup(client)` function for handlers that are not commands.

```python
from core import command

@command(r"echo ([\s\S]+)", usage=".echo <text>", desc="Repeat text", group="Tools")
async def echo(event):
    await event.edit(event.pattern_match.group(1))
```

Guidelines:

- The pattern is written **without** the command prefix; it is added at load time and anchored with `^...$`.
- Check that your pattern does not collide with an existing one. `python selftest.py` reports conflicts.
- Do not import private helpers (`_name`) from another module. If two modules need the same logic, it belongs in `core.py`.
- Any handler that can raise should assume `core.safe()` wraps it - command handlers are wrapped automatically, handlers you register yourself in `setup()` are not.

## Before opening a pull request

```bash
python selftest.py                                   # must be all PASS
python -m py_compile *.py modules/*.py               # syntax
bash -n install.sh run.sh stop.sh                    # shell syntax
```

## Scope

Pull requests that add group-member scraping, cold-DM automation, or mass group-adding will not be merged. They breach Telegram's terms of service and get contributors' accounts banned. `.bulk` is deliberately capped and restricted to existing dialogs for the same reason; please do not "optimise" those limits away.
