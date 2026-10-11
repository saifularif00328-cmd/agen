import json
from pathlib import Path

import pytest

from sosmed import media
from sosmed.cli import App
from sosmed.config import Config
from sosmed.repliz import GalatRepliz, KuotaHabis


@pytest.fixture
def cfg(tmp_path):
    return Config(data_dir=tmp_path / "data", zona="Asia/Jakarta", repliz_access="a", repliz_secret="b",
                  repliz_base="https://api.repliz.test", openai_key="sk-uji", openai_image_model="gpt-image-1",
                  cld_cloud="demo", cld_key="k", cld_secret="s", hari_simpan=3)


class ReplizPalsu:
    """Pengganti Repliz untuk tes App (tanpa jaringan)."""

    def __init__(self):
        self.akun_data = [
            {"id": "fb1", "type": "facebook", "name": "Toko", "username": "toko", "isConnected": True},
            {"id": "ig1", "type": "instagram", "name": "Toko", "username": "toko.ig", "isConnected": True},
            {"id": "tt1", "type": "tiktok", "name": "Toko", "username": "toko.tt", "isConnected": True},
            {"id": "th1", "type": "threads", "name": "Toko", "username": "toko.th", "isConnected": True},
            {"id": "yt1", "type": "youtube", "name": "Toko", "username": "TokoTV", "isConnected": True},
        ]
        self.jadwal_dibuat, self.berkas, self.dihapus, self.diulang = [], [], [], []
        self.gagal_akun = set()
        self.penuh = False
        self.status_jadwal = {}

    def akun(self):
        return self.akun_data

    def unggah(self, path):
        if self.penuh:
            raise KuotaHabis("penuh", 402)
        n = len(self.berkas) + 1
        self.berkas.append(path)
        return {"provider": "repliz", "id": f"f{n}", "url": f"https://storage.repliz.com/u/{n}{Path(path).suffix}"}

    def buat_jadwal(self, body):
        if body["accountId"] in self.gagal_akun:
            raise GalatRepliz("account not found", 404)
        self.jadwal_dibuat.append(body)
        return f"s{len(self.jadwal_dibuat)}"

    def jadwal(self, sid):
        return {"status": self.status_jadwal.get(sid, "pending")}

    def ulang(self, sid):
        self.diulang.append(sid)

    def hapus_jadwal(self, sid):
        self.dihapus.append(("jadwal", sid))

    def hapus_berkas(self, fid):
        self.dihapus.append(("berkas", fid))


@pytest.fixture
def repliz():
    return ReplizPalsu()


@pytest.fixture
def app(cfg, repliz):
    return App(cfg=cfg, repliz=repliz)


@pytest.fixture
def ffmpeg_palsu(monkeypatch):
    """Tiru ffmpeg/ffprobe: ffmpeg menulis berkas keluaran kecil, ffprobe mengembalikan info video 9:16 20 dtk."""
    panggilan = []

    def jalankan(args):
        panggilan.append(args)
        if args[0] == "ffprobe":
            return json.dumps({"streams": [{"codec_type": "video", "width": 1080, "height": 1920}],
                               "format": {"duration": "20.5"}})
        Path(args[-1]).write_bytes(b"\xff\xd8jpg")
        return ""

    monkeypatch.setattr(media, "jalankan", jalankan)
    return panggilan
