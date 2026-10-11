# agen — Agen AI pengelola sosmed

Skill **OpenClaw** untuk mengelola Facebook, Instagram, TikTok, Threads, dan YouTube lewat **Repliz API**,
diperintah dari **bot Telegram**, dengan **persetujuan pemilik** sebelum setiap postingan dijadwalkan.

- Buat draf foto / album / video / Reels / Story / teks, caption per platform, jadwal WIB.
- Unggah foto/video pemilik ke storage Repliz (cadangan Cloudinary bila penuh); foto otomatis JPG ≤ 8 MB, sampul video otomatis.
- Buat gambar pendukung dengan OpenAI Images, dipotong ke rasio 1:1 / 4:5 / 9:16 / 16:9.
- Pratinjau → balasan "OK" → jadwal di Repliz → cek status / coba ulang / batal.
- Bersih-bersih media lama otomatis.

Panduan pasang & pakai: **[TUTORIAL.md](TUTORIAL.md)**.

## Struktur

```
skills/sosmed/SKILL.md          instruksi untuk agen (alur draf → setuju → kirim)
skills/sosmed/scripts/sosmed    CLI yang dipanggil agen (keluaran JSON)
skills/sosmed/sosmed/           kode: repliz, cloudinary, media (ffmpeg), gambar (OpenAI), draf, platform, cli
deploy/pasang_vps.sh            pemasang di VPS Ubuntu
tests/                          pytest (HTTP & ffmpeg ditiru)
```

## Pengembangan

```
pip install -r requirements-dev.txt
pytest -q
```

Contoh CLI (butuh `~/.sosmed/.env`, lihat `.env.example`):

```
skills/sosmed/scripts/sosmed akun --segarkan
skills/sosmed/scripts/sosmed unggah foto.jpg
skills/sosmed/scripts/sosmed draf --platform ig,fb --tipe image --caption "Halo!" --media <url> --jadwal "2026-10-12 07:00"
skills/sosmed/scripts/sosmed setujui <id> --pesan "OK"
skills/sosmed/scripts/sosmed kirim <id>
```

Skema API Repliz diambil dari OpenAPI publik Repliz (`https://api.repliz.com`, Basic auth Access/Secret Key).
