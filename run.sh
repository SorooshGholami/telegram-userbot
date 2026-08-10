#!/usr/bin/env bash
# Background launch without systemd. For permanent hosting prefer:
#   bash install.sh --service
set -euo pipefail
cd "$(dirname "$0")"

SESSION_NAME=$(grep -E '^SESSION_NAME=' .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
SESSION_NAME=${SESSION_NAME:-userbot}

# nohup has no stdin, so an interactive login would hang silently forever.
if [ ! -f "${SESSION_NAME}.session" ]; then
    echo "No ${SESSION_NAME}.session found."
    echo "Log in interactively first, otherwise this would hang waiting for a code:"
    echo "  source .venv/bin/activate && python userbot.py"
    exit 1
fi

if pgrep -f "python userbot.py" >/dev/null; then
    echo "Already running (PID $(pgrep -f 'python userbot.py' | head -1)). Use stop.sh first."
    exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate
nohup python userbot.py > userbot.log 2>&1 &
echo "Started, PID $!  -  logs: tail -f userbot.log"
