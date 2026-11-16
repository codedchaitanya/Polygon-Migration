"""
Test-case file storage.

    from problems.storage import get_storage
    storage = get_storage()          # provider chosen by STORAGE_PROVIDER
    storage.upload_test_case(problem_id, 1, input_text, output_text)

To add a provider: implement `TestCaseStorage` in a new module and register a
builder for it in `_PROVIDERS` below. The migration flow does not change.
"""
from django.conf import settings

from .base import StorageError, TestCaseStorage

__all__ = ["get_storage", "StorageError", "TestCaseStorage"]


def _build_azure():
    from .azure_blob import AzureBlobStorage
    return AzureBlobStorage(
        container_name=settings.AZURE_CONTAINER_NAME,
        connection_string=settings.AZURE_STORAGE_CONNECTION_STRING,
        account_url=settings.AZURE_STORAGE_ACCOUNT_URL,
        tenant_id=settings.AZURE_TENANT_ID,
        client_id=settings.AZURE_CLIENT_ID,
        username=settings.AZURE_USERNAME,
        password=settings.AZURE_PASSWORD,
    )


_PROVIDERS = {
    "azure": _build_azure,
}


def get_storage():
    """Return the storage provider selected by the STORAGE_PROVIDER setting."""
    provider = (settings.STORAGE_PROVIDER or "azure").strip().lower()
    try:
        build = _PROVIDERS[provider]
    except KeyError:
        supported = ", ".join(sorted(_PROVIDERS))
        raise StorageError(
            f"Unknown STORAGE_PROVIDER '{provider}'. Supported: {supported}."
        ) from None
    return build()
