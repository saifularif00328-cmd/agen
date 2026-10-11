"""Periksa & siapkan berkas media dengan ffmpeg/ffprobe (harus terpasang di VPS)."""
import json
import os
import subprocess
from pathlib import Path

GAMBAR = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
VIDEO = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
MAKS_GAMBAR = 8 * 1024 * 1024          # batas foto Instagram
RASIO = {"1:1": (1, 1), "4:5": (4, 5), "9:16": (9, 16), "16:9": (16, 9)}


class GalatMedia(Exception):
    pass


def jalankan(args):
    """Dipisah agar bisa ditiru di tes."""
    try:
        return subprocess.run(args, check=True, capture_output=True, text=True, timeout=600).stdout
    except FileNotFoundError:
        raise GalatMedia(f"{args[0]} belum terpasang di VPS (sudo apt install ffmpeg).")
    except subprocess.CalledProcessError as e:
        raise GalatMedia(f"{args[0]} gagal: {(e.stderr or '')[-300:]}")


def jenis(path):
    ext = Path(path).suffix.lower()
    if ext in GAMBAR:
        return "image"
    if ext in VIDEO:
        return "video"
    raise GalatMedia(f"Format {ext or '(tanpa ekstensi)'} tidak didukung. Kirim foto JPG/PNG atau video MP4/MOV.")


def info(path):
    out = jalankan(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    d = json.loads(out or "{}")
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    rot = str((v.get("tags") or {}).get("rotate", "0"))
    for sd in v.get("side_data_list") or []:
        if "rotation" in sd:
            rot = str(sd["rotation"])
    if rot.lstrip("-") in ("90", "270"):
        w, h = h, w
    return {"lebar": w, "tinggi": h, "durasi": float((d.get("format") or {}).get("duration") or 0)}


def nama_rasio(w, h):
    if not (w and h):
        return "?"
    r = w / h
    return min(RASIO, key=lambda k: abs(RASIO[k][0] / RASIO[k][1] - r))


def siapkan_gambar(path, folder):
    """Instagram hanya menerima JPEG ≤ 8 MB → ubah PNG/WEBP/HEIC ke JPG dan kompres bila terlalu besar."""
    path = Path(path)
    if path.suffix.lower() in (".jpg", ".jpeg") and os.path.getsize(path) <= MAKS_GAMBAR:
        return path
    hasil = Path(folder) / (path.stem + ".jpg")
    for q in (2, 4, 7, 10):              # skala kualitas ffmpeg mjpeg: kecil = bagus
        jalankan(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-vf", "scale='min(2160,iw)':-2",
                  "-q:v", str(q), str(hasil)])
        if os.path.getsize(hasil) <= MAKS_GAMBAR:
            return hasil
    raise GalatMedia("Foto tetap > 8 MB setelah dikompres. Kirim foto yang lebih kecil.")


def potong_rasio(path, rasio, folder):
    """Potong tengah gambar ke rasio tertentu (mis. hasil AI 2:3 → 4:5 atau 9:16)."""
    a, b = RASIO[rasio]
    hasil = Path(folder) / (Path(path).stem + f"-{a}x{b}.jpg")
    crop = f"crop='min(iw,ih*{a}/{b})':'min(ih,iw*{b}/{a})'"
    jalankan(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-vf", crop, "-q:v", "2", str(hasil)])
    return hasil


def thumbnail(path, folder):
    """Ambil satu bingkai video (detik ke-1) sebagai sampul."""
    hasil = Path(folder) / (Path(path).stem + "-sampul.jpg")
    jalankan(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", str(path), "-frames:v", "1",
              "-q:v", "3", str(hasil)])
    return hasil


def peringatan_video(inf, tipe):
    """Peringatan (bukan penolakan) agar agen bisa memberi tahu pemilik."""
    p = []
    rasio = nama_rasio(inf["lebar"], inf["tinggi"])
    if tipe in ("reel", "story") and rasio != "9:16":
        p.append(f"Video berasio {rasio}; Reels/Story idealnya tegak 9:16.")
    if tipe == "story" and inf["durasi"] > 60:
        p.append("Story video maksimal 60 detik; bagian setelahnya bisa terpotong/ditolak.")
    if inf["durasi"] and inf["durasi"] < 3:
        p.append("Video kurang dari 3 detik; Instagram/TikTok bisa menolak.")
    return p
