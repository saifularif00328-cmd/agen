"""Profil gaya bahasa pemilik (berkas gaya.json di SOSMED_DATA)."""
import json
import os
from pathlib import Path

BAWAAN = ("Santai & akrab: bahasa sehari-hari yang sopan, sapaan \"kak\", kalimat pendek, emoji secukupnya "
          "(1–3), ajakan bertindak yang ramah di akhir, 3–8 hashtag relevan. Hindari bahasa kaku dan klaim berlebihan.")
MAKS_CONTOH = 10


class GalatGaya(Exception):
    pass


class Gaya:
    def __init__(self, data_dir):
        self.f = Path(data_dir) / "gaya.json"
        self.f.parent.mkdir(parents=True, exist_ok=True)

    def _baca(self):
        try:
            d = json.loads(self.f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        return {"deskripsi": d.get("deskripsi") or BAWAAN, "contoh": d.get("contoh") or []}

    def _tulis(self, d):
        tmp = Path(str(self.f) + ".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.f)

    def lihat(self):
        d = self._baca()
        panduan = "Gaya bahasa pemilik:\n" + d["deskripsi"]
        if d["contoh"]:
            panduan += "\n\nContoh caption pemilik (tiru nada & pilihan katanya, jangan disalin mentah):\n" + \
                       "\n---\n".join(d["contoh"])
        return {"deskripsi": d["deskripsi"], "contoh": d["contoh"], "panduan": panduan}

    def atur(self, deskripsi):
        deskripsi = (deskripsi or "").strip()
        if len(deskripsi) < 5:
            raise GalatGaya("Tulis deskripsi gaya bahasa minimal satu kalimat.")
        d = self._baca()
        d["deskripsi"] = deskripsi[:1500]
        self._tulis(d)
        return self.lihat()

    def tambah_contoh(self, teks):
        teks = (teks or "").strip()
        if len(teks) < 10:
            raise GalatGaya("Contoh caption terlalu pendek.")
        d = self._baca()
        d["contoh"] = (d["contoh"] + [teks[:2200]])[-MAKS_CONTOH:]
        self._tulis(d)
        return self.lihat()

    def hapus_contoh(self, nomor):
        d = self._baca()
        if not 1 <= nomor <= len(d["contoh"]):
            raise GalatGaya(f"Nomor contoh harus 1–{len(d['contoh'])}.")
        d["contoh"].pop(nomor - 1)
        self._tulis(d)
        return self.lihat()

    def reset(self):
        self._tulis({"deskripsi": BAWAAN, "contoh": []})
        return self.lihat()
