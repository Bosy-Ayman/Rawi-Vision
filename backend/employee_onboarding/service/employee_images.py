import uuid
from ..utils.minio_storage_client import MinioStorageClient
from urllib.parse import urlparse
from pathlib import PurePosixPath

class EmployeeImagesService:
    def __init__(self, minio_client: MinioStorageClient): # constructor dependency injection
        self.bucket_name = "employee-pictures" #hard coded bucket-name to avoid confusion, should this be changed?
        self.minio_client = minio_client
    
    def get_employee_images(self, employee_id: uuid.UUID):
        try:
            image_urls = self.minio_client.get_object_urls(bucket_name=self.bucket_name, prefix=str(employee_id))
            return {"employee_id": employee_id, "image_urls":image_urls}
        except Exception as error:
            raise error

    def delete_employee_images(self, employee_id: uuid.UUID):
        try:
            self.minio_client.remove_objects_from_bucket(bucket_name=self.bucket_name, object_name=str(employee_id))
        except Exception as error:
            raise error