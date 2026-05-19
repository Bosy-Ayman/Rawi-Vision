from sqlalchemy.ext.asyncio import AsyncSession
from ..schemas.attendance import AttendanceCreate, AttendanceResponse
from ..models.attendance import Attendance
from uuid import UUID
from sqlalchemy import select, func
from datetime import date
from employee_onboarding.models.employee import Employee

class AttendanceRepository:
    def __init__(self, db:AsyncSession):
        self.db = db
    
    async def create_attendance_record(self, attendance: AttendanceCreate):
        try:
            # checking if a record already exists for this employee today
            result = await self.db.execute(select(Attendance).where(Attendance.employee_id == attendance.employee_id, func.date(Attendance.day) == date.today()))
            existing = result.scalar_one_or_none()
            if existing:
                return existing  
            new_attendance_record = Attendance(employee_id=attendance.employee_id)
            self.db.add(new_attendance_record)
            await self.db.flush()
            return new_attendance_record
        except Exception as error:
            raise error
    
    async def read_all_attendance_records(self):
        stmt = select(
            Attendance.id, Attendance.employee_id, Attendance.day, Attendance.date_created,
            Employee.first_name, Employee.last_name, Employee.role, Employee.profile_image_url
        ).join(Employee, Attendance.employee_id == Employee.id)
        result = await self.db.execute(stmt)
        rows = result.all()
        combined_records = []
        for row in rows:
            combined_records.append({
                "id": row.id,
                "employee_id": row.employee_id,
                "day": row.day,
                "date_created": row.date_created,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "role": row.role,
                "profile_image_url": row.profile_image_url
            })
        return combined_records
    
    async def read_attendance_record_by_employee_id(self, employee_id: UUID):
        result = await self.db.execute(select(Attendance).where(Attendance.employee_id == employee_id))
        attendance_records = result.scalars().all()
        return attendance_records
    
    async def delete_attendance_record(self, attendance_record:Attendance):
        try:
            await self.db.delete(attendance_record)
        except Exception as error:
            raise error