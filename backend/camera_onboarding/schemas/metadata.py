from pydantic import BaseModel

class CameraMetadataBase(BaseModel):
    room: str | None = None
    building: str | None = None
    username: str | None = None
    password: str | None = None
    rtsp_urls: list[str]
    ip_address: str
    mac_address: str

class CameraMetadataCreate(CameraMetadataBase):
    pass

class CameraMetadataResponse(CameraMetadataBase):
    pass