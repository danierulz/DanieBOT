"""Factory de almacenamiento: GCS en producción, disco local en desarrollo."""
from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from gcs.GCSUploader import GCSUploader
from gcs.local_uploader import LocalFilesystemUploader


@runtime_checkable
class StorageUploader(Protocol):
    def upload_file(self, file, filename: str) -> str: ...

    def upload_bytes(self, blob_path: str, data: bytes, content_type: str = "image/jpeg") -> str: ...

    def upload_multiple(self, files: list) -> list: ...


def create_uploader() -> StorageUploader:
    backend = os.getenv("STORAGE_BACKEND", "gcs").strip().lower()
    if backend == "local":
        return LocalFilesystemUploader()
    bucket = os.getenv("GCS_BUCKET_NAME", "bucket_laslocas_prod")
    return GCSUploader(bucket_name=bucket)
