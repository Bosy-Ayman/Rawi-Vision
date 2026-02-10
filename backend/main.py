from fastapi import FastAPI
from employee_onboarding.routers.employees import employee_router
from employee_onboarding.routers.onboarding_files import onboarding_files_router

app = FastAPI()
app.include_router(employee_router)
app.include_router(onboarding_files_router)

