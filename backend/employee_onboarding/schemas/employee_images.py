from pydantic import BaseModel
import uuid

class EmployeeImages(BaseModel):
    employee_id: uuid.UUID
    image_urls: list[str]

class EmployeeImagesResponse(EmployeeImages):
    pass