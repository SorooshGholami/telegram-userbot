#!/usr/bin/env bash
# Stop a userbot started by run.sh (systemd users: systemctl stop userbot)
set -euo pipefail
PIDS=$(pgrep -f "python userbot.py" || true)
if [ -z "$PIDS" ]; then
    echo "Not running."
    exit 0
fi
echo "$PIDS" | xargs kill
echo "Sent SIGTERM to: $PIDS"
