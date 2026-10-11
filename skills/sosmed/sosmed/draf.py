"""Penyimpanan draf & catatan media (berkas JSON di SOSMED_DATA)."""
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

STATUS = ("menunggu", "disetujui", "ditolak", "dikirim", "sebagian", "gagal")


class GalatDraf(Exception):
    pass


class Gudang:
    def __init__(self, cfg):
        self.cfg = cfg
        self.root = Path(cfg.data_dir)
        self.dir_draf = self.root / "draf"
        self.dir_media = self.root / "media"
        for d in (self.dir_draf, self.dir_media):
            d.mkdir(parents=True, exist_ok=True)
        self.f_media = self.root / "media.json"
        self.f_akun = self.root / "akun.json"

    # --- utilitas JSON atomik ---
    @staticmethod
    def _baca(path, bawaan):
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return bawaan

    @staticmethod
    def _tulis(path, data):
        tmp = Path(str(path) + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    # --- akun (cache) ---
    def simpan_akun(self, daftar):
        self._tulis(self.f_akun, daftar)

    def akun(self):
        return self._baca(self.f_akun, [])

    # --- media ---
    def catat_media(self, url, info):
        m = self._baca(self.f_media, {})
        m[url] = dict(info, waktu=sekarang_utc().isoformat())
        self._tulis(self.f_media, m)

    def media(self):
        return self._baca(self.f_media, {})

    def hapus_catatan_media(self, url):
        m = self._baca(self.f_media, {})
        m.pop(url, None)
        self._tulis(self.f_media, m)

    # --- draf ---
    def _path(self, did):
        if not did or not did.isalnum():
            raise GalatDraf("ID draf tidak sah.")
        return self.dir_draf / f"{did}.json"

    def baru(self, isi):
        did = secrets.token_hex(3)
        isi = dict(isi, id=did, status="menunggu", dibuat=sekarang_utc().isoformat(), riwayat=[])
        self._tulis(self._path(did), isi)
        return isi

    def ambil(self, did):
        d = self._baca(self._path(did), None)
        if d is None:
            raise GalatDraf(f"Draf {did} tidak ditemukan.")
        return d

    def simpan(self, d):
        self._tulis(self._path(d["id"]), d)

    def semua(self):
        hasil = [self._baca(p, None) for p in sorted(self.dir_draf.glob("*.json"))]
        return sorted((d for d in hasil if d), key=lambda d: d.get("dibuat", ""), reverse=True)

    def ubah_status(self, d, status, catatan=""):
        assert status in STATUS
        d["riwayat"].append({"dari": d["status"], "ke": status, "waktu": sekarang_utc().isoformat(),
                             "catatan": catatan})
        d["status"] = status
        self.simpan(d)
        return d


def sekarang_utc():
    return datetime.now(timezone.utc)


def parse_jadwal(teks, zona):
    """'sekarang' → 3 menit lagi; 'YYYY-MM-DD HH:MM' (atau 'HH:MM' = hari ini/besok) dalam zona lokal → ISO UTC 'Z'."""
    tz = ZoneInfo(zona)
    teks = (teks or "sekarang").strip().lower()
    kini = sekarang_utc()
    if teks in ("sekarang", "now", "langsung"):
        waktu = kini + timedelta(minutes=3)
    else:
        lokal_kini = kini.astimezone(tz)
        try:
            if len(teks) <= 5:
                jam = datetime.strptime(teks, "%H:%M").time()
                waktu = datetime.combine(lokal_kini.date(), jam, tz)
                if waktu <= lokal_kini:
                    waktu += timedelta(days=1)
            else:
                waktu = datetime.strptime(teks.replace("t", " "), "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        except ValueError:
            raise GalatDraf("Format jadwal: 'sekarang', 'HH:MM', atau 'YYYY-MM-DD HH:MM' (waktu lokal).")
        if waktu.astimezone(timezone.utc) < kini + timedelta(minutes=1):
            raise GalatDraf("Jadwal sudah lewat. Pilih waktu di masa depan.")
    return waktu.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def tampil_lokal(iso, zona):
    w = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S.000Z").replace(tzinfo=timezone.utc)
    return w.astimezone(ZoneInfo(zona)).strftime("%d-%m-%Y %H:%M")
