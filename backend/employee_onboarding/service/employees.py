from ..repository.employee import EmployeeRepository
from ..schemas.employee import EmployeeCreate, EmployeeUpdate
from ..utils.minio_storage_client import MinioStorageClient
from fastapi import UploadFile
from sqlalchemy.exc import SQLAlchemyError
from minio.error import S3Error
import uuid
from ..exceptions import EmployeeNotFound
from ..celery_tasks.embedding import create_embedding_task
from .employee_images import EmployeeImagesService
from ..schemas.employee import EmployeeResponse

class EmployeeService:
    def __init__ (self, repository: EmployeeRepository, object_storage:MinioStorageClient, employee_image_service: EmployeeImagesService): # constructor dependency injection
        self.repository = repository
        self.bucket_name = "employee-pictures"
        self.object_storage = object_storage
        self.employee_image_service = employee_image_service
    
    async def create_employee(self, employee: EmployeeCreate, employee_pictures: list[UploadFile]):
        uploaded_files=[]
        try: 
            new_employee = await self.repository.create_employee(employee=employee)
            for picture in employee_pictures:
                await self.object_storage.add_object_to_bucket(picture, bucket_name= self.bucket_name, object_name=f"{new_employee.id}/{picture.filename}")
                uploaded_files.append(picture)
            # need to figure out a workaround if the celery task fails - using saga pattern 
            create_embedding_task.delay(self.bucket_name, new_employee.id)
            return new_employee
        except (SQLAlchemyError, S3Error, Exception) as error:
            self.object_storage.remove_objects_from_bucket(bucket_name=self.bucket_name, object_name=str(new_employee.id))
            raise error

    async def get_all_employees(self):
        try:
            employees = await self.repository.read_all_employees()
            if not employees:
                raise EmployeeNotFound("No employees found")
            return employees
        except (SQLAlchemyError) as error:
            raise error

    async def get_employee_by_id(self, id: uuid.UUID):
        try:
            employee_data = await self.repository.read_employee_by_id(id)
            employee_images = self.employee_image_service.get_employee_images(employee_id=id)
            employee_response = EmployeeResponse(id=employee_data.id, date_created=employee_data.date_created, first_name= employee_data.first_name, last_name= employee_data.last_name, role= employee_data.role, embedding= employee_data.embedding, embedding_status= employee_data.embedding_status, images=employee_images["image_urls"])
            if not employee_data:
                raise EmployeeNotFound("No employees found")
            return employee_response
        except (SQLAlchemyError) as error:
            raise error  #check if the error need to be more descriptive
    
    async def delete_employee(self, id: uuid.UUID): # the pictures of the employee should be deleted after a while maybe? 
        try:
            employee = await self.repository.read_employee_by_id(id)
            if not employee:
                raise EmployeeNotFound(f"employee with {id} not found")
            await self.repository.delete_employee(employee=employee)
            self.employee_image_service.delete_employee_images(employee_id=employee.id)
        except (SQLAlchemyError) as error:
            raise error  
        except (Exception) as exception_error:
            raise exception_error

    async def update_employee(self, id: uuid.UUID, updated_employee_info: EmployeeUpdate):
        try:
            employee = await self.repository.read_employee_by_id(id)
            if not employee:
                raise EmployeeNotFound(f"employee with {id} not found")
            update_data = updated_employee_info.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(employee, field, value)
            await self.repository.db.commit()
            await self.repository.db.refresh(employee)
            return employee
        except (SQLAlchemyError) as error:
            self.repository.db.rollback()
            raise error  
        except (Exception) as exception_error:
            raise exception_error