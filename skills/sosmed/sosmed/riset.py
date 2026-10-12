"""Riset tren: Google Trends harian (RSS publik, tanpa key) + ringkasan hasil riset Repliz."""
import xml.etree.ElementTree as ET

import requests

URL_TREN = "https://trends.google.com/trending/rss?geo={geo}"
NS = {"ht": "https://trends.google.com/trending/rss"}


class GalatRiset(Exception):
    pass


def _teks(el, tag):
    x = el.find(tag, NS)
    return (x.text or "").strip() if x is not None and x.text else ""


def parse_tren(xml_teks, jumlah=15):
    try:
        akar = ET.fromstring(xml_teks)
    except ET.ParseError:
        raise GalatRiset("Data Google Trends tidak bisa dibaca (format berubah?).")
    hasil = []
    for item in akar.iter("item"):
        berita = [{"judul": _teks(n, "ht:news_item_title"), "sumber": _teks(n, "ht:news_item_source"),
                   "url": _teks(n, "ht:news_item_url")} for n in item.findall("ht:news_item", NS)][:2]
        hasil.append({"topik": _teks(item, "title"), "pencarian": _teks(item, "ht:approx_traffic"),
                      "mulai": _teks(item, "pubDate"), "berita": berita})
        if len(hasil) >= jumlah:
            break
    return hasil


def tren_google(geo="ID", jumlah=15, session=None):
    r = (session or requests).get(URL_TREN.format(geo=geo), timeout=30,
                                  headers={"User-Agent": "Mozilla/5.0 (sosmed-agen)"})
    if r.status_code >= 400:
        raise GalatRiset(f"Google Trends menjawab {r.status_code}.")
    return parse_tren(r.text, jumlah)


def ringkas_threads(data, jumlah=10):
    hasil = []
    for d in (data or {}).get("docs", [])[:jumlah]:
        hasil.append({"teks": (d.get("description") or d.get("title") or "")[:300], "tipe": d.get("type"),
                      "pemilik": (d.get("owner") or {}).get("name") or (d.get("owner") or {}).get("username"),
                      "suka": d.get("likeCount") or d.get("likes"), "balasan": d.get("replyCount"),
                      "url": d.get("permalink") or d.get("url")})
    return hasil


def ringkas_musik(data, jumlah=15):
    return [{"judul": m.get("name"), "artis": m.get("artist"), "durasi": m.get("duration"), "id": m.get("id")}
            for m in (data or {}).get("docs", [])[:jumlah]]
