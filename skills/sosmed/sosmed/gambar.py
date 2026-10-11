"""Buat gambar dengan OpenAI Images API, lalu potong ke rasio sosmed."""
import base64
import time
from pathlib import Path

import requests

from . import media

UKURAN = {"1:1": "1024x1024", "4:5": "1024x1536", "9:16": "1024x1536", "16:9": "1536x1024"}


class GalatGambar(Exception):
    pass


def buat(cfg, prompt, rasio, folder, session=None):
    if not cfg.openai_key:
        raise GalatGambar("OPENAI_API_KEY belum diisi di VPS.")
    if rasio not in UKURAN:
        raise GalatGambar(f"Rasio harus salah satu: {', '.join(UKURAN)}")
    r = (session or requests).post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {cfg.openai_key}"},
        json={"model": cfg.openai_image_model, "prompt": prompt, "size": UKURAN[rasio], "n": 1},
        timeout=300,
    )
    if r.status_code >= 400:
        try:
            pesan = r.json().get("error", {}).get("message") or r.text
        except ValueError:
            pesan = r.text
        raise GalatGambar(f"OpenAI {r.status_code}: {pesan}"[:400])
    item = r.json()["data"][0]
    if item.get("b64_json"):
        isi = base64.b64decode(item["b64_json"])
    else:
        unduh = (session or requests).get(item["url"], timeout=120)
        unduh.raise_for_status()
        isi = unduh.content
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    asli = folder / f"ai-{int(time.time())}.png"
    asli.write_bytes(isi)
    w, h = (int(x) for x in UKURAN[rasio].split("x"))
    a, b = media.RASIO[rasio]
    if w * b != h * a:                    # ukuran OpenAI tidak persis rasio sosmed → potong tengah
        return media.potong_rasio(asli, rasio, folder)
    return media.siapkan_gambar(asli, folder)
