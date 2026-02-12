from fastapi import UploadFile, Form, File
from database import db_dependency
from ..models.employee import Employee
from sqlalchemy import select
import uuid
from ..schemas.employee import EmployeeUpdate, EmployeeCreate, EmployeeResponse
from sqlalchemy.ext.asyncio import AsyncSession

# im following -no commits in repository-
class EmployeeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_employee(self, employee: EmployeeCreate):
        new_employee = Employee(first_name = employee.first_name, last_name= employee.last_name, role= employee.role)
        self.db.add(new_employee)
        await self.db.flush()
        return new_employee
    
    async def read_all_employees(self):
        result = await self.db.execute(select(Employee))
        employees = result.scalars().all()
        return employees
    
    async def read_employee_by_id(self, id: uuid.UUID):
        result = await self.db.execute(select(Employee).where(Employee.id == id))
        employee = result.scalars().one_or_none()
        return employee

    async def delete_employee(self, employee: EmployeeResponse):
        await self.db.delete(employee)
        return employee