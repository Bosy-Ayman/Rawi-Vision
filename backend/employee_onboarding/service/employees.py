from ..repository.employee import EmployeeRepository
from ..schemas.employee import EmployeeCreate, EmployeeUpdate
from ..utils.minio_storage_client import MinioStorageClient
from fastapi import UploadFile
from sqlalchemy.exc import SQLAlchemyError
from minio.error import S3Error
import uuid
from ..exceptions import EmployeeNotFound

class EmployeeService:
    def __init__ (self, repository: EmployeeRepository):
        self.repository = repository
        self.object_storage = MinioStorageClient()
        self.bucket_name = "employee-pictures"
    
    # saga orchestration is used to ensure both the metadata of the employee and their pictures are uploaded to the system
    async def create_employee(self, employee: EmployeeCreate, employee_pictures: list[UploadFile]):
        uploaded_files=[]
        try: 
            new_employee = await self.repository.create_employee(employee=employee)
            for picture in employee_pictures:
                await self.object_storage.add_object_to_bucket(picture, bucket_name= self.bucket_name, object_name=f"{new_employee.id}/{picture.filename}")
                uploaded_files.append(picture)
           
            await self.repository.db.commit()
            await self.repository.db.refresh(new_employee)
            return new_employee

        except (SQLAlchemyError, S3Error, Exception) as error:
            self.repository.db.rollback()
            for obj in uploaded_files:  # maybe i should wrap this in a try except as well?
                self.object_storage.remove_object_from_bucket(obj, self.bucket_name)
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
            employee = await self.repository.read_employee_by_id(id)
            if not employee:
                raise EmployeeNotFound("No employees found")
            return employee
        except (SQLAlchemyError) as error:
            raise error  #check if the error need to be more descriptive
    
    async def delete_employee(self, id: uuid.UUID): # the pictures of the employee should be deleted after a while maybe? 
        try:
            employee = await self.repository.read_employee_by_id(id)
            if not employee:
                raise EmployeeNotFound(f"employee with {id} not found")
            await self.repository.delete_employee(employee=employee)
            await self.repository.db.commit()
        except (SQLAlchemyError) as error:
            self.repository.db.rollback()
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