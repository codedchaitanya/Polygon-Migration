"""Azure Blob Storage provider."""
import logging

from azure.core.exceptions import AzureError
from azure.storage.blob import BlobServiceClient

from .base import StorageError, TestCaseStorage

logger = logging.getLogger(__name__)


class AzureBlobStorage(TestCaseStorage):
    """
    Stores files as blobs in one Azure container.

    Authentication, in order of preference:
      1. `connection_string` (storage account access key or SAS).
      2. Azure AD username/password (`account_url`, `tenant_id`, `client_id`,
         `username`, `password`). Does not work for accounts with MFA.
    """

    name = "Azure Blob Storage"

    def __init__(self, container_name, connection_string=None, account_url=None,
                 tenant_id=None, client_id=None, username=None, password=None):
        if not container_name:
            raise StorageError("AZURE_CONTAINER_NAME is not set.")
        self.container_name = container_name

        try:
            if connection_string:
                service = BlobServiceClient.from_connection_string(connection_string)
            elif all([account_url, tenant_id, client_id, username, password]):
                from azure.identity import UsernamePasswordCredential
                credential = UsernamePasswordCredential(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    username=username,
                    password=password,
                )
                service = BlobServiceClient(account_url=account_url, credential=credential)
            else:
                raise StorageError(
                    "Azure storage is not configured. Set AZURE_STORAGE_CONNECTION_STRING, or "
                    "AZURE_STORAGE_ACCOUNT_URL with AZURE_TENANT_ID, AZURE_CLIENT_ID, "
                    "AZURE_USERNAME and AZURE_PASSWORD."
                )
        except (AzureError, ValueError) as e:
            raise StorageError(f"Could not create the Azure Blob client: {e}") from e

        self.container = service.get_container_client(container_name)

    def upload_file(self, path, data):
        try:
            self.container.upload_blob(name=path, data=data, overwrite=True)
        except AzureError as e:
            raise StorageError(f"Azure upload failed for '{path}': {e}") from e
        logger.info("Uploaded %s to container %s", path, self.container_name)

    def list_files(self, prefix):
        try:
            return [blob.name for blob in self.container.list_blobs(name_starts_with=prefix)]
        except AzureError as e:
            raise StorageError(f"Azure listing failed for '{prefix}': {e}") from e

    def delete_file(self, path):
        try:
            self.container.delete_blob(path)
        except AzureError as e:
            raise StorageError(f"Azure delete failed for '{path}': {e}") from e
        logger.info("Deleted %s from container %s", path, self.container_name)
