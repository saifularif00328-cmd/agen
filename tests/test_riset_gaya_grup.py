"""Riset tren, gaya bahasa, catatan grup FB, dan penulisan provider AI kustom."""
import importlib.util
import json
from pathlib import Path

import pytest

from sosmed import riset
from sosmed.cli import Galat
from sosmed.gaya import BAWAAN, GalatGaya
from sosmed.grup import GalatGrup, normal_url
from sosmed.repliz import GalatRepliz

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0"><channel>
<item><title>timnas indonesia</title><ht:approx_traffic>500+</ht:approx_traffic><pubDate>Mon, 12 Oct 2026</pubDate>
 <ht:news_item><ht:news_item_title>Timnas menang</ht:news_item_title><ht:news_item_url>https://berita.id/a</ht:news_item_url>
 <ht:news_item_source>Berita</ht:news_item_source></ht:news_item></item>
<item><title>harga emas</title><ht:approx_traffic>200+</ht:approx_traffic></item>
</channel></rss>"""


class Resp:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status


def test_parse_tren_dan_ambil(app, monkeypatch):
    t = riset.parse_tren(RSS)
    assert t[0]["topik"] == "timnas indonesia" and t[0]["pencarian"] == "500+"
    assert t[0]["berita"][0]["url"] == "https://berita.id/a" and t[1]["berita"] == []
    assert len(riset.parse_tren(RSS, jumlah=1)) == 1
    with pytest.raises(riset.GalatRiset):
        riset.parse_tren("<bukan xml")

    class S:
        def get(self, url, **kw):
            assert url.endswith("geo=ID")
            return Resp(RSS)
    app.session = S()
    assert app.tren()["tren"][1]["topik"] == "harga emas"


def test_riset_threads_dan_musik(app, repliz):
    repliz.cari_threads = lambda aid, kata, mode, urut: {"docs": [
        {"description": "Kopi susu gula aren enak", "type": "text", "owner": {"name": "Budi"}}]}
    r = app.tren_threads("kopi")
    assert r["hasil"][0]["teks"].startswith("Kopi") and r["hasil"][0]["pemilik"] == "Budi"
    repliz.musik_tiktok = lambda g, n, rg: {"docs": [{"id": "1", "artist": "A", "name": "Lagu", "duration": 30}]}
    assert app.musik_tiktok()["musik"][0]["judul"] == "Lagu"

    def tolak(*a):
        raise GalatRepliz("upgrade", 402)
    repliz.musik_tiktok = tolak
    with pytest.raises(Galat, match="add-on"):
        app.musik_tiktok()
    repliz.akun_data = [a for a in repliz.akun_data if a["type"] != "threads"]
    app.gudang.simpan_akun([])
    with pytest.raises(Galat, match="Threads"):
        app.tren_threads("kopi")


def test_gaya_bahasa(app):
    g = app.gaya
    assert g.lihat()["deskripsi"] == BAWAAN
    g.atur("Gaya anak muda Medan, pakai 'bah' sesekali")
    for i in range(12):
        g.tambah_contoh(f"Contoh caption nomor {i} yang cukup panjang")
    d = g.lihat()
    assert "Medan" in d["panduan"] and len(d["contoh"]) == 10 and d["contoh"][0].endswith("nomor 2 yang cukup panjang")
    g.hapus_contoh(1)
    assert len(g.lihat()["contoh"]) == 9
    with pytest.raises(GalatGaya):
        g.hapus_contoh(99)
    with pytest.raises(GalatGaya):
        g.atur("")
    assert g.reset()["contoh"] == []


def test_grup_facebook(app):
    assert normal_url("https://m.facebook.com/groups/jualbelimedan/?ref=share") == \
        "https://www.facebook.com/groups/jualbelimedan"
    with pytest.raises(GalatGrup):
        normal_url("https://facebook.com/somepage")
    g = app.grup
    a = g.simpan("Jual Beli Medan", "https://www.facebook.com/groups/jualbelimedan", "120rb", "Promo hanya Sabtu", "medan")
    assert a["baru"] and a["status"] == "belum"
    b = g.simpan("Jual Beli Medan (resmi)", "https://facebook.com/groups/jualbelimedan/")
    assert not b["baru"] and len(g.daftar()) == 1 and g.daftar()[0]["nama"] == "Jual Beli Medan (resmi)"
    g.tandai(a["id"], "aktif", "admin ramah", promo=True)
    assert g.daftar(status="aktif")[0]["terakhir_promo"]
    assert g.daftar(topik="medan") and not g.daftar(topik="bali")
    with pytest.raises(GalatGrup):
        g.tandai(a["id"], "spam")
    g.hapus(a["id"])
    assert g.daftar() == []


def test_cli_gaya_dan_grup(app, capsys, monkeypatch):
    from sosmed import cli
    monkeypatch.setattr(cli, "App", lambda: app)
    assert cli.main(["gaya", "atur", "Formal dan sopan"]) == 0
    assert json.loads(capsys.readouterr().out)["deskripsi"] == "Formal dan sopan"
    assert cli.main(["grup", "simpan", "--nama", "X", "--url", "https://facebook.com/x"]) == 1
    assert "link grup" in capsys.readouterr().out


def _atur_ai():
    p = Path(__file__).resolve().parent.parent / "deploy" / "atur_ai.py"
    spec = importlib.util.spec_from_file_location("atur_ai", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_tambah_provider_kustom(tmp_path):
    m = _atur_ai()
    cfg = tmp_path / "openclaw.json"
    cfg.write_text(json.dumps({"agents": {"defaults": {"model": {"primary": "google/gemini-2.5-flash"}}},
                               "channels": {"telegram": {"x": 1}}}))
    refs = m.tambah_provider(cfg, "relay", "https://api.relay.test/v1/", "sk-rahasia", ["gpt-4o-mini", "claude-x"],
                             utama="gpt-4o-mini")
    d = json.loads(cfg.read_text())
    assert refs == ["relay/gpt-4o-mini", "relay/claude-x"]
    p = d["models"]["providers"]["relay"]
    assert p["baseUrl"] == "https://api.relay.test/v1" and p["api"] == "openai-completions"
    assert d["agents"]["defaults"]["model"]["primary"] == "relay/gpt-4o-mini" and d["channels"]["telegram"] == {"x": 1}
    assert list(tmp_path.glob("openclaw.json.bak-*"))
    for args in [("Relay!", "https://a/v1", "k", ["m"]), ("relay", "ftp://a", "k", ["m"]),
                 ("relay", "https://a/v1", "", ["m"]), ("relay", "https://a/v1", "k", [" "])]:
        with pytest.raises(m.GalatAtur):
            m.tambah_provider(cfg, *args)
    with pytest.raises(m.GalatAtur, match="utama"):
        m.tambah_provider(cfg, "relay", "https://a/v1", "k", ["m"], utama="lain")


def test_daftar_model_9router():
    import io
    m = _atur_ai()

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    dilihat = {}

    def buka(req, timeout):
        dilihat["url"], dilihat["auth"] = req.full_url, req.get_header("Authorization")
        return R(json.dumps({"object": "list", "data": [{"id": "kr/claude-sonnet-4.5"}, {"id": "cx/gpt-5.5"},
                                                        {"id": "kr/claude-sonnet-4.5"}]}).encode())
    assert m.daftar_model("http://127.0.0.1:20128/v1/", "sk-x", buka) == ["cx/gpt-5.5", "kr/claude-sonnet-4.5"]
    assert dilihat == {"url": "http://127.0.0.1:20128/v1/models", "auth": "Bearer sk-x"}

    def gagal(req, timeout):
        raise OSError("tolak")
    assert m.daftar_model("http://127.0.0.1:20128/v1", "k", gagal) == []
