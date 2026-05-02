import pytest
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from camera_onboarding.routers.camera import camera_router, get_camera_service
from camera_onboarding.schemas.camera import CameraCreate, CameraResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_camera_dict(**overrides):
    base = {
        "id": str(uuid4()),
        "room": "101",
        "building": "HQ",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "username": "admin",
    }
    base.update(overrides)
    return base


def build_app(mock_service):
    """Throwaway FastAPI app with get_camera_service overridden."""
    app = FastAPI()
    app.include_router(camera_router)
    app.dependency_overrides[get_camera_service] = lambda: mock_service
    return app


# ---------------------------------------------------------------------------
# GET /camera
# ---------------------------------------------------------------------------

class TestGetAllCameras:
    def test_returns_empty_list(self):
        svc = MagicMock()
        svc.get_all_cameras = AsyncMock(return_value=[])

        resp = TestClient(build_app(svc)).get("/camera")

        assert resp.status_code == 200
        assert resp.json() == []
        svc.get_all_cameras.assert_awaited_once()

    def test_propagates_service_exception(self):
        svc = MagicMock()
        svc.get_all_cameras = AsyncMock(side_effect=RuntimeError("DB down"))

        resp = TestClient(build_app(svc), raise_server_exceptions=False).get("/camera")

        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /camera
# ---------------------------------------------------------------------------

class TestCreateCamera:
    DEFAULT_FORM = {
        "room": "101",
        "building": "HQ",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "username": "admin",
        "password": "secret",
    }

    def test_missing_required_field_returns_422(self):
        svc = MagicMock()
        incomplete = {k: v for k, v in self.DEFAULT_FORM.items() if k != "mac_address"}

        resp = TestClient(build_app(svc)).post("/camera", data=incomplete)

        assert resp.status_code == 422

    def test_propagates_service_exception(self):
        svc = MagicMock()
        svc.create_camera_instance = AsyncMock(side_effect=ValueError("Duplicate MAC"))

        resp = TestClient(build_app(svc), raise_server_exceptions=False).post(
            "/camera", data=self.DEFAULT_FORM
        )

        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# DELETE /camera/{id}
# ---------------------------------------------------------------------------

class TestDeleteCamera:
    def test_deletes_existing_camera(self):
        camera_id = uuid4()
        svc = MagicMock()
        svc.delete_camera = AsyncMock(return_value=None)

        resp = TestClient(build_app(svc)).delete(f"/camera/{camera_id}")

        assert resp.status_code == 204
        svc.delete_camera.assert_awaited_once_with(id=camera_id)

    def test_returns_404_when_camera_not_found(self):
        camera_id = uuid4()
        svc = MagicMock()
        svc.delete_camera = AsyncMock(side_effect=Exception("not found"))

        resp = TestClient(build_app(svc)).delete(f"/camera/{camera_id}")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "camera not found"

    def test_invalid_uuid_returns_422(self):
        svc = MagicMock()

        resp = TestClient(build_app(svc)).delete("/camera/not-a-uuid")

        assert resp.status_code == 422
        svc.delete_camera.assert_not_called()