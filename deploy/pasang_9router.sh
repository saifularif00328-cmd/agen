#!/usr/bin/env bash
# Pasang 9Router (gateway AI) di VPS untuk OpenClaw. Jalankan sebagai pengguna agen (tanpa sudo):
#   bash ~/agen/deploy/pasang_9router.sh
# 9Router hanya mendengarkan di 127.0.0.1 (tidak terbuka ke internet). Dashboard dibuka lewat SSH tunnel.
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then
  echo "Jalankan sebagai pengguna agen, bukan root:  sudo -iu agen  lalu ulangi."; exit 1
fi
export PATH="$HOME/.npm-global/bin:$PATH"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
for f in .bashrc .profile; do   # agar systemctl --user jalan setelah `sudo -iu agen`
  grep -q 'XDG_RUNTIME_DIR' "$HOME/$f" 2>/dev/null || echo 'export XDG_RUNTIME_DIR=/run/user/$(id -u)' >> "$HOME/$f"
done
DATA="$HOME/.9router"
ENVF="$DATA/9router.env"

echo "== 1/4 Pasang 9Router (npm)"
npm install -g 9router >/dev/null
BIN="$(command -v 9router)" || { echo "9router tidak ditemukan setelah dipasang."; exit 1; }
echo "   $BIN"

echo "== 2/4 Pengaturan (password dashboard & kunci acak)"
mkdir -p "$DATA"; chmod 700 "$DATA"
if [ ! -f "$ENVF" ]; then
  while true; do
    read -r -s -p "   Buat password dashboard 9Router (min 8 karakter, tidak tampil): " PW; echo
    [ "${#PW}" -ge 8 ] && break
    echo "   Terlalu pendek."
  done
  umask 077
  cat > "$ENVF" <<EOF
PORT=20128
HOSTNAME=127.0.0.1
NEXT_PUBLIC_BASE_URL=http://localhost:20128
DATA_DIR=$DATA
INITIAL_PASSWORD=$PW
JWT_SECRET=$(openssl rand -hex 32)
API_KEY_SECRET=$(openssl rand -hex 32)
MACHINE_ID_SALT=$(openssl rand -hex 16)
REQUIRE_API_KEY=true
AUTH_COOKIE_SECURE=false
ENABLE_REQUEST_LOGS=false
EOF
  unset PW
else
  echo "   Pengaturan lama dipakai ($ENVF)."
fi
chmod 600 "$ENVF"

echo "== 3/4 Jalankan otomatis (layanan pengguna)"
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/9router.service" <<EOF
[Unit]
Description=9Router AI gateway (lokal untuk OpenClaw)
After=network-online.target

[Service]
EnvironmentFile=$ENVF
Environment=PATH=$HOME/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
WorkingDirectory=$DATA
# tanpa layar (systemd) menu interaktif 9router langsung keluar → pakai mode latar (--tray) & ikat ke 127.0.0.1
ExecStart=$BIN --tray --skip-update --no-browser --host 127.0.0.1 --port 20128
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF
if systemctl --user daemon-reload 2>/dev/null && systemctl --user enable 9router 2>/dev/null; then
  systemctl --user restart 9router
  echo "   Layanan systemd pengguna aktif (9router)."
else
  echo "   systemd pengguna tidak tersedia; pakai cadangan nohup + @reboot."
  pkill -f "$BIN" 2>/dev/null || true
  ARGS="--tray --skip-update --no-browser --host 127.0.0.1 --port 20128"
  ( set -a; . "$ENVF"; set +a; cd "$DATA"; nohup "$BIN" $ARGS >"$DATA/9router.log" 2>&1 < /dev/null & )
  TUGAS="@reboot cd $DATA && set -a && . $ENVF && set +a && $BIN $ARGS >$DATA/9router.log 2>&1 < /dev/null"
  ( crontab -l 2>/dev/null | grep -v '9router' || true; echo "$TUGAS" ) | crontab -
fi

echo "== 4/4 Cek"
for i in $(seq 1 30); do
  if curl -s -o /dev/null http://127.0.0.1:20128/; then echo "   9Router hidup di http://127.0.0.1:20128"; break; fi
  sleep 2
  [ "$i" -eq 30 ] && echo "   Belum menjawab. Cek log: journalctl --user -u 9router -n 50  (atau $DATA/9router.log)"
done

cat <<EOF

Selesai. Langkah berikutnya:
 1. Di LAPTOP buka PowerShell baru, jalankan (biarkan jendela terbuka):
      ssh -L 20128:127.0.0.1:20128 root@IP_VPS_ANDA
 2. Di browser laptop buka:  http://localhost:20128/dashboard  → login dengan password tadi.
 3. Sambungkan provider AI di dashboard, lalu buat API key (salin).
 4. Kembali ke VPS (pengguna agen):  python3 ~/agen/deploy/atur_ai.py  → pilih "9Router di VPS ini".
EOF
