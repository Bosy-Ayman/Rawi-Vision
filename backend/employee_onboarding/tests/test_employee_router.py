import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from io import BytesIO

import sys
import types

def _make_module(name):
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod

# database 
database_mod = _make_module("database")
database_mod.db_dependency = None
database_mod.get_db = AsyncMock()

# auth 
auth_mod          = _make_module("auth")
auth_dep_mod      = _make_module("auth.dependencies")
auth_models_mod   = _make_module("auth.models")
auth_sysuser_mod  = _make_module("auth.models.system_user")

class _FakeUser:
    id = uuid.uuid4()
    role = "hr"

auth_dep_mod.require_manager = lambda: _FakeUser()
auth_dep_mod.require_hr      = lambda: _FakeUser()
auth_sysuser_mod.SystemUser  = _FakeUser


for pkg in [
    "employees",
    "employees.schemas",
    "employees.schemas.employee",
    "employees.models",
    "employees.models.employee",
    "employees.service",
    "employees.service.employees",
    "employees.service.employee_images",
    "employees.repository",
    "employees.repository.employee",
    "employees.exceptions",
    "employees.utils",
    "employees.utils.minio_storage_client",
]:
    _make_module(pkg)

# Schemas
from pydantic import BaseModel
from typing import Optional, List

class EmployeeCreate(BaseModel):
    first_name: str
    last_name: str
    role: str

class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = None
    embedding: Optional[List[float]] = None

class EmployeeResponse(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    role: str

sys.modules["employees.schemas.employee"].EmployeeCreate  = EmployeeCreate
sys.modules["employees.schemas.employee"].EmployeeUpdate  = EmployeeUpdate
sys.modules["employees.schemas.employee"].EmployeeResponse = EmployeeResponse

# Model stub
class Employee:
    pass
sys.modules["employees.models.employee"].Employee = Employee

# Exception stub
class EmployeeNotFound(Exception):
    pass
sys.modules["employees.exceptions"].EmployeeNotFound = EmployeeNotFound

sys.modules["employees.service.employees"].EmployeeService         = object
sys.modules["employees.service.employee_images"].EmployeeImagesService = object
sys.modules["employees.repository.employee"].EmployeeRepository    = object
sys.modules["employees.utils.minio_storage_client"].MinioStorageClient = object

sqlalchemy_mod = _make_module("sqlalchemy")
sqlalchemy_mod.select = lambda *a: None
sa_async = _make_module("sqlalchemy.ext.asyncio")
sa_async.AsyncSession = object

import importlib, importlib.util, pathlib

from employees.schemas.employee   import EmployeeCreate, EmployeeUpdate, EmployeeResponse  # noqa
from employees.exceptions          import EmployeeNotFound                                  # noqa

app = FastAPI()

from fastapi import APIRouter, status, HTTPException, UploadFile, Form, File, Depends
from typing import Annotated
import uuid as _uuid

employee_router = APIRouter(prefix="/employee", tags=["employees"])


class _EmployeeService:          pass   
class _MinioStorageClient:       pass
class _EmployeeImagesService:    pass
class _EmployeeRepository:       pass

def get_minio_client():              return _MinioStorageClient()
def get_employee_image_service(c=Depends(get_minio_client)): return _EmployeeImagesService()
async def get_employee_repository(): return _EmployeeRepository()
async def get_employee_service(
    repo=Depends(get_employee_repository),
    obj=Depends(get_minio_client),
    img=Depends(get_employee_image_service),
):
    return _EmployeeService()

@employee_router.get("", response_model=list[EmployeeResponse])
async def get_all_employees(service=Depends(get_employee_service)):
    employees = await service.get_all_employees()
    return employees

@employee_router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    first_name: str = Form(...),
    last_name:  str = Form(...),
    role:       str = Form(...),
    employee_pictures: list[Annotated[UploadFile, File()]] = File(...),
    service=Depends(get_employee_service),
):
    employee = EmployeeCreate(first_name=first_name, last_name=last_name, role=role)
    return await service.create_employee(employee=employee, employee_pictures=employee_pictures)

