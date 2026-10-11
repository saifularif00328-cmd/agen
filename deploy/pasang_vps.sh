#!/usr/bin/env bash
# Pasang skill "sosmed" untuk OpenClaw di VPS Ubuntu.
# Jalankan sebagai root:   sudo bash deploy/pasang_vps.sh
# Aman dijalankan ulang (untuk memperbarui kode / mengganti key).
set -euo pipefail

PENGGUNA="${PENGGUNA:-agen}"
REPO_URL="${REPO_URL:-https://github.com/saifularif00328-cmd/agen.git}"
CABANG="${CABANG:-claude/aplikasi-sesuai-prd-bppvd6}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Jalankan dengan sudo: sudo bash $0"; exit 1
fi

echo "== 1/6 Paket sistem (python3, ffmpeg, git)"
apt-get -o Acquire::http::Timeout=20 -o Acquire::Retries=2 update -q || echo "peringatan: apt update gagal, lanjut"
DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3 python3-venv ffmpeg git curl ca-certificates ufw

echo "== 2/6 Pengguna khusus '$PENGGUNA' (OpenClaw tidak dijalankan sebagai root)"
if ! id "$PENGGUNA" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "$PENGGUNA"
fi
RUMAH="$(getent passwd "$PENGGUNA" | cut -d: -f6)"
loginctl enable-linger "$PENGGUNA" 2>/dev/null || true   # layanan pengguna tetap jalan setelah logout

echo "== 3/6 Kode agen di $RUMAH/agen"
if [ -d "$RUMAH/agen/.git" ]; then
  sudo -u "$PENGGUNA" git -C "$RUMAH/agen" fetch -q origin "$CABANG"
  sudo -u "$PENGGUNA" git -C "$RUMAH/agen" checkout -q "$CABANG"
  sudo -u "$PENGGUNA" git -C "$RUMAH/agen" reset -q --hard "origin/$CABANG"
else
  sudo -u "$PENGGUNA" git clone -q -b "$CABANG" "$REPO_URL" "$RUMAH/agen"
fi

echo "== 4/6 Python venv skill"
sudo -u "$PENGGUNA" python3 -m venv "$RUMAH/.sosmed/venv"
sudo -u "$PENGGUNA" "$RUMAH/.sosmed/venv/bin/pip" install -q --upgrade pip
sudo -u "$PENGGUNA" "$RUMAH/.sosmed/venv/bin/pip" install -q -r "$RUMAH/agen/requirements.txt"

echo "== 5/6 Kunci API (diketik di sini, tidak tampil di layar, disimpan di $RUMAH/.sosmed/.env)"
ENVF="$RUMAH/.sosmed/.env"
touch "$ENVF"; chown "$PENGGUNA:$PENGGUNA" "$ENVF"; chmod 600 "$ENVF"
setel() {   # setel NAMA "keterangan" [wajib]
  local nama="$1" ket="$2" wajib="${3:-}" ada nilai
  ada="$(grep -E "^$nama=." "$ENVF" >/dev/null 2>&1 && echo ya || true)"
  if [ -n "$ada" ]; then
    read -r -p "  $nama sudah terisi. Ganti? (y/T) " jw
    [ "${jw,,}" = "y" ] || return 0
  fi
  while true; do
    read -r -s -p "  $ket: " nilai; echo
    [ -n "$nilai" ] || [ -z "$wajib" ] && break
    echo "  (wajib diisi)"
  done
  sed -i "/^$nama=/d" "$ENVF"
  [ -n "$nilai" ] && printf '%s=%s\n' "$nama" "$nilai" >> "$ENVF"
  return 0
}
setel REPLIZ_ACCESS_KEY "Repliz Access Key (dashboard Repliz > Settings > API)" wajib
setel REPLIZ_SECRET_KEY "Repliz Secret Key" wajib
setel OPENAI_API_KEY "OpenAI API key (platform.openai.com > API keys) untuk membuat gambar" wajib
echo "  Cloudinary = cadangan bila storage Repliz penuh (boleh dikosongkan, tekan Enter)."
setel CLOUDINARY_CLOUD_NAME "Cloudinary Cloud name"
setel CLOUDINARY_API_KEY "Cloudinary API Key"
setel CLOUDINARY_API_SECRET "Cloudinary API Secret"
grep -q '^SOSMED_TZ=' "$ENVF" || echo 'SOSMED_TZ=Asia/Jakarta' >> "$ENVF"

echo "== 6/6 Pasang skill ke workspace OpenClaw + jadwal bersih-bersih harian"
WS="${OPENCLAW_WORKSPACE:-$RUMAH/.openclaw/workspace}"
sudo -u "$PENGGUNA" mkdir -p "$WS/skills"
sudo -u "$PENGGUNA" ln -sfn "$RUMAH/agen/skills/sosmed" "$WS/skills/sosmed"
TUGAS="17 3 * * * $RUMAH/agen/skills/sosmed/scripts/sosmed bersihkan >> $RUMAH/.sosmed/bersihkan.log 2>&1"
( crontab -u "$PENGGUNA" -l 2>/dev/null | grep -v 'sosmed bersihkan' || true; echo "$TUGAS" ) | crontab -u "$PENGGUNA" -

echo
echo "Cek koneksi Repliz (daftar akun):"
if sudo -u "$PENGGUNA" "$RUMAH/agen/skills/sosmed/scripts/sosmed" akun --segarkan; then
  echo "OK — akun di atas yang akan dikelola agen."
else
  echo "Gagal membaca akun Repliz. Periksa Access/Secret Key lalu jalankan ulang skrip ini."
fi

if ! ufw status | grep -q "Status: active"; then
  PORT_SSH="$(ss -tlnp 2>/dev/null | awk '/sshd/ {sub(/.*:/,"",$4); print $4; exit}')"
  echo
  read -r -p "Aktifkan firewall (hanya SSH port ${PORT_SSH:-22} yang dibuka)? (y/T) " jw
  if [ "${jw,,}" = "y" ]; then
    ufw allow "${PORT_SSH:-22}/tcp" >/dev/null
    ufw --force enable
  fi
fi

echo
echo "Selesai. Langkah berikutnya (lihat TUTORIAL.md bagian D): pasang OpenClaw sebagai pengguna '$PENGGUNA':"
echo "  sudo -iu $PENGGUNA"
echo "  curl -fsSL https://openclaw.ai/install.sh | bash"
