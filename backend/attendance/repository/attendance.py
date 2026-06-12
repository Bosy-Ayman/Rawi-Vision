from sqlalchemy.ext.asyncio import AsyncSession
from ..schemas.attendance import AttendanceCreate, AttendanceResponse
from ..models.attendance import Attendance
from uuid import UUID
from sqlalchemy import select, func, desc
from datetime import date
from employee_onboarding.models.employee import Employee

class AttendanceRepository:
    def __init__(self, db:AsyncSession):
        self.db = db
    
    async def create_attendance_record(self, attendance: AttendanceCreate):
        try:
            new_attendance_record = Attendance(
                employee_id=attendance.employee_id,
                look_count=1,
                camera_id=attendance.camera_id,
                duration_seconds=attendance.duration_seconds
            )
            self.db.add(new_attendance_record)
            await self.db.flush()
            return new_attendance_record
        except Exception as error:
            raise error

    async def update_attendance_duration(self, employee_id: UUID, camera_id: str, duration_seconds: float):
        try:
            # Find the most recent attendance record for this employee and camera
            stmt = select(Attendance).where(
                Attendance.employee_id == employee_id,
                Attendance.camera_id == camera_id
            ).order_by(desc(Attendance.date_created)).limit(1)
            
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                existing.duration_seconds = duration_seconds
                existing.last_seen = func.now()
                await self.db.flush()
                return existing
            return None
        except Exception as error:
            raise error
    
    async def read_all_attendance_records(self):
        stmt = select(
            Attendance.id, Attendance.employee_id, Attendance.day, Attendance.date_created, 
            Attendance.last_seen, Attendance.look_count, Attendance.camera_id, Attendance.duration_seconds,
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
                "last_seen": row.last_seen,
                "look_count": row.look_count,
                "camera_id": row.camera_id,
                "duration_seconds": row.duration_seconds,
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