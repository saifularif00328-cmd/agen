"""Alur utama: unggah → draf → setujui → kirim → status/ulang/batal → bersihkan."""
import json
from datetime import timedelta

import pytest

from sosmed import cli, cloudinary, draf
from sosmed.cli import Galat
from sosmed.platform import GalatPlatform


def _foto(tmp_path, nama="a.jpg"):
    p = tmp_path / nama
    p.write_bytes(b"\xff\xd8foto")
    return p


def test_unggah_foto_dan_video(app, repliz, tmp_path, ffmpeg_palsu):
    r = app.unggah(_foto(tmp_path))
    assert r["media"] == {"type": "image", "url": "https://storage.repliz.com/u/1.jpg",
                          "thumbnail": "https://storage.repliz.com/u/1.jpg"}
    v = tmp_path / "klip.mp4"
    v.write_bytes(b"video")
    r = app.unggah(v, rencana="story")
    m = r["media"]
    assert m["type"] == "video" and m["url"].endswith(".mp4") and m["thumbnail"].endswith(".jpg")
    assert m["rasio"] == "9:16" and m["durasi"] == 20.5 and r["peringatan"] == []
    # catatan media menyimpan sampul untuk dipakai draf
    assert app.gudang.media()[m["url"]]["thumbnail"] == m["thumbnail"]


def test_png_diubah_ke_jpg_dan_format_salah_ditolak(app, repliz, tmp_path, ffmpeg_palsu):
    r = app.unggah(_foto(tmp_path, "b.png"))
    assert r["media"]["url"].endswith(".jpg")                     # IG wajib JPEG
    with pytest.raises(Exception, match="tidak didukung"):
        app.unggah(_foto(tmp_path, "c.gif"))
    with pytest.raises(Galat, match="tidak ditemukan"):
        app.unggah(tmp_path / "tidak-ada.jpg")


def test_storage_penuh_pindah_ke_cloudinary(app, repliz, tmp_path, ffmpeg_palsu, monkeypatch):
    repliz.penuh = True
    monkeypatch.setattr(cloudinary, "unggah", lambda cfg, path, session=None: {
        "provider": "cloudinary", "id": "sosmed-agen/x", "jenis": "image",
        "url": "https://res.cloudinary.com/demo/image/upload/x.jpg"})
    r = app.unggah(_foto(tmp_path))
    assert r["disimpan_di"] == "cloudinary" and "cloudinary" in r["media"]["url"]
    app.cfg.cld_cloud = ""
    with pytest.raises(Galat, match="Cloudinary belum disetel"):
        app.unggah(_foto(tmp_path, "d.jpg"))


def _draf_video(app, tmp_path, tipe="reel", platform="semua", **kw):
    v = tmp_path / "klip.mp4"
    v.write_bytes(b"video")
    url = app.unggah(v)["media"]["url"]
    return app.draf([platform], tipe, kw.pop("caption", "Promo hari ini! #diskon"), medias=[url], **kw)


def test_draf_reel_menyesuaikan_platform(app, repliz, tmp_path, ffmpeg_palsu):
    d = _draf_video(app, tmp_path, "reel")
    data = app.gudang.ambil(d["id"])
    tipe = {t["platform"]: t["tipe"] for t in data["target"]}
    assert tipe == {"facebook": "reel", "instagram": "video", "tiktok": "video", "threads": "video",
                    "youtube": "video"}
    assert data["status"] == "menunggu" and data["judul"] == "Promo hari ini! #diskon"   # judul YouTube otomatis
    assert "Balas OK" in d["pratinjau"] and "Reels dikirim sebagai video" in d["pratinjau"]


def test_draf_story_dan_teks_melewati_platform_tak_didukung(app, repliz, tmp_path, ffmpeg_palsu):
    d = _draf_video(app, tmp_path, "story")
    plats = {t["platform"] for t in app.gudang.ambil(d["id"])["target"]}
    assert plats == {"facebook", "instagram"} and "dilewati" in d["pratinjau"]
    d = app.draf(["fb", "ig", "threads"], "text", "Selamat pagi!")
    assert {t["platform"] for t in app.gudang.ambil(d["id"])["target"]} == {"facebook", "threads"}
    with pytest.raises(Galat, match="Tidak ada tujuan"):
        app.draf(["ig", "tiktok"], "text", "Halo")


