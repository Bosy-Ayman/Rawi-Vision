from .minio_client import minio_client_init
from io import BytesIO
from fastapi import UploadFile

class MinioStorageClient:
    def __init__(self):
        self.client = minio_client_init()

    def ensure_bucket_exists(self, bucket_name):
        if not self.client.bucket_exists(bucket_name= bucket_name):
            self.client.make_bucket(bucket_name= bucket_name)
    
    async def add_object_to_bucket(self, upload_file: UploadFile, bucket_name: str, object_name:str):
        self.ensure_bucket_exists(bucket_name=bucket_name)
        file_content = await upload_file.read()
        file_stream = BytesIO(file_content)
        self.client.put_object(bucket_name=bucket_name, object_name=object_name, data=file_stream, length=len(file_content), content_type=upload_file.content_type)

    def remove_object_from_bucket(self, object, bucket_name, object_name):
        self.client.remove_object(bucket_name=bucket_name, object_name=object_name)