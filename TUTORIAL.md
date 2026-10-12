# Tutorial: Agen AI Pengelola Sosmed (OpenClaw + Repliz + Telegram)

Agen ini menerima perintah Anda lewat **bot Telegram**, menyiapkan postingan (caption, foto/video Anda, atau gambar
buatan AI), mengirim **pratinjau untuk Anda setujui**, lalu menjadwalkannya ke **Facebook, Instagram, TikTok,
Threads, dan YouTube** lewat **Repliz**.

```
Anda (Telegram) ──► OpenClaw di VPS ──► skill "sosmed" ──► Repliz ──► FB / IG / TikTok / Threads / YouTube
                         ▲                   │
                         └── pratinjau ◄─────┘  (baru diposting setelah Anda balas "OK")
```

> **Aturan emas:** semua kunci/token (Repliz, OpenAI, Cloudinary, token bot Telegram) hanya diketik **di VPS**.
> Jangan pernah dikirim ke chat mana pun, termasuk ke Claude dan ke bot Anda sendiri.

---

## A. Yang perlu disiapkan

1. **VPS Ubuntu** (RAM ≥ 2 GB) + IP dan password/SSH root dari penyedia VPS.
2. **Bot Telegram** — di Telegram cari **@BotFather** → kirim `/newbot` → isi nama & username bot →
   BotFather memberi **token** (simpan di catatan HP Anda, jangan dibagikan).
3. **Kunci API Repliz** — dashboard Repliz → **Settings → API** → salin **Access Key** dan **Secret Key**.
   Pastikan akun FB/IG/TikTok/Threads/YouTube sudah tersambung di Repliz.
4. **Kunci API OpenAI** — https://platform.openai.com → **API keys → Create new secret key**.
   Isi saldo (Billing) secukupnya; dipakai untuk "otak" agen dan membuat gambar (berbayar per pemakaian).
5. *(Opsional)* **Cloudinary** — cadangan bila storage Repliz penuh: https://cloudinary.com/users/register_free →
   Dashboard → catat **Cloud name, API Key, API Secret**.

## B. Masuk ke VPS

Dari laptop (Windows: buka **PowerShell**):

```
ssh root@IP_VPS_ANDA
```

Ketik `yes` bila ditanya, lalu password VPS (tidak tampil saat diketik — normal).

## C. Pasang skill sosmed (sekali jalan)

Salin-tempel satu per satu:

```
apt-get update && apt-get install -y git
```
```
git clone -b claude/aplikasi-sesuai-prd-bppvd6 https://github.com/saifularif00328-cmd/agen.git /root/agen-pasang
```
```
sudo bash /root/agen-pasang/deploy/pasang_vps.sh
```

Skrip akan:
1. memasang Python, ffmpeg, git, dan Node.js 24 (untuk OpenClaw);
2. membuat pengguna khusus **`agen`** (OpenClaw tidak dijalankan sebagai root);
3. menyalin kode ke `/home/agen/agen`;
4. **menanyakan kunci API** — tempel kunci saat diminta (tidak terlihat di layar, itu normal), tekan Enter;
   Cloudinary boleh dikosongkan;
5. memasang skill ke OpenClaw + jadwal bersih-bersih media tiap pukul 03:17;
6. mengecek koneksi Repliz — akun sosmed Anda harus muncul di daftar;
7. menawarkan firewall (jawab `y`).

Bila daftar akun tidak muncul: periksa Access/Secret Key, lalu jalankan ulang perintah ketiga di atas.

## D. Pasang OpenClaw (otak agen) + sambungkan Telegram

```
sudo -iu agen
```
```
curl -fsSL https://openclaw.ai/install.sh | bash
```

(Node.js 24 sudah dipasang oleh skrip bagian C.) Bila penginstal meminta password/sudo, tekan Ctrl+C lalu pakai:
`npm install -g openclaw@latest` kemudian `openclaw onboard --install-daemon`.

Penginstal otomatis membuka **onboarding**. Pilihan yang dipakai:
- **Model provider:** OpenAI → tempel **OpenAI API key** Anda.
- **Channel:** Telegram → tempel **token bot** dari BotFather.
- Setujui pemasangan **daemon/gateway** agar agen tetap jalan setelah Anda keluar dari SSH.

Setelah selesai, cek:

```
openclaw gateway status
```

Lalu buka Telegram, kirim pesan apa saja ke bot Anda. OpenClaw biasanya membalas dengan **kode pairing** untuk
pengguna baru — setujui dengan perintah yang ditampilkan (di terminal VPS), sehingga **hanya akun Telegram Anda**
yang bisa memerintah agen.

> Bila onboarding menyebut folder *workspace* selain `/home/agen/.openclaw/workspace`, pasang ulang tautan skill:
> `exit`, lalu `sudo OPENCLAW_WORKSPACE=/folder/workspace/tersebut bash /root/agen-pasang/deploy/pasang_vps.sh`

Keluar dari pengguna agen: `exit`.

## E. Uji coba pertama (pakai satu akun dulu)

Di Telegram, ke bot Anda:

1. `cek akun sosmed saya` → agen menampilkan daftar akun dari Repliz.
2. Kirim **satu foto** dengan pesan:
   `posting ke instagram jam 21:00 nanti, promo kopi susu 15rb`
