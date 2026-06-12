from ..repository.attendance import AttendanceRepository
from ..schemas.attendance import AttendanceCreate
from ..utils.exceptions import AttendanceRecordNotFound
from uuid import UUID

class AttendanceService:
    def __init__(self, repository: AttendanceRepository):
        self.repo = repository
    
    async def create_attendance_record(self, attendance: AttendanceCreate):
        try:
            new_attendance_record = await self.repo.create_attendance_record(attendance=attendance)
            await self.repo.db.commit()
            await self.repo.db.refresh(new_attendance_record)
            return new_attendance_record
        except Exception as error:
            raise error
    
    async def get_all_attendance_records(self):
        try:
            attendance_records = await self.repo.read_all_attendance_records()
            return attendance_records
        except Exception as error:
            raise error
    
    async def get_attendance_record_by_employee_id(self, employee_id):
        try:
            attendance_records = await self.repo.read_attendance_record_by_employee_id(employee_id=employee_id)
            return attendance_records
        except Exception as error:
            raise error
    
    async def delete_attendance_record(self, employee_id:UUID):
        try:
            attendance_records = await self.repo.read_attendance_record_by_employee_id(employee_id)
            if not attendance_records:
                raise AttendanceRecordNotFound
            else:
                for record in attendance_records:
                    await self.repo.delete_attendance_record(record)
            await self.repo.db.commit()
        except Exception as error:
            await self.repo.db.rollback()
            raise error