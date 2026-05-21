import tempfile
from io import BytesIO

import pytest

from gcs.local_uploader import LocalFilesystemUploader


@pytest.fixture
def uploader(tmp_path):
    upload_dir = tmp_path / "uploads"
    return LocalFilesystemUploader(
        upload_dir=str(upload_dir),
        public_base_url="http://localhost:5000",
    )


def test_upload_file_returns_static_url(uploader, tmp_path):
    data = b"fake-image-bytes"
    file_obj = BytesIO(data)
    url = uploader.upload_file(file_obj, "foto.jpg")

    assert url.startswith("http://localhost:5000/static/uploads/")
    assert "foto.jpg" in url
    files = list((tmp_path / "uploads").rglob("*.jpg"))
    assert len(files) == 1
    assert files[0].read_bytes() == data


def test_upload_bytes_preserves_blob_path(uploader, tmp_path):
    rel = "images/ficha-123/imagen.jpg"
    url = uploader.upload_bytes(rel, b"binary", content_type="image/jpeg")

    assert url == f"http://localhost:5000/static/uploads/{rel}"
    assert (tmp_path / "uploads" / "images" / "ficha-123" / "imagen.jpg").is_file()


def test_upload_bytes_rejects_path_traversal(uploader):
    with pytest.raises(ValueError):
        uploader.upload_bytes("../etc/passwd", b"x")


def test_create_uploader_local_backend(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_UPLOAD_DIR", tempfile.mkdtemp())
    from gcs.storage_factory import create_uploader

    uploader = create_uploader()
    assert isinstance(uploader, LocalFilesystemUploader)
