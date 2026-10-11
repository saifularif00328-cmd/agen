"""CLI `sosmed` yang dipanggil agen OpenClaw. Semua keluaran berupa JSON (satu objek) di stdout."""
import argparse
import json
import mimetypes
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import cloudinary, gambar, media, platform
from .config import muat
from .draf import GalatDraf, Gudang, parse_jadwal, sekarang_utc, tampil_lokal
from .repliz import GalatRepliz, KuotaHabis, Repliz, body_jadwal

BATAS_CAPTION = {"threads": 500, "instagram": 2200, "tiktok": 2200, "facebook": 63206, "youtube": 5000}
NAMA = {"facebook": "Facebook", "instagram": "Instagram", "tiktok": "TikTok", "threads": "Threads",
        "youtube": "YouTube"}
LABEL_TIPE = {"text": "teks", "image": "foto", "album": "album", "video": "video", "reel": "Reels",
              "story": "Story"}


class Galat(Exception):
    pass


class App:
    def __init__(self, cfg=None, repliz=None, session=None):
        self.cfg = cfg or muat()
        self.gudang = Gudang(self.cfg)
        self._repliz = repliz
        self.session = session

    @property
    def repliz(self):
        if self._repliz is None:
            self._repliz = Repliz(self.cfg)
        return self._repliz

    # ---------- akun ----------
    def akun(self, segarkan=False):
        daftar = self.gudang.akun()
        if segarkan or not daftar:
            daftar = [{"id": a.get("id") or a.get("_id"), "platform": a.get("type"), "nama": a.get("name"),
                       "username": a.get("username"), "tersambung": bool(a.get("isConnected"))}
                      for a in self.repliz.akun()]
            self.gudang.simpan_akun(daftar)
        return daftar

    # ---------- unggah ----------
    def _unggah_berkas(self, path):
        try:
            hasil = self.repliz.unggah(str(path))
        except KuotaHabis:
            if not self.cfg.ada_cloudinary:
                raise Galat("Storage Repliz penuh dan Cloudinary belum disetel.")
            hasil = cloudinary.unggah(self.cfg, str(path), session=self.session)
        self.gudang.catat_media(hasil["url"], hasil)
        return hasil

    def unggah(self, berkas, rencana=None):
        path = Path(berkas)
        if not path.is_file():
            raise Galat(f"Berkas tidak ditemukan: {berkas}")
        jenis = media.jenis(path)
        peringatan = []
        if jenis == "image":
            siap = media.siapkan_gambar(path, self.gudang.dir_media)
            up = self._unggah_berkas(siap)
            obj = {"type": "image", "url": up["url"], "thumbnail": up["url"]}
        else:
            inf = media.info(path)
            if rencana:
                peringatan += media.peringatan_video(inf, rencana)
            sampul = self._unggah_berkas(media.thumbnail(path, self.gudang.dir_media))
            up = self._unggah_berkas(path)
            obj = {"type": "video", "url": up["url"], "thumbnail": sampul["url"],
                   "durasi": round(inf["durasi"], 1), "rasio": media.nama_rasio(inf["lebar"], inf["tinggi"])}
            self.gudang.catat_media(up["url"], dict(up, thumbnail=sampul["url"]))
        return {"media": obj, "disimpan_di": up["provider"], "peringatan": peringatan}

    def gambar(self, prompt, rasio):
        path = gambar.buat(self.cfg, prompt, rasio, self.gudang.dir_media, session=self.session)
        up = self._unggah_berkas(path)
        self.gudang.catat_media(up["url"], dict(up, ai=True))
        return {"media": {"type": "image", "url": up["url"], "thumbnail": up["url"], "ai": True},
                "berkas_lokal": str(path), "disimpan_di": up["provider"]}

    def _media_dari_url(self, url):
        catatan = self.gudang.media().get(url, {})
        if not url.startswith(("http://", "https://")):
            raise Galat(f"Media harus URL hasil perintah `unggah`/`gambar`, bukan berkas lokal: {url}")
        mime = mimetypes.guess_type(url.split("?")[0])[0] or ""
        jenis = "video" if mime.startswith("video") else "image"
        m = {"alt": "", "customThumbnail": False, "type": jenis, "url": url,
             "thumbnail": catatan.get("thumbnail") or (url if jenis == "image" else "")}
        if jenis == "video" and not m["thumbnail"]:
            raise Galat(f"Video {url} belum punya sampul. Unggah lewat perintah `unggah` agar sampul dibuat.")
        return m, bool(catatan.get("ai"))

    # ---------- draf ----------
    def _target(self, platforms, tipe, caption, caption_per, akun_ids):
        akun = [a for a in self.akun() if a.get("tersambung")]
        if akun_ids:
            akun = [a for a in akun if a["id"] in akun_ids]
        target, catatan = [], []
        for p in platforms:
            t, cat = platform.tipe_untuk(tipe, p)
            if cat:
                catatan.append(cat)
            if not t:
                continue
            milik = [a for a in akun if a["platform"] == p]
            if not milik:
                catatan.append(f"{NAMA[p]}: belum ada akun tersambung di Repliz — dilewati.")
                continue
            cap = caption_per.get(p, caption)
            if len(cap) > BATAS_CAPTION[p]:
                raise Galat(f"Caption {NAMA[p]} {len(cap)} karakter, batasnya {BATAS_CAPTION[p]}. Persingkat.")
            for a in milik:
                target.append({"platform": p, "akun_id": a["id"], "akun": a.get("username") or a.get("nama"),
                               "tipe": t, "caption": cap})
        if not target:
            raise Galat("Tidak ada tujuan yang bisa diposting. " + " ".join(catatan))
        return target, catatan

    def draf(self, platforms, tipe, caption="", caption_per=None, judul="", medias=(), jadwal="sekarang",
             akun_ids=None):
        if tipe not in platform.TIPE:
            raise Galat(f"Tipe harus salah satu: {', '.join(platform.TIPE)}")
        caption_per = {platform.ALIAS.get(k.lower(), k.lower()): v for k, v in (caption_per or {}).items()}
        mlist, ai = [], False
        for u in medias:
            m, is_ai = self._media_dari_url(u)
            mlist.append(m)
            ai = ai or is_ai
        platform.cek_media(tipe, mlist)
        plats = platform.normal(platforms)
        target, catatan = self._target(plats, tipe, caption, caption_per, akun_ids)
        if any(t["platform"] == "youtube" for t in target) and not judul:
            judul = (caption.strip().splitlines() or ["Video"])[0][:100]
        d = self.gudang.baru({"tipe": tipe, "judul": judul, "caption": caption, "medias": mlist, "ai": ai,
                              "jadwal_teks": jadwal, "jadwal": parse_jadwal(jadwal, self.cfg.zona),
                              "target": target, "catatan": catatan, "hasil": []})
        return self._ringkas(d)

    def _ringkas(self, d):
        baris = [f"📝 Draf #{d['id']} — {LABEL_TIPE.get(d['tipe'], d['tipe'])}, "
                 f"tayang {tampil_lokal(d['jadwal'], self.cfg.zona)} ({self.cfg.zona})"]
        for t in d["target"]:
            ket = "" if t["tipe"] == d["tipe"] else f" (sebagai {LABEL_TIPE[t['tipe']]})"
            baris.append(f"• {NAMA[t['platform']]} @{t['akun']}{ket}")
        if d.get("judul"):
            baris.append(f"Judul: {d['judul']}")
        caps = {t["caption"] for t in d["target"]}
        if len(caps) == 1:
            baris.append(f"Caption:\n{caps.pop() or '(tanpa caption)'}")
        else:
            for t in d["target"]:
                baris.append(f"Caption {NAMA[t['platform']]}:\n{t['caption']}")
        for c in d.get("catatan", []):
            baris.append(f"⚠️ {c}")
        if d["status"] == "menunggu":
            baris.append("Balas OK untuk menjadwalkan, atau tulis revisinya.")
        return {"id": d["id"], "status": d["status"], "media": [m["url"] for m in d["medias"]],
                "pratinjau": "\n".join(baris)}

    def lihat(self, did):
        return self._ringkas(self.gudang.ambil(did))

    def daftar(self, status=None):
        return [{"id": d["id"], "status": d["status"], "tipe": d["tipe"],
                 "jadwal": tampil_lokal(d["jadwal"], self.cfg.zona),
                 "platform": sorted({t["platform"] for t in d["target"]}),
                 "caption": (d.get("caption") or "")[:60]}
                for d in self.gudang.semua() if not status or d["status"] == status][:30]

    def setujui(self, did, pesan):
        d = self.gudang.ambil(did)
        if d["status"] != "menunggu":
            raise Galat(f"Draf #{did} berstatus {d['status']}, tidak bisa disetujui.")
        if not (pesan or "").strip():
            raise Galat("Sertakan --pesan berisi balasan persetujuan pemilik (mis. \"OK\").")
        self.gudang.ubah_status(d, "disetujui", f"pemilik: {pesan.strip()[:200]}")
        return {"id": did, "status": "disetujui"}

    def tolak(self, did, alasan=""):
        d = self.gudang.ambil(did)
        if d["status"] in ("dikirim", "sebagian"):
            raise Galat("Draf sudah dikirim; pakai `batal` untuk membatalkan jadwal di Repliz.")
        self.gudang.ubah_status(d, "ditolak", alasan)
        return {"id": did, "status": "ditolak"}

    def ubah(self, did, caption=None, caption_per=None, judul=None, jadwal=None):
        d = self.gudang.ambil(did)
        if d["status"] not in ("menunggu", "disetujui"):
            raise Galat(f"Draf #{did} berstatus {d['status']}, buat draf baru.")
        if caption is not None:
            d["caption"] = caption
        per = {platform.ALIAS.get(k.lower(), k.lower()): v for k, v in (caption_per or {}).items()}
        for t in d["target"]:
            if caption is not None:
                t["caption"] = caption
            if t["platform"] in per:
                t["caption"] = per[t["platform"]]
            if len(t["caption"]) > BATAS_CAPTION[t["platform"]]:
                raise Galat(f"Caption {NAMA[t['platform']]} melebihi {BATAS_CAPTION[t['platform']]} karakter.")
        if judul is not None:
            d["judul"] = judul
        if jadwal is not None:
            d["jadwal_teks"], d["jadwal"] = jadwal, parse_jadwal(jadwal, self.cfg.zona)
        if d["status"] == "disetujui":          # isi berubah → wajib disetujui ulang
            self.gudang.ubah_status(d, "menunggu", "diubah setelah disetujui")
        else:
            self.gudang.simpan(d)
        return self._ringkas(d)

    def kirim(self, did):
        d = self.gudang.ambil(did)
        if d["status"] != "disetujui":
            raise Galat(f"Draf #{did} belum disetujui pemilik (status: {d['status']}). Tidak dikirim.")
        batas = (sekarang_utc() + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if d["jadwal"] < batas:
            if d.get("jadwal_teks", "").strip().lower() in ("sekarang", "now", "langsung"):
                d["jadwal"] = parse_jadwal("sekarang", self.cfg.zona)
            else:
                raise Galat("Jam tayang sudah lewat. Ubah jadwal dulu (`ubah --jadwal`), lalu minta persetujuan ulang.")
        hasil = []
        for t in d["target"]:
            if any(h["akun_id"] == t["akun_id"] and h.get("schedule_id") for h in d.get("hasil", [])):
                continue                               # sudah terkirim pada percobaan sebelumnya
            body = body_jadwal(account_id=t["akun_id"], tipe=t["tipe"], caption=t["caption"],
                               judul=d.get("judul", ""), medias=d["medias"], schedule_at=d["jadwal"], ai=d.get("ai"))
            try:
                sid = self.repliz.buat_jadwal(body)
                hasil.append({"platform": t["platform"], "akun_id": t["akun_id"], "schedule_id": sid})
            except GalatRepliz as e:
                hasil.append({"platform": t["platform"], "akun_id": t["akun_id"], "galat": str(e)})
        d["hasil"] = [h for h in d.get("hasil", []) if h.get("schedule_id")] + hasil
        ok = [h for h in d["hasil"] if h.get("schedule_id")]
        status = "dikirim" if len(ok) == len(d["target"]) else ("sebagian" if ok else "gagal")
        self.gudang.ubah_status(d, status)
        return {"id": did, "status": status, "jadwal": tampil_lokal(d["jadwal"], self.cfg.zona), "hasil": d["hasil"]}

    def status(self, did):
        d = self.gudang.ambil(did)
        keluar = []
        for h in d.get("hasil", []):
            if not h.get("schedule_id"):
                keluar.append({"platform": h["platform"], "status": "gagal_dibuat", "galat": h.get("galat")})
                continue
            j = self.repliz.jadwal(h["schedule_id"])
            keluar.append({"platform": h["platform"], "schedule_id": h["schedule_id"], "status": j.get("status"),
                           "galat": j.get("error") or j.get("message")})
        return {"id": did, "status_draf": d["status"], "hasil": keluar}

    def ulang(self, did):
        d = self.gudang.ambil(did)
        diulang = []
        for h in d.get("hasil", []):
            if h.get("schedule_id"):
                j = self.repliz.jadwal(h["schedule_id"])
                if str(j.get("status", "")).lower() in ("failed", "error", "gagal"):
                    self.repliz.ulang(h["schedule_id"])
                    diulang.append(h["platform"])
        if d["status"] in ("sebagian", "gagal"):     # target yang belum terbuat dicoba lagi
            self.gudang.ubah_status(d, "disetujui", "coba ulang")
            r = self.kirim(did)
            return {"id": did, "diulang": diulang, "kirim_ulang": r}
        return {"id": did, "diulang": diulang}

    def batal(self, did):
        d = self.gudang.ambil(did)
        dibatalkan = []
        for h in d.get("hasil", []):
            if h.get("schedule_id"):
                j = self.repliz.jadwal(h["schedule_id"])
                if str(j.get("status", "")).lower() == "pending":
                    self.repliz.hapus_jadwal(h["schedule_id"])
                    dibatalkan.append(h["platform"])
        self.gudang.ubah_status(d, "ditolak", "dibatalkan pemilik")
        return {"id": did, "dibatalkan": dibatalkan}

    def bersihkan(self):
        kini = sekarang_utc()
        batas = kini - timedelta(days=self.cfg.hari_simpan)
        dipakai = set()
        for d in self.gudang.semua():
            tayang = datetime.strptime(d["jadwal"], "%Y-%m-%dT%H:%M:%S.000Z").replace(tzinfo=timezone.utc)
            if d["status"] in ("menunggu", "disetujui") or tayang > batas:
                for m in d["medias"]:
                    dipakai.update({m["url"], m.get("thumbnail")})
        dihapus, gagal = [], []
        for url, info in self.gudang.media().items():
            if url in dipakai or datetime.fromisoformat(info["waktu"]) > batas:
                continue
            try:
                if info["provider"] == "repliz":
                    self.repliz.hapus_berkas(info["id"])
                else:
                    cloudinary.hapus(self.cfg, info["id"], info.get("jenis", "image"), session=self.session)
                self.gudang.hapus_catatan_media(url)
                dihapus.append(url)
            except Exception as e:                    # lanjutkan berkas lain
                gagal.append({"url": url, "galat": str(e)[:200]})
        for p in self.gudang.dir_media.glob("*"):     # salinan lokal sementara
            if datetime.fromtimestamp(p.stat().st_mtime, timezone.utc) < batas:
                p.unlink(missing_ok=True)
        return {"dihapus": len(dihapus), "gagal": gagal}


def _json(teks):
    if not teks:
        return {}
    try:
        d = json.loads(teks)
    except ValueError:
        raise Galat("--caption-per harus JSON, mis. '{\"tiktok\": \"caption pendek\"}'")
    if not isinstance(d, dict):
        raise Galat("--caption-per harus objek JSON.")
    return d


def parser():
    p = argparse.ArgumentParser(prog="sosmed", description="Kelola postingan sosmed lewat Repliz (dipakai agen).")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("akun", help="daftar akun sosmed di Repliz")
    a.add_argument("--segarkan", action="store_true")
    u = sub.add_parser("unggah", help="unggah foto/video lokal → URL media")
    u.add_argument("berkas")
    u.add_argument("--rencana", choices=platform.TIPE, help="tipe postingan yang direncanakan (untuk peringatan)")
    g = sub.add_parser("gambar", help="buat gambar AI lalu unggah")
    g.add_argument("prompt")
    g.add_argument("--rasio", default="1:1", choices=list(gambar.UKURAN))
    d = sub.add_parser("draf", help="buat draf postingan (status menunggu persetujuan)")
    d.add_argument("--platform", required=True, help="mis. ig,fb,tiktok,threads,youtube atau semua")
    d.add_argument("--tipe", required=True, choices=platform.TIPE)
    d.add_argument("--caption", default="")
    d.add_argument("--caption-per", default="", help='JSON caption khusus per platform')
    d.add_argument("--judul", default="", help="judul video (YouTube)")
    d.add_argument("--media", nargs="*", default=[], help="URL dari perintah unggah/gambar")
    d.add_argument("--jadwal", default="sekarang", help="'sekarang', 'HH:MM', atau 'YYYY-MM-DD HH:MM'")
    d.add_argument("--akun", default="", help="batasi ke ID akun tertentu (pisahkan koma)")
    for nama in ("lihat", "kirim", "status", "ulang", "batal"):
        sub.add_parser(nama).add_argument("id")
    s = sub.add_parser("setujui")
    s.add_argument("id")
    s.add_argument("--pesan", required=True, help="balasan pemilik yang menyetujui, apa adanya")
    t = sub.add_parser("tolak")
    t.add_argument("id")
    t.add_argument("--alasan", default="")
    e = sub.add_parser("ubah")
    e.add_argument("id")
    e.add_argument("--caption")
    e.add_argument("--caption-per", default="")
    e.add_argument("--judul")
    e.add_argument("--jadwal")
    ls = sub.add_parser("daftar")
    ls.add_argument("--status", choices=("menunggu", "disetujui", "ditolak", "dikirim", "sebagian", "gagal"))
    sub.add_parser("bersihkan", help="hapus media lama yang sudah tayang")
    return p


def jalankan(argv, app=None):
    args = parser().parse_args(argv)
    app = app or App()
    c = args.cmd
    if c == "akun":
        return {"akun": app.akun(args.segarkan)}
    if c == "unggah":
        return app.unggah(args.berkas, args.rencana)
    if c == "gambar":
        return app.gambar(args.prompt, args.rasio)
    if c == "draf":
        return app.draf(args.platform.split(","), args.tipe, args.caption, _json(args.caption_per), args.judul,
                        args.media, args.jadwal, [x for x in args.akun.split(",") if x])
    if c == "setujui":
        return app.setujui(args.id, args.pesan)
    if c == "tolak":
        return app.tolak(args.id, args.alasan)
    if c == "ubah":
        return app.ubah(args.id, args.caption, _json(args.caption_per), args.judul, args.jadwal)
    if c == "daftar":
        return {"draf": app.daftar(args.status)}
    if c == "bersihkan":
        return app.bersihkan()
    return getattr(app, c)(args.id)


def main(argv=None):
    try:
        hasil = jalankan(sys.argv[1:] if argv is None else argv)
        print(json.dumps({"ok": True, **(hasil if isinstance(hasil, dict) else {"hasil": hasil})},
                         ensure_ascii=False, indent=1))
        return 0
    except (Galat, GalatDraf, GalatRepliz, platform.GalatPlatform, media.GalatMedia,
            cloudinary.GalatCloudinary, gambar.GalatGambar) as e:
        print(json.dumps({"ok": False, "galat": str(e)}, ensure_ascii=False))
        return 1
