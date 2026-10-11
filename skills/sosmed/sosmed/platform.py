"""Aturan tipe postingan per platform (sesuai dokumentasi Repliz)."""

PLATFORM = ("facebook", "instagram", "tiktok", "threads", "youtube")
ALIAS = {"fb": "facebook", "ig": "instagram", "tt": "tiktok", "yt": "youtube", "th": "threads",
         "facebook": "facebook", "instagram": "instagram", "tiktok": "tiktok", "threads": "threads",
         "youtube": "youtube"}
TIPE = ("text", "image", "album", "video", "reel", "story")

# tipe → platform yang mendukung (Repliz: reel hanya FB, story FB+IG, text FB+Threads, YouTube hanya video)
DUKUNG = {
    "text": {"facebook", "threads"},
    "image": {"facebook", "instagram", "threads", "tiktok"},
    "album": {"facebook", "instagram", "threads", "tiktok"},
    "video": {"facebook", "instagram", "threads", "tiktok", "youtube"},
    "reel": {"facebook"},
    "story": {"facebook", "instagram"},
}


class GalatPlatform(Exception):
    pass


def normal(daftar):
    hasil = []
    for p in daftar:
        p = p.strip().lower()
        if not p:
            continue
        if p == "semua":
            return list(PLATFORM)
        if p not in ALIAS:
            raise GalatPlatform(f"Platform tidak dikenal: {p}. Pilih: {', '.join(PLATFORM)} atau 'semua'.")
        if ALIAS[p] not in hasil:
            hasil.append(ALIAS[p])
    if not hasil:
        raise GalatPlatform("Pilih minimal satu platform.")
    return hasil


def tipe_untuk(tipe, platform):
    """Kembalikan (tipe_repliz | None, catatan). None = dilewati untuk platform ini."""
    if tipe == "reel" and platform != "facebook":
        return "video", f"{platform}: Reels dikirim sebagai video (di Instagram video otomatis tampil sebagai Reels)."
    if platform in DUKUNG[tipe]:
        return tipe, None
    if tipe == "text":
        return None, f"{platform}: tidak bisa posting teks saja (butuh foto/video) — dilewati."
    if tipe in ("image", "album"):
        return None, f"{platform}: tidak menerima foto — dilewati."
    if tipe == "story":
        return None, f"{platform}: tidak punya Story lewat Repliz — dilewati."
    return None, f"{platform}: tipe {tipe} tidak didukung — dilewati."


def cek_media(tipe, medias):
    jenis = [m["type"] for m in medias]
    if tipe == "text":
        if medias:
            raise GalatPlatform("Postingan teks tidak memakai media; pilih tipe image/video.")
        return
    if not medias:
        raise GalatPlatform(f"Tipe {tipe} butuh media.")
    if tipe == "image" and (len(medias) != 1 or jenis != ["image"]):
        raise GalatPlatform("Tipe image = tepat 1 foto. Untuk beberapa foto pakai tipe album.")
    if tipe == "album" and not (2 <= len(medias) <= 10):
        raise GalatPlatform("Album berisi 2–10 foto/video.")
    if tipe in ("video", "reel") and (len(medias) != 1 or jenis != ["video"]):
        raise GalatPlatform(f"Tipe {tipe} = tepat 1 video.")
    if tipe == "story" and len(medias) != 1:
        raise GalatPlatform("Story = tepat 1 foto atau video.")
