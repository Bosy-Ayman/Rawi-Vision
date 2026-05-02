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

    def remove_objects_from_bucket(self, bucket_name, object_name):
        objects = self.client.list_objects(bucket_name=bucket_name, prefix=object_name, recursive=True)
        for obj in objects:
            self.client.remove_object(bucket_name=bucket_name, object_name=obj.object_name)
        
    def get_objects_binary(self, bucket_name, prefix):
        result=[]
        objects = self.client.list_objects(bucket_name=bucket_name, prefix=prefix, recursive=True)
        for obj in objects:
            image = self.client.get_object(bucket_name=bucket_name, object_name=obj.object_name)
            result.append(image.read())
        return result
    
    def get_object_urls(self, bucket_name, prefix):
        img_urls = []
        objects = self.client.list_objects(bucket_name=bucket_name, prefix=prefix, recursive=True)
        for obj in objects:
            image = self.client.presigned_get_object(bucket_name=bucket_name, object_name=obj.object_name) # can add an expiry date to the urls, by default is 7 days
            img_urls.append(image)
        return img_urls

