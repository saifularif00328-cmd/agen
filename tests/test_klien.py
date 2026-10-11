"""Klien HTTP: Repliz (unggah 3 langkah, 402, galat), Cloudinary (tanda tangan), OpenAI Images."""
import base64
import json

import pytest

from sosmed import cloudinary, gambar, media
from sosmed.repliz import GalatRepliz, KuotaHabis, Repliz, body_jadwal


class Resp:
    def __init__(self, status=200, data=None, content=b""):
        self.status_code, self._data = status, data
        self.content = content or (json.dumps(data).encode() if data is not None else b"")
        self.text = self.content.decode(errors="ignore")

    def json(self):
        if self._data is None:
            raise ValueError
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class Sesi:
    def __init__(self, jawaban):
        self.jawaban, self.log, self.auth = list(jawaban), [], None

    def request(self, metode, url, **kw):
        self.log.append((metode, url, kw))
        return self.jawaban.pop(0)

    def put(self, url, **kw):
        kw["data"] = kw["data"].read()
        return self.request("PUT", url, **kw)

    def post(self, url, **kw):
        return self.request("POST", url, **kw)

    def get(self, url, **kw):
        return self.request("GET", url, **kw)


def test_repliz_unggah_tiga_langkah(cfg, tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"12345")
    s = Sesi([Resp(200, {"id": "F1", "upload": "https://r2.test/up?sig=1", "url": "https://storage.repliz.com/v.mp4"}),
              Resp(200), Resp(204)])
    r = Repliz(cfg, session=s).unggah(str(f))
    assert r == {"provider": "repliz", "id": "F1", "url": "https://storage.repliz.com/v.mp4"}
    (m1, u1, k1), (m2, u2, k2), (m3, u3, _) = s.log
    assert (m1, u1) == ("POST", "https://api.repliz.test/public/storage/file/init")
    assert k1["json"] == {"filename": "v.mp4", "size": 5, "mimetype": "video/mp4"}
    assert (m2, u2) == ("PUT", "https://r2.test/up?sig=1") and k2["data"] == b"12345" and k2["auth"] is None
    assert (m3, u3) == ("POST", "https://api.repliz.test/public/storage/file/F1/complete")
    assert s.auth == ("a", "b")


def test_repliz_402_dan_galat(cfg, tmp_path):
    f = tmp_path / "a.jpg"
    f.write_bytes(b"x")
    with pytest.raises(KuotaHabis):
        Repliz(cfg, session=Sesi([Resp(402, {"code": 402, "message": "upgrade"})])).unggah(str(f))
    with pytest.raises(GalatRepliz, match="account not found"):
        Repliz(cfg, session=Sesi([Resp(404, {"message": "account not found"})])).buat_jadwal({})
    cfg.repliz_secret = ""
    with pytest.raises(GalatRepliz, match="belum diisi"):
        Repliz(cfg)


def test_repliz_akun_berhalaman(cfg):
    s = Sesi([Resp(200, {"docs": [{"id": 1}], "hasNextPage": True}),
              Resp(200, {"docs": [{"id": 2}], "hasNextPage": False})])
    assert [a["id"] for a in Repliz(cfg, session=s).akun()] == [1, 2]
    assert s.log[1][2]["params"]["page"] == 2


def test_body_jadwal_lengkap():
    b = body_jadwal(account_id="A", tipe="story", caption="", judul="", schedule_at="2030-01-01T00:00:00.000Z",
                    medias=[{"type": "video", "url": "u", "thumbnail": "t"}], ai=True)
    assert b["additionalInfo"]["isAiGenerated"] is True and b["replies"] == [] and b["topic"] == ""
    assert b["meta"] == {"title": "", "description": "", "url": ""}


def test_tanda_tangan_cloudinary():
    # contoh resmi dokumentasi Cloudinary
    p = {"eager": "w_400,h_300,c_pad|w_260,h_200,c_crop", "public_id": "sample_image", "timestamp": 1315060510}
    assert cloudinary._tanda(p, "abcd") == "bfd09f95f331f558cbd1320e67aa8d488770583e"


def test_cloudinary_unggah(cfg, tmp_path):
    f = tmp_path / "a.jpg"
    f.write_bytes(b"x")
    s = Sesi([Resp(200, {"public_id": "sosmed-agen/a", "resource_type": "image",
                         "secure_url": "https://res.cloudinary.com/demo/a.jpg"})])
    r = cloudinary.unggah(cfg, str(f), session=s)
    assert r["url"].startswith("https://res.cloudinary.com") and r["id"] == "sosmed-agen/a"
    _, url, kw = s.log[0]
    assert url == "https://api.cloudinary.com/v1_1/demo/auto/upload"
    assert kw["data"]["folder"] == "sosmed-agen" and kw["data"]["api_key"] == "k" and "signature" in kw["data"]
    assert "s" not in kw["data"].values()                         # secret tidak ikut terkirim


def test_gambar_openai_dipotong_ke_rasio(cfg, tmp_path, monkeypatch, ffmpeg_palsu):
    b64 = base64.b64encode(b"\x89PNGdata").decode()
    s = Sesi([Resp(200, {"data": [{"b64_json": b64}]})])
    path = gambar.buat(cfg, "kopi susu di meja kayu", "4:5", tmp_path, session=s)
    _, url, kw = s.log[0]
    assert url == "https://api.openai.com/v1/images/generations"
    assert kw["json"]["size"] == "1024x1536" and kw["headers"]["Authorization"] == "Bearer sk-uji"
    assert path.name.endswith("-4x5.jpg")
    assert any("crop=" in " ".join(a) for a in ffmpeg_palsu)
    s = Sesi([Resp(400, {"error": {"message": "Your request was rejected"}})])
    with pytest.raises(gambar.GalatGambar, match="rejected"):
        gambar.buat(cfg, "x", "1:1", tmp_path, session=s)


def test_info_video_rotasi(monkeypatch):
    monkeypatch.setattr(media, "jalankan", lambda a: json.dumps({
        "streams": [{"codec_type": "video", "width": 1920, "height": 1080, "side_data_list": [{"rotation": -90}]}],
        "format": {"duration": "70"}}))
    inf = media.info("x.mp4")
    assert (inf["lebar"], inf["tinggi"]) == (1080, 1920) and media.nama_rasio(1080, 1920) == "9:16"
    assert media.peringatan_video(inf, "story") == ["Story video maksimal 60 detik; bagian setelahnya bisa terpotong/ditolak."]
    assert "9:16" in media.peringatan_video({"lebar": 1920, "tinggi": 1080, "durasi": 10}, "reel")[0]
