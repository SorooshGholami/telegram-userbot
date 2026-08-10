#!/usr/bin/env bash
# Setup for Linux.
#
#   bash install.sh             create venv, install dependencies
#   bash install.sh --service   also render a systemd unit for this exact path
#
set -euo pipefail
cd "$(dirname "$0")"
WORKDIR="$(pwd)"

command -v python3 >/dev/null || { echo "python3 is not installed."; exit 1; }

PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "Python ${PY_MAJOR}.${PY_MINOR} found, but 3.10 or newer is required."
    echo "  Debian/Ubuntu:  sudo apt install python3 python3-venv python3-pip"
    echo "  Fedora:         sudo dnf install python3 python3-pip"
    echo "  Arch:           sudo pacman -S python python-pip"
    exit 1
fi
echo "Python ${PY_MAJOR}.${PY_MINOR} OK"

# python3-venv is a separate package on Debian/Ubuntu and its absence is a common trap.
if ! python3 -c 'import venv' 2>/dev/null; then
    echo "The venv module is missing. On Debian/Ubuntu: sudo apt install python3-venv"
    exit 1
fi

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt

[ -f .env ] || { cp .env.example .env; echo "Created .env - fill in API_ID and API_HASH."; }

# The session file is account-equivalent; make sure it is not group/world readable.
umask 077
chmod 700 "$WORKDIR" 2>/dev/null || true

echo
echo "Dependencies installed."

if [ "${1:-}" = "--service" ]; then
    OUT="systemd/userbot.rendered.service"
    sed -e "s|__USER__|$(id -un)|g" \
        -e "s|__GROUP__|$(id -gn)|g" \
        -e "s|__WORKDIR__|${WORKDIR}|g" \
        systemd/userbot.service > "$OUT"
    echo
    echo "Rendered unit written to ${OUT}"
    echo "Log in interactively FIRST, then install it:"
    echo "  source .venv/bin/activate && python userbot.py    # enter phone + code, then Ctrl+C"
    echo "  sudo cp ${OUT} /etc/systemd/system/userbot.service"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable --now userbot"
    echo "  journalctl -u userbot -f"
else
    echo "Next:"
    echo "  source .venv/bin/activate"
    echo "  python selftest.py"
    echo "  python userbot.py       # first run asks for phone number and login code"
fi
