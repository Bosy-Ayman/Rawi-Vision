from fastapi import APIRouter, Depends, HTTPException, status
from ..schemas.employee_images import EmployeeImagesResponse
from ..service.employee_images import EmployeeImagesService 
from minio.error import S3Error
import uuid
from ..utils.minio_storage_client import MinioStorageClient

employee_image_router = APIRouter(prefix="/employee_image", tags=["employee images"])

def get_minio_client():
    return MinioStorageClient()

def get_employee_image_service(minio_client:MinioStorageClient = Depends(get_minio_client)):
    return EmployeeImagesService(minio_client=minio_client)

@employee_image_router.get("/{id}", response_model=EmployeeImagesResponse, status_code=status.HTTP_200_OK)
def get_all_employee_images(id: uuid.UUID, service: EmployeeImagesService = Depends(get_employee_image_service)):
    try:
        result = service.get_employee_images(employee_id=id)
        return result
    except (S3Error) as error:
        if error.code == "NoSuchKey":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image objects not found") 
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@employee_image_router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_all_employee_images(id: uuid.UUID, service:EmployeeImagesService =  Depends(get_employee_image_service)):
    try:
        service.delete_employee_images(employee_id=id)
    except (S3Error) as error:
        if error.code == "NoSuchKey":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image objects not found") 
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)