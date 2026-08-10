# Security

## The session file

`userbot.session` is created on first login and is **equivalent to full access to your Telegram account**. Anyone who obtains it can log in as you without your phone number or a login code.

- It is listed in `.gitignore`. Verify with `git status` before your first commit.
- Keep it at mode `600` and store the project in a directory only your user can read.
- If you think it has leaked: open Telegram → Settings → Devices → terminate the session, then delete the file and log in again.

## API credentials

`API_ID` and `API_HASH` identify the **application**, not the account, so leaking them does not grant account access. The practical risk is that abuse by someone else can get the `api_id` itself blocked, breaking every client that uses it. Telegram offers no straightforward way to revoke and reissue them, so treat `.env` as private regardless.

## Reporting a vulnerability

Open a private security advisory on GitHub rather than a public issue.
