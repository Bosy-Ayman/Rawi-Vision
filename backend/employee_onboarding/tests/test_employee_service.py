import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import UploadFile
from employee_onboarding.service.employees import EmployeeService
import uuid
from unittest.mock import MagicMock
from employee_onboarding.exceptions import EmployeeNotFound


@pytest.mark.asyncio
async def test_create_employee_success(mocker):
    mock_repo = AsyncMock()
    mock_repo.db = AsyncMock()
    fake_employee = MagicMock()
    fake_employee.id = 1
    mock_repo.create_employee.return_value = fake_employee
    mock_storage = AsyncMock()
    mock_image_service = AsyncMock()
    mock_delay = mocker.patch("employee_onboarding.celery_tasks.embedding.create_embedding_task.delay")
    service = EmployeeService(repository=mock_repo,object_storage=mock_storage,employee_image_service=mock_image_service)
    fake_file = MagicMock(spec=UploadFile)
    fake_file.filename = "photo.jpg"
    employee_data = MagicMock()
    result = await service.create_employee(employee_data,[fake_file])
    assert result == fake_employee
    mock_repo.create_employee.assert_called_once()
    mock_storage.add_object_to_bucket.assert_called_once()
    mock_repo.db.commit.assert_called_once()
    mock_repo.db.refresh.assert_called_once_with(fake_employee)
    mock_delay.assert_called_once_with("employee-pictures", 1)

# image upload fails case
@pytest.mark.asyncio
async def test_create_employee_upload_failure(mocker):
    mock_repo = AsyncMock()
    mock_repo.db = AsyncMock()
    fake_employee = MagicMock()
    fake_employee.id = 1
    mock_repo.create_employee.return_value = fake_employee
    mock_storage = AsyncMock()
    mock_storage.add_object_to_bucket.side_effect = Exception("Upload failed")
    mock_image_service = AsyncMock()
    service = EmployeeService(repository=mock_repo,object_storage=mock_storage,employee_image_service=mock_image_service)
    fake_file = MagicMock(spec=UploadFile)
    fake_file.filename = "photo.jpg"
    with pytest.raises(Exception):
        await service.create_employee(MagicMock(),[fake_file])
    mock_repo.db.rollback.assert_called_once()
    mock_storage.remove_objects_from_bucket.assert_called_once_with(bucket_name="employee-pictures",object_name="1")


@pytest.mark.asyncio
async def test_get_all_employees_success(mocker):
    mock_repo = AsyncMock()
    mock_repo.read_all_employees.return_value = ["emp1", "emp2"]
    service = EmployeeService(repository=mock_repo,object_storage=mocker.Mock(),employee_image_service=mocker.Mock())
    result = await service.get_all_employees()
    assert result == ["emp1", "emp2"]
    mock_repo.read_all_employees.assert_called_once()

@pytest.mark.asyncio
async def test_get_employee_by_id_success(mocker):
    employee_id = uuid.uuid4()
    fake_employee = MagicMock()
    fake_employee.id = employee_id
    fake_employee.date_created = "2024"
    fake_employee.first_name = "Shahd"
    fake_employee.last_name = "Hossam"
    fake_employee.role = "Fouda"
    fake_employee.embedding = None
    fake_employee.embedding_status = "processing"
    mock_repo = AsyncMock()
    mock_repo.read_employee_by_id.return_value = fake_employee
    mock_image_service = mocker.Mock()
    mock_image_service.get_employee_images.return_value = {"image_urls": ["url1", "url2"]}
    service = EmployeeService(repository=mock_repo,object_storage=mocker.Mock(),employee_image_service=mock_image_service)
    result = await service.get_employee_by_id(employee_id)
    assert result.id == employee_id
    assert result.images == ["url1", "url2"]
    mock_repo.read_employee_by_id.assert_called_once_with(employee_id)

@pytest.mark.asyncio
async def test_get_employee_by_id_not_found(mocker):
    employee_id = uuid.uuid4()
    mock_repo = AsyncMock()
    mock_repo.read_employee_by_id.return_value = None
    service = EmployeeService(repository=mock_repo,object_storage=mocker.Mock(),employee_image_service=mocker.Mock())
    with pytest.raises(EmployeeNotFound):
        await service.get_employee_by_id(employee_id)

@pytest.mark.asyncio
async def test_delete_employee_success(mocker):
    employee_id = uuid.uuid4()
    fake_employee = MagicMock()
    fake_employee.id = employee_id
    mock_repo = AsyncMock()
    mock_repo.db = AsyncMock()
    mock_repo.read_employee_by_id.return_value = fake_employee
    mock_image_service = mocker.Mock()
    service = EmployeeService(repository=mock_repo,object_storage=mocker.Mock(),employee_image_service=mock_image_service)
    await service.delete_employee(employee_id)
    mock_repo.delete_employee.assert_called_once_with(employee=fake_employee)
    mock_image_service.delete_employee_images.assert_called_once_with(employee_id=employee_id)
    mock_repo.db.commit.assert_called_once()

@pytest.mark.asyncio
async def test_update_employee_success(mocker):
    employee_id = uuid.uuid4()
    fake_employee = MagicMock()
    fake_employee.first_name = "Old"
    update_data = mocker.Mock()
    update_data.model_dump.return_value = {"first_name": "New"}
    mock_repo = AsyncMock()
    mock_repo.db = AsyncMock()
    mock_repo.read_employee_by_id.return_value = fake_employee
    service = EmployeeService(repository=mock_repo,object_storage=mocker.Mock(),employee_image_service=mocker.Mock())
    result = await service.update_employee(employee_id, update_data)
    assert fake_employee.first_name == "New"
    mock_repo.db.commit.assert_called_once()
    mock_repo.db.refresh.assert_called_once_with(fake_employee)