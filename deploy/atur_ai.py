#!/usr/bin/env python3
"""Tambah/ganti provider AI untuk OpenClaw (jalankan di VPS sebagai pengguna agen):

    python3 ~/agen/deploy/atur_ai.py

Untuk layanan OpenAI-compatible seperti RelayRouter / 9Router / OpenRouter / provider lain yang memberi
"Base URL" + "API key". Key diketik di VPS (tidak tampil), tidak pernah lewat chat.
"""
import getpass
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

CFG = Path.home() / ".openclaw" / "openclaw.json"
CONTOH = {
    "1": ("9router", "9Router di VPS ini", "http://127.0.0.1:20128/v1"),
    "2": ("relay", "RelayRouter / 9Router dari penjual", "https://alamat-dari-penjual/v1"),
    "3": ("openrouter", "OpenRouter", "https://openrouter.ai/api/v1"),
    "4": ("kustom", "Provider lain (OpenAI-compatible)", "https://.../v1"),
}
URL_BAWAAN = {"1", "3"}


class GalatAtur(Exception):
    pass


def tambah_provider(cfg_path, pid, base_url, api_key, models, utama=None):
    """Tulis models.providers.<pid> ke openclaw.json (dengan cadangan). models = daftar id model."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,30}", pid):
        raise GalatAtur("Nama provider hanya huruf kecil/angka/strip, 2–31 karakter.")
    if not re.match(r"^https?://", base_url or ""):
        raise GalatAtur("Base URL harus diawali http:// atau https://")
    if not api_key:
        raise GalatAtur("API key kosong.")
    models = [m.strip() for m in models if m.strip()]
    if not models:
        raise GalatAtur("Isi minimal satu nama model.")
    cfg_path = Path(cfg_path)
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    except ValueError:
        raise GalatAtur(f"{cfg_path} bukan JSON biasa; ubah lewat `openclaw onboard` saja.")
    if cfg_path.exists():
        shutil.copy2(cfg_path, cfg_path.with_name(cfg_path.name + f".bak-{datetime.now():%Y%m%d%H%M%S}"))
    prov = data.setdefault("models", {}).setdefault("providers", {})
    prov[pid] = {"baseUrl": base_url.rstrip("/"), "apiKey": api_key, "api": "openai-completions",
                 "models": [{"id": m, "name": m} for m in models]}
    if utama:
        if utama not in models:
            raise GalatAtur("Model utama harus salah satu model yang diisi.")
        agents = data.setdefault("agents", {}).setdefault("defaults", {})
        model = agents.get("model") if isinstance(agents.get("model"), dict) else {}
        model["primary"] = f"{pid}/{utama}"
        agents["model"] = model
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cfg_path.with_name(cfg_path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(cfg_path)
    return [f"{pid}/{m}" for m in models]


def daftar_model(base_url, api_key, buka=urllib.request.urlopen):
    """Ambil daftar id model dari {base}/models (format OpenAI). Gagal → []."""
    req = urllib.request.Request(base_url.rstrip("/") + "/models",
                                 headers={"Authorization": f"Bearer {api_key}", "User-Agent": "sosmed-agen"})
    try:
        with buka(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return []
    items = data.get("data", data) if isinstance(data, dict) else data
    return sorted({m.get("id") for m in items if isinstance(m, dict) and m.get("id")}) if isinstance(items, list) else []


def _pilih_model(ids):
    for i, m in enumerate(ids, 1):
        print(f"  {i:>3}. {m}")
    teks = input("Pilih nomor model (pisahkan koma, mis. 1,3): ").strip()
    hasil = []
    for t in teks.split(","):
        t = t.strip()
        if t.isdigit() and 1 <= int(t) <= len(ids):
            hasil.append(ids[int(t) - 1])
    return hasil


def main():
    print("== Tambah provider AI untuk OpenClaw ==")
    print("Gemini / OpenAI bawaan: pakai `openclaw onboard` (bagian Model).")
    for k, (_, nama, _) in CONTOH.items():
        print(f"  {k}. {nama}")
    pilih = input(f"Pilih [1-{len(CONTOH)}]: ").strip()
    if pilih not in CONTOH:
        print("Batal.")
        return 1
    pid, nama, contoh_url = CONTOH[pilih]
    if pilih == "4":
        pid = input("Nama singkat provider (huruf kecil, mis. murah): ").strip().lower() or "kustom"
    tanda = " — Enter untuk memakai ini" if pilih in URL_BAWAAN else ""
    base = input(f"Base URL ({contoh_url}{tanda}): ").strip() or (contoh_url if pilih in URL_BAWAAN else "")
    key = getpass.getpass("API key (tidak tampil saat diketik/ditempel): ").strip()
    ids = daftar_model(base, key) if base else []
    if ids:
        print(f"Ditemukan {len(ids)} model:")
        models = _pilih_model(ids)
    else:
        print("Daftar model tidak bisa diambil (cek Base URL/key). Ketik manual.")
        models = input("Nama model, pisahkan koma (mis. kr/claude-sonnet-4.5): ").split(",")
    models = [m.strip() for m in models if m.strip()]
    utama = None
    if models:
        print("Model utama (dipakai agen):")
        for i, m in enumerate(models, 1):
            print(f"  {i}. {m}")
        u = input("Nomor model utama (Enter = 1, ketik 0 = jangan ubah model utama): ").strip() or "1"
        if u.isdigit() and 1 <= int(u) <= len(models):
            utama = models[int(u) - 1]
    try:
        refs = tambah_provider(CFG, pid, base, key, models, utama)
    except GalatAtur as e:
        print("Gagal:", e)
        return 1
    print("Tersimpan. Model tersedia:", ", ".join(refs))
    if utama:
        print(f"Model utama: {pid}/{utama}")
    print("Menyalakan ulang gateway…")
    subprocess.run(["openclaw", "gateway", "restart"], check=False)
    print(f"Di Telegram bisa ganti model kapan saja: /model {refs[0]}  (atau /model untuk menu)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
