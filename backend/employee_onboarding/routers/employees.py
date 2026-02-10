from fastapi import APIRouter, status, HTTPException
from ..schemas.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from ..models.employee import Employee
from database import db_dependency
from sqlalchemy import select
import uuid

employee_router = APIRouter(prefix="/employee", tags=["employees"])

# reads all employees info
@employee_router.get("",response_model=list[EmployeeResponse])
async def get_all_employees(db: db_dependency):
    results = await db.execute(select(Employee))
    employees = results.scalars().all() 
    return employees

#creates a new employee
@employee_router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(employee: EmployeeCreate, db:db_dependency):
    new_employee = Employee(first_name=employee.first_name, last_name=employee.last_name,role= employee.role)
    db.add(new_employee)
    await db.commit()
    await db.refresh(new_employee)
    return new_employee

# gets an employee by id 
@employee_router.get("/{id}", response_model=EmployeeResponse)
async def get_employee_by_id(id: uuid.UUID, db:db_dependency):
    results = await db.execute(select(Employee).where(Employee.id == id))
    employees = results.scalars().one_or_none() 
    if employees is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail= "Employee not found")
    return employees

# updates employee info partially
@employee_router.patch("/{id}" , response_model=EmployeeResponse)
async def update_employee_partially(id: uuid.UUID, employee_new_data: EmployeeUpdate, db: db_dependency):
    result = await db.execute(select(Employee).where(Employee.id == id))
    employee = result.scalars().one_or_none()
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail= "Employee not found")
    update_data = employee_new_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(employee, field, value)
    await db.commit()
    await db.refresh(employee)
    return employee

# deletes an employee
@employee_router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee_by_id(id: uuid.UUID, db:db_dependency):
    result = await db.execute(select(Employee).where(Employee.id == id))
    employee = result.scalars().one_or_none()
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail= "Employee not found")
    await db.delete(employee)
    await db.commit()
