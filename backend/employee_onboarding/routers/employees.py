from fastapi import APIRouter, status, HTTPException, UploadFile, Form, File, Depends
from ..schemas.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from ..models.employee import Employee
from database import db_dependency
from sqlalchemy import select
import uuid
from ..service.employees import EmployeeService
from ..repository.employee import EmployeeRepository
from ..exceptions import EmployeeNotFound
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession


employee_router = APIRouter(prefix="/employee", tags=["employees"])
async def get_employee_repository(db: AsyncSession = Depends(get_db)):
    return EmployeeRepository(db=db)

async def get_employee_service(repo: EmployeeRepository = Depends(get_employee_repository)):
    return EmployeeService(repo)

# reads all employees info
@employee_router.get("", response_model=list[EmployeeResponse])
async def get_all_employees(service: EmployeeService = Depends(get_employee_service)):
    try: 
        employees = await service.get_all_employees()  
        return employees
    except EmployeeNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employees not found")

#creates a new employee
@employee_router.post("", response_model=EmployeeResponse , status_code=status.HTTP_201_CREATED) #should add the minio image storage here
async def create_employee(first_name: str = Form(...), last_name: str = Form(...), role: str = Form(...), employee_pictures: list[UploadFile] = File(...), service: EmployeeService = Depends(get_employee_service)):
    employee = EmployeeCreate(first_name=first_name, last_name= last_name, role= role)
    created_employee = await service.create_employee(employee=employee, employee_pictures=employee_pictures)
    return created_employee

# gets an employee by id 
@employee_router.get("/{id}", response_model=EmployeeResponse)
async def get_employee_by_id(id: uuid.UUID, service: EmployeeService = Depends(get_employee_service)):
    try:
        employee = await service.get_employee_by_id(id)
        return employee
    except EmployeeNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

# updates employee info partially
@employee_router.patch("/{id}" , response_model=EmployeeResponse)
async def update_employee_partially(id: uuid.UUID, employee_new_data: EmployeeUpdate, service: EmployeeService = Depends(get_employee_service)):
    try:
        updated_employee = await service.update_employee(id, updated_employee_info=employee_new_data)
        return updated_employee
    except EmployeeNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

# deletes an employee
@employee_router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee_by_id(id: uuid.UUID, service: EmployeeService = Depends(get_employee_service)):
    try: 
        await service.delete_employee(id=id)
    except EmployeeNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

