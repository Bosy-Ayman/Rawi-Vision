from fastapi import APIRouter, status, HTTPException
from ..schemas.onboarding_files import OnboardingFileCreate, OnboardingFileResponse, OnboardingFileUpdate
from ..models.onboarding_file import OnboardingFile
from database import db_dependency
from sqlalchemy import select

onboarding_files_router = APIRouter(prefix="/file", tags=["file onboarding"])

#retrives all onboarding files
@onboarding_files_router.get("", response_model=list[OnboardingFileResponse])
async def get_all_onboarding_files(db: db_dependency):
    result =  await db.execute(select(OnboardingFile))
    files =  result.scalars().all()
    return files 

# adds a new onboarding file
@onboarding_files_router.post("", response_model=OnboardingFileResponse, status_code = status.HTTP_201_CREATED)
async def add_new_onboarding_file(file: OnboardingFileCreate, db:db_dependency):
    new_file = OnboardingFile(filename= file.filename, path = file.path)
    db.add(new_file)
    await db.commit()
    await db.refresh(new_file)
    return new_file

# updates a file partially
@onboarding_files_router.patch("/{id}", response_model=OnboardingFileResponse)
async def update_onboarding_file(id: int, new_file: OnboardingFileUpdate ,db: db_dependency):
    result = await db.execute(select(OnboardingFile).where(OnboardingFile.id == id))
    onboarding_file = result.scalars().one_or_none()
    if onboarding_file is None:
        raise HTTPException(status_code= status.HTTP_404_NOT_FOUND, detail="File not found")
    update_data = new_file.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(onboarding_file, field,value)
    await db.commit()
    await db.refresh(onboarding_file)
    return onboarding_file

#delete a file
@onboarding_files_router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file_by_id(id: int, db:db_dependency):
    result = await db.execute(select(OnboardingFile).where(OnboardingFile.id == id))
    onboarding_file = result.scalars().one_or_none()
    if onboarding_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail= "File not found")
    await db.delete(onboarding_file)
    await db.commit()