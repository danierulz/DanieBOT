from urllib.parse import urlparse

from provider_importers.types import ImportedProduct, ProviderImportError

SOCHIC_HOSTS = {"sochic.com.ar", "www.sochic.com.ar"}
LASLOCAS_HOSTS = {"laslocas.com", "www.laslocas.com"}


def detect_provider(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    host = parsed.netloc.lower()
    if host in SOCHIC_HOSTS:
        return "sochic"
    if host in LASLOCAS_HOSTS:
        return "laslocas"
    raise ProviderImportError(
        "URL no reconocida. Solo se aceptan productos de sochic.com.ar o laslocas.com."
    )


def fetch_product(url: str) -> ImportedProduct:
    provider = detect_provider(url)
    if provider == "sochic":
        from provider_importers.sochic import fetch_sochic_product

        return fetch_sochic_product(url)
    if provider == "laslocas":
        from provider_importers.laslocas import fetch_laslocas_product

        return fetch_laslocas_product(url)
    raise ProviderImportError(f"Proveedor no soportado: {provider}")
