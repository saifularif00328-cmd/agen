"""Klien kecil Repliz Public API (https://api.repliz.com, Basic auth accessKey:secretKey)."""
import mimetypes
import os

import requests


class GalatRepliz(Exception):
    def __init__(self, pesan, status=None):
        super().__init__(pesan)
        self.status = status


class KuotaHabis(GalatRepliz):
    """402 — storage Repliz penuh (upgrade paket)."""


class Repliz:
    def __init__(self, cfg, session=None):
        if not (cfg.repliz_access and cfg.repliz_secret):
            raise GalatRepliz("REPLIZ_ACCESS_KEY / REPLIZ_SECRET_KEY belum diisi di VPS.")
        self.base = cfg.repliz_base
        self.s = session or requests.Session()
        self.s.auth = (cfg.repliz_access, cfg.repliz_secret)

    def _req(self, metode, path, **kw):
        kw.setdefault("timeout", 60)
        r = self.s.request(metode, self.base + path, **kw)
        if r.status_code == 402:
            raise KuotaHabis("Storage Repliz penuh (402).", 402)
        if r.status_code >= 400:
            try:
                pesan = r.json().get("message") or r.text
            except ValueError:
                pesan = r.text
            raise GalatRepliz(f"Repliz {metode} {path} → {r.status_code}: {pesan}"[:500], r.status_code)
        if r.status_code == 204 or not r.content:
            return None
        return r.json()

    # --- akun ---
    def akun(self):
        hasil, page = [], 1
        while True:
            d = self._req("GET", "/public/account", params={"page": page, "limit": 50})
            hasil += d.get("docs", [])
            if not d.get("hasNextPage"):
                return hasil
            page += 1

    # --- storage: init → PUT ke URL presigned → complete ---
    def unggah(self, path):
        nama = os.path.basename(path)
        ukuran = os.path.getsize(path)
        mime = mimetypes.guess_type(nama)[0] or "application/octet-stream"
        d = self._req("POST", "/public/storage/file/init",
                      json={"filename": nama, "size": ukuran, "mimetype": mime})
        with open(path, "rb") as f:
            r = self.s.put(d["upload"], data=f, headers={"Content-Type": mime}, auth=None, timeout=600)
        if r.status_code >= 400:
            raise GalatRepliz(f"Gagal mengirim berkas ke storage Repliz: {r.status_code} {r.text[:200]}", r.status_code)
        self._req("POST", f"/public/storage/file/{d['id']}/complete")
        return {"provider": "repliz", "id": d["id"], "url": d["url"]}

    def hapus_berkas(self, file_id):
        self._req("DELETE", f"/public/storage/file/{file_id}")

    # --- jadwal ---
    def buat_jadwal(self, body):
        return self._req("POST", "/public/schedule", json=body)["scheduleId"]

    def jadwal(self, schedule_id):
        return self._req("GET", f"/public/schedule/{schedule_id}")

    def ulang(self, schedule_id):
        self._req("PUT", f"/public/schedule/{schedule_id}/retry")

    def hapus_jadwal(self, schedule_id):
        self._req("DELETE", f"/public/schedule/{schedule_id}")


def body_jadwal(*, account_id, tipe, caption, judul, medias, schedule_at, ai=False):
    """Susun body POST /public/schedule — semua field wajib skema diisi (kosong bila tak dipakai)."""
    return {
        "title": judul or "",
        "description": caption or "",
        "topic": "",
        "type": tipe,
        "medias": medias,
        "meta": {"title": "", "description": "", "url": ""},
        "additionalInfo": {
            "isAiGenerated": bool(ai), "isDraft": False, "isAutoAddMusic": False, "isShareToFeed": False,
            "collaborators": [],
            "music": {"id": "", "artist": "", "name": "", "thumbnail": "", "volume": {"video": 50, "music": 100}},
            "products": [], "tags": [], "mentions": [], "targetCountries": [],
        },
        "replies": [],
        "accountId": account_id,
        "scheduleAt": schedule_at,
    }
