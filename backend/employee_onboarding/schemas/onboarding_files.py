from pydantic import BaseModel
from datetime import datetime

class OnboardingFilesBase(BaseModel):
    filename: str
    path: str

class OnboardingFileCreate(OnboardingFilesBase):
    pass

class OnboardingFileResponse(OnboardingFilesBase):
    id: int
    date_created: datetime

class OnboardingFileUpdate(BaseModel):
    filename: str| None = None
    path: str| None = None