from fastapi import APIRouter, status, HTTPException, Depends
from ..service.attendance import AttendanceService
from ..repository.attendance import AttendanceRepository
from ..schemas.attendance import AttendanceCreate, AttendanceResponse
from sqlalchemy.ext.asyncio import AsyncSession
from database import db_dependency
from database import get_db
from uuid import UUID

attendance_router = APIRouter(prefix= "/attendance", tags=["attendance"])

def get_attendance_repository(db: AsyncSession=Depends(get_db)):
    return AttendanceRepository(db=db)

def get_attendance_service(repo:AttendanceRepository = Depends(get_attendance_repository)):
    return AttendanceService(repository=repo)

@attendance_router.get("", response_model=list[AttendanceResponse])
async def get_all_attendance_records(service: AttendanceService= Depends(get_attendance_service)):
    try:
        attendance_records = await service.get_all_attendance_records()
        return attendance_records
    except Exception as error:
        raise error

@attendance_router.get("/{id}", response_model=list[AttendanceResponse])
async def get_attendance_record_by_employee_id(id: UUID, service: AttendanceService= Depends(get_attendance_service)):
    try:
        attendance_records = await service.get_attendance_record_by_employee_id(employee_id=id)
        return attendance_records
    except Exception as error:
        raise error

@attendance_router.post("", response_model=AttendanceResponse)
async def create_attendance_record(attendance_create: AttendanceCreate, service: AttendanceService = Depends(get_attendance_service)):
    try:
        new_attendance_record = await service.create_attendance_record(attendance=attendance_create)
        return new_attendance_record
    except Exception as error:
        raise error