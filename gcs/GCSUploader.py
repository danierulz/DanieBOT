from google.cloud import storage
import uuid

class GCSUploader:
    def __init__(self, bucket_name: str):
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)

    def upload_file(self, file, filename: str) -> str:
        """
        Sube un archivo a GCS y devuelve la URL pública.
        """
        blob_name = f"uploads/{uuid.uuid4()}-{filename}"
        blob = self.bucket.blob(blob_name)
        blob.upload_from_file(file, content_type="image/jpeg")  # ajusta content_type según tu caso
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