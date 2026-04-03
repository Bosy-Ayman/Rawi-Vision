from fastapi import FastAPI
from employee_onboarding.routers.employees import employee_router
from employee_onboarding.routers.employee_images import employee_image_router
from camera_onboarding.routers.camera import camera_router
from auth.routers.auth import auth_router
from camera_onboarding.routers.discovery import camera_discovery_router
from camera_ingestion.routers.ingestion import ingestion_router
from camera_ingestion.routers.stream import stream_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(employee_router)
app.include_router(employee_image_router)
app.include_router(auth_router)
app.include_router(camera_router)
app.include_router(camera_discovery_router)
app.include_router(ingestion_router)
app.include_router(stream_router)



