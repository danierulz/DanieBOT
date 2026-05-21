"""Almacenamiento de imágenes en disco para desarrollo local (sin GCP)."""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import BinaryIO

_UNSAFE_PATH = re.compile(r"\.\.|^[\\/]")


def _safe_relative_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip("/")
    if not normalized or _UNSAFE_PATH.search(normalized):
        raise ValueError(f"Ruta no permitida: {path}")
    return normalized


def _safe_filename(filename: str) -> str:
    name = os.path.basename(filename.replace("\\", "/"))
    if not name or name in (".", ".."):
        raise ValueError(f"Nombre de archivo no permitido: {filename}")
    return name


class LocalFilesystemUploader:
    """Guarda archivos bajo LOCAL_UPLOAD_DIR y devuelve URLs servidas por /static."""

    def __init__(
        self,
        upload_dir: str | None = None,
        public_base_url: str | None = None,
    ) -> None:
        self.upload_dir = Path(upload_dir or os.getenv("LOCAL_UPLOAD_DIR", "static/uploads"))
        self.public_base_url = (public_base_url or os.getenv("SITE_PUBLIC_URL", "http://localhost:5000")).rstrip(
            "/"
        )
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        # Ruta web: /static/uploads/... (static/ ya está montado en FastAPI)
        self._static_prefix = "/static/uploads"

    def _public_url(self, relative_path: str) -> str:
        rel = _safe_relative_path(relative_path)
        return f"{self.public_base_url}{self._static_prefix}/{rel}"

    def _write_bytes(self, relative_path: str, data: bytes) -> str:
        rel = _safe_relative_path(relative_path)
        dest = self.upload_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return self._public_url(rel)

    def _read_fileobj(self, file: BinaryIO) -> bytes:
        if hasattr(file, "seek"):
            file.seek(0)
        return file.read()

    def upload_file(self, file: BinaryIO, filename: str) -> str:
        safe_name = _safe_filename(filename)
        rel = f"uploads/{uuid.uuid4()}-{safe_name}"
        return self._write_bytes(rel, self._read_fileobj(file))

    def upload_bytes(
        self,
        blob_path: str,
        data: bytes,
        content_type: str = "image/jpeg",
    ) -> str:
        return self._write_bytes(blob_path, data)

    def upload_multiple(self, files: list) -> list:
        urls = []
        for f in files:
            url = self.upload_file(f.file, f.filename)
            urls.append(url)
        return urls
