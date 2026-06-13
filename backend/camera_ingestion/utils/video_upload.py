import aiofiles
class VideoUploadFile:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.content_type = "video/mp4"
        self._f = None

    async def read(self) -> bytes:
        async with aiofiles.open(self.file_path, "rb") as f:
            return await f.read()