def test_validasi_media_dan_caption(app, repliz, tmp_path, ffmpeg_palsu):
    foto = app.unggah(_foto(tmp_path))["media"]["url"]
    with pytest.raises(GalatPlatform, match="album"):
        app.draf(["ig"], "image", "x", medias=[foto, foto])
    with pytest.raises(GalatPlatform, match="2–10"):
        app.draf(["ig"], "album", "x", medias=[foto])
    with pytest.raises(GalatPlatform, match="butuh media"):
        app.draf(["ig"], "image", "x")
    with pytest.raises(Galat, match="bukan berkas lokal"):
        app.draf(["ig"], "image", "x", medias=["/tmp/a.jpg"])
    with pytest.raises(Galat, match="Threads 501 karakter"):
        app.draf(["threads"], "image", "a" * 501, medias=[foto])
    d = app.draf(["threads", "ig"], "image", "a" * 501, caption_per={"threads": "pendek"}, medias=[foto])
    caps = {t["platform"]: t["caption"] for t in app.gudang.ambil(d["id"])["target"]}
    assert caps == {"threads": "pendek", "instagram": "a" * 501}
    with pytest.raises(GalatPlatform, match="tidak dikenal"):
        app.draf(["myspace"], "image", "x", medias=[foto])


def test_kirim_wajib_disetujui(app, repliz, tmp_path, ffmpeg_palsu):
    foto = app.unggah(_foto(tmp_path))["media"]["url"]
    d = app.draf(["ig", "fb"], "image", "Halo", medias=[foto], jadwal="2030-01-01 07:00")
    with pytest.raises(Galat, match="belum disetujui"):
        app.kirim(d["id"])
    assert repliz.jadwal_dibuat == []
    with pytest.raises(Galat, match="--pesan"):
        app.setujui(d["id"], "  ")
    app.setujui(d["id"], "OK")
    r = app.kirim(d["id"])
    assert r["status"] == "dikirim" and len(repliz.jadwal_dibuat) == 2
    b = repliz.jadwal_dibuat[0]
    assert b["scheduleAt"] == "2030-01-01T00:00:00.000Z"           # 07:00 WIB = 00:00 UTC
    assert b["type"] == "image" and b["medias"][0]["type"] == "image" and b["description"] == "Halo"
    wajib = {"title", "description", "topic", "type", "medias", "meta", "additionalInfo", "replies",
             "accountId", "scheduleAt"}
    assert wajib <= set(b)
    with pytest.raises(Galat, match="belum disetujui"):             # tidak bisa dikirim dua kali
        app.kirim(d["id"])


def test_ubah_setelah_disetujui_minta_persetujuan_ulang(app, repliz, tmp_path, ffmpeg_palsu):
    foto = app.unggah(_foto(tmp_path))["media"]["url"]
    d = app.draf(["ig"], "image", "Halo", medias=[foto])
    app.setujui(d["id"], "ok")
    r = app.ubah(d["id"], caption="Halo semua")
    assert r["status"] == "menunggu" and "Halo semua" in r["pratinjau"]
    with pytest.raises(Galat):
        app.kirim(d["id"])


def test_kirim_sebagian_lalu_ulang(app, repliz, tmp_path, ffmpeg_palsu):
    foto = app.unggah(_foto(tmp_path))["media"]["url"]
    d = app.draf(["ig", "fb"], "image", "Halo", medias=[foto], jadwal="2030-01-01 07:00")
    app.setujui(d["id"], "OK")
    repliz.gagal_akun = {"fb1"}
    r = app.kirim(d["id"])
    assert r["status"] == "sebagian" and any("galat" in h for h in r["hasil"])
    repliz.gagal_akun = set()
    r = app.ulang(d["id"])
    assert r["kirim_ulang"]["status"] == "dikirim"
    assert [b["accountId"] for b in repliz.jadwal_dibuat] == ["ig1", "fb1"]   # IG tidak dobel
    repliz.status_jadwal["s1"] = "failed"
    assert app.ulang(d["id"])["diulang"] == ["instagram"] and repliz.diulang == ["s1"]
    st = app.status(d["id"])
    assert {h["status"] for h in st["hasil"]} == {"failed", "pending"}
    r = app.batal(d["id"])
    assert r["dibatalkan"] == ["facebook"]


