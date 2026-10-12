"""Catatan grup Facebook untuk promo manual (berkas grup.json). Agen TIDAK gabung/posting otomatis."""
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

STATUS = ("belum", "minta-gabung", "gabung", "aktif", "ditolak", "dilarang-promo")
POLA_URL = re.compile(r"^https?://(www\.|m\.|web\.)?facebook\.com/groups/[^/?#\s]+", re.I)


class GalatGrup(Exception):
    pass


def normal_url(url):
    url = (url or "").strip()
    m = POLA_URL.match(url)
    if not m:
        raise GalatGrup("URL harus berupa link grup Facebook, mis. https://www.facebook.com/groups/namagrup")
    return re.sub(r"^https?://(www\.|m\.|web\.)?", "https://www.", m.group(0)).rstrip("/")


class Grup:
    def __init__(self, data_dir):
        self.f = Path(data_dir) / "grup.json"
        self.f.parent.mkdir(parents=True, exist_ok=True)

    def _baca(self):
        try:
            return json.loads(self.f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _tulis(self, daftar):
        tmp = Path(str(self.f) + ".tmp")
        tmp.write_text(json.dumps(daftar, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.f)

    def simpan(self, nama, url, anggota="", aturan="", topik=""):
        url = normal_url(url)
        daftar = self._baca()
        for g in daftar:
            if g["url"].lower() == url.lower():
                g.update({k: v for k, v in {"nama": nama, "anggota": anggota, "aturan": aturan,
                                             "topik": topik}.items() if v})
                self._tulis(daftar)
                return dict(g, baru=False)
        g = {"id": secrets.token_hex(3), "nama": (nama or url)[:150], "url": url, "anggota": anggota,
             "aturan": aturan[:500], "topik": topik.lower()[:80], "status": "belum", "catatan": "",
             "terakhir_promo": "", "dicatat": datetime.now(timezone.utc).isoformat()}
        daftar.append(g)
        self._tulis(daftar)
        return dict(g, baru=True)

    def daftar(self, topik=None, status=None):
        hasil = self._baca()
        if topik:
            hasil = [g for g in hasil if topik.lower() in (g.get("topik") or "") or topik.lower() in g["nama"].lower()]
        if status:
            hasil = [g for g in hasil if g["status"] == status]
        return hasil

    def tandai(self, gid, status, catatan="", promo=False):
        if status not in STATUS:
            raise GalatGrup(f"Status harus salah satu: {', '.join(STATUS)}")
        daftar = self._baca()
        for g in daftar:
            if g["id"] == gid:
                g["status"] = status
                if catatan:
                    g["catatan"] = catatan[:500]
                if promo:
                    g["terakhir_promo"] = datetime.now(timezone.utc).isoformat()
                self._tulis(daftar)
                return g
        raise GalatGrup(f"Grup {gid} tidak ditemukan.")

    def hapus(self, gid):
        daftar = self._baca()
        sisa = [g for g in daftar if g["id"] != gid]
        if len(sisa) == len(daftar):
            raise GalatGrup(f"Grup {gid} tidak ditemukan.")
        self._tulis(sisa)
        return {"dihapus": gid}