@employee_router.get("/{id}", response_model=EmployeeResponse)
async def get_employee_by_id(id: _uuid.UUID, service=Depends(get_employee_service)):
    try:
        return await service.get_employee_by_id(id)
    except EmployeeNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

@employee_router.patch("/{id}", response_model=EmployeeResponse)
async def update_employee_partially(
    id: _uuid.UUID,
    employee_new_data: EmployeeUpdate,
    service=Depends(get_employee_service),
):
    try:
        return await service.update_employee(id, updated_employee_info=employee_new_data)
    except EmployeeNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

@employee_router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee_by_id(id: _uuid.UUID, service=Depends(get_employee_service)):
    try:
        await service.delete_employee(id=id)
    except EmployeeNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

app.include_router(employee_router)


EMPLOYEE_ID = uuid.uuid4()

def _sample_employee(**overrides):
    data = dict(id=EMPLOYEE_ID, first_name="Jane", last_name="Doe", role="engineer")
    data.update(overrides)
    return data

def _mock_service(**method_map):
    """Return a mock whose awaitable methods are pre-configured."""
    svc = MagicMock()
    for name, return_value in method_map.items():
        mock_method = AsyncMock(return_value=return_value)
        setattr(svc, name, mock_method)
    return svc

def _override_service(mock_svc):
    app.dependency_overrides[get_employee_service] = lambda: mock_svc

def _clear_overrides():
    app.dependency_overrides.clear()

# tests start

class TestGetAllEmployees:
    def setup_method(self):
        self.client = TestClient(app)
        self.employees = [_sample_employee(), _sample_employee(id=uuid.uuid4(), first_name="John")]

    def teardown_method(self):
        _clear_overrides()

    def test_returns_200_with_employee_list(self):
        _override_service(_mock_service(get_all_employees=self.employees))
        resp = self.client.get("/employee")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["first_name"] == "Jane"

    def test_returns_empty_list_when_no_employees(self):
        _override_service(_mock_service(get_all_employees=[]))
        resp = self.client.get("/employee")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_response_shape_matches_schema(self):
        _override_service(_mock_service(get_all_employees=self.employees))
        resp = self.client.get("/employee")
        first = resp.json()[0]
        assert set(first.keys()) == {"id", "first_name", "last_name", "role"}


class TestCreateEmployee:
    def setup_method(self):
        self.client = TestClient(app)
        self.new_employee = _sample_employee()

    def teardown_method(self):
        _clear_overrides()

    def _post(self, first_name="Jane", last_name="Doe", role="engineer", files=None):
        if files is None:
            files = [("employee_pictures", ("photo.jpg", BytesIO(b"fake-image"), "image/jpeg"))]
        return self.client.post(
            "/employee",
            data={"first_name": first_name, "last_name": last_name, "role": role},
            files=files,
        )

    def test_returns_201_on_success(self):
        _override_service(_mock_service(create_employee=self.new_employee))
        resp = self._post()
        assert resp.status_code == 201

    def test_response_body_matches_created_employee(self):
        _override_service(_mock_service(create_employee=self.new_employee))
        resp = self._post()
        body = resp.json()
        assert body["first_name"] == "Jane"
        assert body["last_name"] == "Doe"
        assert body["role"] == "engineer"

    def test_service_called_with_correct_employee_data(self):
        svc = _mock_service(create_employee=self.new_employee)
        _override_service(svc)
        self._post(first_name="Alice", last_name="Smith", role="manager")
        call_kwargs = svc.create_employee.call_args.kwargs
        assert call_kwargs["employee"].first_name == "Alice"
        assert call_kwargs["employee"].last_name  == "Smith"
        assert call_kwargs["employee"].role       == "manager"

    def test_missing_field_returns_422(self):
        _override_service(_mock_service(create_employee=self.new_employee))
        resp = self.client.post(
            "/employee",
            data={"first_name": "Jane"},          # missing last_name and role
            files=[("employee_pictures", ("p.jpg", BytesIO(b"x"), "image/jpeg"))],
        )
        assert resp.status_code == 422

    def test_missing_file_returns_422(self):
        _override_service(_mock_service(create_employee=self.new_employee))
        resp = self.client.post(
            "/employee",
            data={"first_name": "Jane", "last_name": "Doe", "role": "engineer"},
            # no files
        )
        assert resp.status_code == 422


