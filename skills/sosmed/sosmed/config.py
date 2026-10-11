"""Pengaturan dari environment (diisi OpenClaw `skills.entries.sosmed.env` atau berkas ~/.sosmed/.env).

Kunci rahasia hanya dibaca dari environment / berkas .env di VPS — tidak pernah ditulis ke log atau keluaran.
"""
import os
from dataclasses import dataclass
from pathlib import Path


def _muat_env_berkas(path):
    """Isi os.environ dari berkas KEY=VALUE tanpa menimpa yang sudah ada."""
    try:
        teks = Path(path).read_text(encoding="utf-8")
    except OSError:
        return
    for baris in teks.splitlines():
        baris = baris.strip()
        if not baris or baris.startswith("#") or "=" not in baris:
            continue
        k, v = baris.split("=", 1)
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)


@dataclass
class Config:
    data_dir: Path
    zona: str
    repliz_access: str
    repliz_secret: str
    repliz_base: str
    openai_key: str
    openai_image_model: str
    cld_cloud: str
    cld_key: str
    cld_secret: str
    hari_simpan: int

    @property
    def ada_cloudinary(self):
        return bool(self.cld_cloud and self.cld_key and self.cld_secret)


def muat():
    data_dir = Path(os.environ.get("SOSMED_DATA") or Path.home() / ".sosmed")
    _muat_env_berkas(data_dir / ".env")
    e = os.environ.get
    return Config(
        data_dir=data_dir,
        zona=e("SOSMED_TZ", "Asia/Jakarta"),
        repliz_access=e("REPLIZ_ACCESS_KEY", ""),
        repliz_secret=e("REPLIZ_SECRET_KEY", ""),
        repliz_base=e("REPLIZ_BASE_URL", "https://api.repliz.com").rstrip("/"),
        openai_key=e("OPENAI_API_KEY", ""),
        openai_image_model=e("OPENAI_IMAGE_MODEL", "gpt-image-1"),
        cld_cloud=e("CLOUDINARY_CLOUD_NAME", ""),
        cld_key=e("CLOUDINARY_API_KEY", ""),
        cld_secret=e("CLOUDINARY_API_SECRET", ""),
        hari_simpan=int(e("SOSMED_HARI_SIMPAN", "3")),
    )
