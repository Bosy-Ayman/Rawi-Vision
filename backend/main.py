from fastapi import FastAPI
from employee_onboarding.routers.employees import employee_router

app = FastAPI()
app.include_router(employee_router)

