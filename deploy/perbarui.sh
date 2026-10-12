#!/usr/bin/env bash
# Perbarui agen sosmed (jalankan sebagai pengguna agen, tanpa sudo):  bash ~/agen/deploy/perbarui.sh
set -euo pipefail
cd "$HOME/agen"
git pull -q --ff-only
"$HOME/.sosmed/venv/bin/pip" install -q -r requirements.txt
WS="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
rm -rf "$WS/skills/sosmed"
cp -a "$HOME/agen/skills/sosmed" "$WS/skills/sosmed"
openclaw gateway restart || true
echo "Agen diperbarui ke: $(git log --oneline -1)"
