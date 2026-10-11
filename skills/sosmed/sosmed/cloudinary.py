"""Unggah cadangan ke Cloudinary (dipakai bila storage Repliz penuh). Upload bertanda tangan via REST."""
import hashlib
import time

import requests

FOLDER = "sosmed-agen"


class GalatCloudinary(Exception):
    pass


def _tanda(params, secret):
    teks = "&".join(f"{k}={params[k]}" for k in sorted(params))
    return hashlib.sha1((teks + secret).encode()).hexdigest()


def _kirim(cfg, url, params, files=None, session=None):
    params = dict(params, timestamp=int(time.time()))
    params["signature"] = _tanda(params, cfg.cld_secret)
    params["api_key"] = cfg.cld_key
    r = (session or requests).post(url, data=params, files=files, timeout=600)
    if r.status_code >= 400:
        try:
            pesan = r.json().get("error", {}).get("message") or r.text
        except ValueError:
            pesan = r.text
        raise GalatCloudinary(f"Cloudinary {r.status_code}: {pesan}"[:400])
    return r.json()


def unggah(cfg, path, session=None):
    if not cfg.ada_cloudinary:
        raise GalatCloudinary("Cloudinary belum disetel (CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET).")
    url = f"https://api.cloudinary.com/v1_1/{cfg.cld_cloud}/auto/upload"
    with open(path, "rb") as f:
        d = _kirim(cfg, url, {"folder": FOLDER}, files={"file": f}, session=session)
    return {"provider": "cloudinary", "id": d["public_id"], "jenis": d.get("resource_type", "image"),
            "url": d["secure_url"]}


def hapus(cfg, public_id, jenis="image", session=None):
    url = f"https://api.cloudinary.com/v1_1/{cfg.cld_cloud}/{jenis}/destroy"
    _kirim(cfg, url, {"public_id": public_id}, session=session)