3. Agen membalas **pratinjau** (caption, platform, jam tayang) + fotonya.
4. Balas **`OK`** → agen menjadwalkan dan memberi tahu jamnya.
5. Setelah jam tayang, tanya `cek status postingan tadi`.

Bila berhasil, coba platform lain dan jenis lain.

## F. Contoh perintah sehari-hari

- *(kirim video)* `jadikan reels ke semua platform besok jam 7 pagi, caption tentang menu baru`
- *(kirim 3 foto)* `buat album ke fb dan ig sekarang`
- *(kirim video tegak)* `upload ke story ig dan fb`
- `buatkan gambar poster diskon 20% akhir pekan, posting ke ig & threads sabtu jam 9`
- `ganti captionnya lebih singkat` · `jadwal diundur jam 20:00` · `batalkan postingan tadi`
- `daftar postingan yang menunggu persetujuan`

## G. Aturan & batasan yang perlu diketahui

| Hal | Keterangan |
|---|---|
| Persetujuan | Agen **selalu** mengirim pratinjau dan menunggu balasan setuju Anda. Bila Anda merevisi setelah OK, agen minta OK lagi. |
| Reels | Hanya Facebook yang punya tipe Reels di Repliz; di IG/TikTok/YouTube/Threads dikirim sebagai video (di IG otomatis tampil sebagai Reels). |
| Story | Hanya FB & IG. Stiker (link, polling, lokasi, musik) tidak bisa lewat API. Video Story ≤ 60 detik, tegak 9:16. |
| Teks saja | Hanya FB & Threads. YouTube hanya video. |
| Ukuran video | Bot Telegram hanya bisa mengambil berkas **≤ 20 MB**. Kompres video di HP bila lebih besar. |
| Foto | Otomatis diubah ke JPG ≤ 8 MB (syarat Instagram). |
| Storage | File diunggah ke storage Repliz (kuota sesuai paket); bila penuh, pindah ke Cloudinary. Media dihapus otomatis 3 hari setelah tayang. |
| Biaya | OpenAI berbayar per pemakaian (chat + gambar). Repliz sesuai paket Anda. |

## H. Memperbarui agen

```
sudo bash /home/agen/agen/deploy/pasang_vps.sh
```

Kunci yang sudah ada tidak perlu diisi ulang (jawab `T` saat ditanya ganti).

## I. Bila ada masalah

| Gejala | Cek |
|---|---|
| Bot tidak membalas | `sudo -iu agen` → `openclaw gateway status`; bila mati: `openclaw gateway start` |
| "REPLIZ_ACCESS_KEY belum diisi" | jalankan ulang skrip bagian C/H dan isi kunci |
| "Storage Repliz penuh" | isi Cloudinary (jalankan ulang skrip) atau upgrade paket Repliz |
| Postingan gagal tayang | tanya bot `cek status postingan <id>`; pesan galat dari platform ikut ditampilkan; `coba ulang` |
| Uji CLI manual | `sudo -iu agen` → `~/agen/skills/sosmed/scripts/sosmed akun --segarkan` |

**Bila kunci pernah bocor** (terkirim ke chat/orang lain): segera buat kunci baru di dashboard terkait (Repliz,
OpenAI, Cloudinary, atau `/revoke` di BotFather untuk token bot), lalu jalankan ulang skrip dan pilih ganti.

## J. Fitur riset, gaya bahasa, dan grup Facebook

Contoh perintah ke bot:
- `tren apa yang lagi ramai hari ini? kasih 5 ide konten untuk usaha kopi saya`
- `riset hashtag dan ide reels untuk jualan baju muslim`
- `ingat gaya bahasa saya: santai, pakai "kak", tanpa emoji berlebihan` · *(kirim contoh caption)* `simpan ini sebagai contoh gaya saya`
- `carikan grup facebook jual beli di Medan untuk promo kopi, catat ya` · `tampilkan daftar grup` · `grup Jual Beli Medan sudah saya posting`

Grup Facebook: agen **mencari dan mencatat** grup + menyiapkan teks promo per grup. Bergabung dan menempel postingan
tetap Anda lakukan sendiri (API grup ditutup Meta; otomatisasi berisiko akun diblokir).

## K. Ganti / tambah "otak" AI

- **Ganti model dari Telegram:** ketik `/model` (muncul menu) atau `/model google/gemini-2.5-flash`.
- **Tambah provider baru** (RelayRouter/9Router, OpenRouter, atau layanan lain yang memberi *Base URL* + *API key*),
  di VPS sebagai `agen`:
  ```
  python3 ~/agen/deploy/atur_ai.py
  ```
  Isi Base URL, key (tidak tampil), nama model → otomatis tersimpan & gateway dinyalakan ulang.
- Gemini/OpenAI bawaan: `openclaw onboard` bagian Model.
- Pesan "The AI service needs a short break" = kuota/batas per menit provider habis (umum di Gemini gratis).
  Tunggu 1–2 menit, atau pindah model/provider.

## L. Memperbarui agen (tanpa sudo)

```
bash ~/agen/deploy/perbarui.sh
```