def test_jadwal_sekarang_diperbarui_saat_persetujuan_terlambat(app, repliz, tmp_path, ffmpeg_palsu, monkeypatch):
    foto = app.unggah(_foto(tmp_path))["media"]["url"]
    d = app.draf(["ig"], "image", "Halo", medias=[foto], jadwal="sekarang")
    app.setujui(d["id"], "OK")
    kini = draf.sekarang_utc()
    monkeypatch.setattr(cli, "sekarang_utc", lambda: kini + timedelta(hours=1))
    monkeypatch.setattr(draf, "sekarang_utc", lambda: kini + timedelta(hours=1))
    app.kirim(d["id"])
    assert repliz.jadwal_dibuat[0]["scheduleAt"] > (kini + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")


def test_jadwal_tertentu_yang_lewat_ditolak(app, repliz, tmp_path, ffmpeg_palsu, monkeypatch):
    foto = app.unggah(_foto(tmp_path))["media"]["url"]
    d = app.draf(["ig"], "image", "Halo", medias=[foto], jadwal="2030-01-01 07:00")
    app.setujui(d["id"], "OK")
    jauh = draf.sekarang_utc().replace(year=2031)
    monkeypatch.setattr(cli, "sekarang_utc", lambda: jauh)
    with pytest.raises(Galat, match="sudah lewat"):
        app.kirim(d["id"])


def test_parse_jadwal(monkeypatch):
    assert draf.parse_jadwal("2030-05-01 19:30", "Asia/Jakarta") == "2030-05-01T12:30:00.000Z"
    with pytest.raises(draf.GalatDraf, match="lewat"):
        draf.parse_jadwal("2020-01-01 07:00", "Asia/Jakarta")
    with pytest.raises(draf.GalatDraf, match="Format"):
        draf.parse_jadwal("besok pagi", "Asia/Jakarta")
    assert draf.parse_jadwal("sekarang", "Asia/Jakarta") > draf.sekarang_utc().strftime("%Y-%m-%dT%H:%M")
    assert draf.parse_jadwal("07:00", "Asia/Jakarta").endswith("T00:00:00.000Z")


def test_bersihkan_media_lama(app, repliz, tmp_path, ffmpeg_palsu, monkeypatch):
    foto = app.unggah(_foto(tmp_path))["media"]["url"]
    lama = app.unggah(_foto(tmp_path, "lama.jpg"))["media"]["url"]
    d = app.draf(["ig"], "image", "Halo", medias=[foto])           # draf aktif → fotonya dipertahankan
    kini = draf.sekarang_utc()
    monkeypatch.setattr(cli, "sekarang_utc", lambda: kini + timedelta(days=10))
    r = app.bersihkan()
    assert r["dihapus"] == 1 and ("berkas", "f2") in repliz.dihapus
    assert foto in app.gudang.media() and lama not in app.gudang.media()
    assert d["id"]


def test_cli_keluaran_json(app, repliz, capsys, monkeypatch):
    monkeypatch.setattr(cli, "App", lambda: app)
    assert cli.main(["akun"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] and {a["platform"] for a in out["akun"]} == {"facebook", "instagram", "tiktok", "threads",
                                                                   "youtube"}
    assert cli.main(["kirim", "abc123"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out == {"ok": False, "galat": "Draf abc123 tidak ditemukan."}
    assert cli.main(["draf", "--platform", "ig", "--tipe", "image", "--caption-per", "[1]"]) == 1
    assert "objek JSON" in capsys.readouterr().out
