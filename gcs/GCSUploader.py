from google.cloud import storage
import uuid

class GCSUploader:
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        self.client = None
        self.bucket = None

    def _get_bucket(self):
        if self.bucket is None:
            self.client = storage.Client()
            self.bucket = self.client.bucket(self.bucket_name)
        return self.bucket

    def upload_file(self, file, filename: str) -> str:
        """
        Sube un archivo a GCS y devuelve la URL pública.
        """
        blob_name = f"uploads/{uuid.uuid4()}-{filename}"
        blob = self._get_bucket().blob(blob_name)
        blob.upload_from_file(file, content_type="image/jpeg")  # ajusta content_type según tu caso
        blob.make_public()
        return blob.public_url

    def upload_bytes(
        self,
        blob_path: str,
        data: bytes,
        content_type: str = "image/jpeg",
    ) -> str:
        """Sube bytes a una ruta fija del bucket y devuelve la URL pública."""
        blob = self._get_bucket().blob(blob_path)
        blob.upload_from_string(data, content_type=content_type)
        blob.make_public()
        return blob.public_url

    def upload_multiple(self, files: list) -> list:
        """
        Sube múltiples archivos y devuelve una lista de URLs.
        """
        urls = []
        for f in files:
            url = self.upload_file(f.file, f.filename)
            urls.append(url)
        return urls
