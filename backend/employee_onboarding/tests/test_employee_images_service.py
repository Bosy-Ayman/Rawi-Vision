import pytest
import uuid
from employee_onboarding.service.employee_images import EmployeeImagesService

def test_get_employee_images_success(mocker):
    employee_id = uuid.uuid4()
    image_urls = ["url1", "url2"]
    mock_minio = mocker.Mock()
    mock_minio.get_object_urls.return_value = image_urls
    service = EmployeeImagesService(mock_minio)
    result = service.get_employee_images(employee_id)
    assert result == {"employee_id": employee_id, "image_urls": image_urls}
    mock_minio.get_object_urls.assert_called_once_with(bucket_name="employee-pictures", prefix=str(employee_id))

def test_get_employee_images_error(mocker):
    employee_id = uuid.uuid4()
    mock_minio = mocker.Mock()
    mock_minio.get_object_urls.side_effect = Exception("MinIO error")
    service = EmployeeImagesService(mock_minio)
    with pytest.raises(Exception):
        service.get_employee_images(employee_id)

def test_delete_employee_images_success(mocker):
    employee_id = uuid.uuid4()
    mock_minio = mocker.Mock()
    service = EmployeeImagesService(mock_minio)
    service.delete_employee_images(employee_id)
    mock_minio.remove_objects_from_bucket.assert_called_once_with(bucket_name="employee-pictures", object_name=str(employee_id))

def test_delete_employee_images_error(mocker):
    employee_id = uuid.uuid4()
    mock_minio = mocker.Mock()
    mock_minio.remove_objects_from_bucket.side_effect = Exception("delete error")
    service = EmployeeImagesService(mock_minio)
    with pytest.raises(Exception):
        service.delete_employee_images(employee_id)