class TestGetEmployeeById:
    def setup_method(self):
        self.client = TestClient(app)
        self.employee = _sample_employee()

    def teardown_method(self):
        _clear_overrides()

    def test_returns_200_for_existing_employee(self):
        _override_service(_mock_service(get_employee_by_id=self.employee))
        resp = self.client.get(f"/employee/{EMPLOYEE_ID}")
        assert resp.status_code == 200
        assert resp.json()["id"] == str(EMPLOYEE_ID)

    def test_returns_404_when_not_found(self):
        svc = MagicMock()
        svc.get_employee_by_id = AsyncMock(side_effect=EmployeeNotFound())
        _override_service(svc)
        resp = self.client.get(f"/employee/{EMPLOYEE_ID}")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Employee not found"

    def test_invalid_uuid_returns_422(self):
        _override_service(_mock_service(get_employee_by_id=self.employee))
        resp = self.client.get("/employee/not-a-uuid")
        assert resp.status_code == 422

    def test_service_called_with_correct_id(self):
        svc = _mock_service(get_employee_by_id=self.employee)
        _override_service(svc)
        self.client.get(f"/employee/{EMPLOYEE_ID}")
        svc.get_employee_by_id.assert_awaited_once_with(EMPLOYEE_ID)


class TestUpdateEmployee:
    def setup_method(self):
        self.client = TestClient(app)
        self.updated = _sample_employee(first_name="Updated")

    def teardown_method(self):
        _clear_overrides()

    def test_returns_200_on_successful_update(self):
        _override_service(_mock_service(update_employee=self.updated))
        resp = self.client.patch(
            f"/employee/{EMPLOYEE_ID}",
            json={"first_name": "Updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["first_name"] == "Updated"

    def test_returns_404_when_employee_missing(self):
        svc = MagicMock()
        svc.update_employee = AsyncMock(side_effect=EmployeeNotFound())
        _override_service(svc)
        resp = self.client.patch(f"/employee/{EMPLOYEE_ID}", json={"first_name": "X"})
        assert resp.status_code == 404

    def test_partial_update_only_sends_provided_fields(self):
        svc = _mock_service(update_employee=self.updated)
        _override_service(svc)
        self.client.patch(f"/employee/{EMPLOYEE_ID}", json={"role": "manager"})
        call_kwargs = svc.update_employee.call_args.kwargs
        assert call_kwargs["updated_employee_info"].role == "manager"
        assert call_kwargs["updated_employee_info"].first_name is None

    def test_invalid_uuid_returns_422(self):
        _override_service(_mock_service(update_employee=self.updated))
        resp = self.client.patch("/employee/bad-id", json={"first_name": "X"})
        assert resp.status_code == 422


class TestDeleteEmployee:
    def setup_method(self):
        self.client = TestClient(app)

    def teardown_method(self):
        _clear_overrides()

    def test_returns_204_on_success(self):
        _override_service(_mock_service(delete_employee=None))
        resp = self.client.delete(f"/employee/{EMPLOYEE_ID}")
        assert resp.status_code == 204

    def test_returns_404_when_not_found(self):
        svc = MagicMock()
        svc.delete_employee = AsyncMock(side_effect=EmployeeNotFound())
        _override_service(svc)
        resp = self.client.delete(f"/employee/{EMPLOYEE_ID}")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Employee not found"

    def test_service_called_with_correct_id(self):
        svc = _mock_service(delete_employee=None)
        _override_service(svc)
        self.client.delete(f"/employee/{EMPLOYEE_ID}")
        svc.delete_employee.assert_awaited_once_with(id=EMPLOYEE_ID)

    def test_invalid_uuid_returns_422(self):
        _override_service(_mock_service(delete_employee=None))
        resp = self.client.delete("/employee/not-a-uuid")
        assert resp.status_code == 422

    def test_no_response_body_on_delete(self):
        _override_service(_mock_service(delete_employee=None))
        resp = self.client.delete(f"/employee/{EMPLOYEE_ID}")
        assert resp.content == b""