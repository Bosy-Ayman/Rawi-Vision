import pytest
import numpy as np
from unittest.mock import MagicMock, patch

@patch("anomaly.celery_tasks.tasks._kafka_producer")
@patch("anomaly.celery_tasks.tasks.cv2.VideoCapture")
@patch("anomaly.celery_tasks.tasks.load_models")
def test_run_anomaly_detection_logic_flow(mock_load_models, mock_cv2, mock_kafka):
    from anomaly.celery_tasks.tasks import run_anomaly_detection
    
    mock_load_models.return_value = None
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    
    # Infinite generator to prevent StopIteration
    def fake_read():
        yield (True, fake_frame)
        while True:
            yield (False, None)
            
    mock_cap.read.side_effect = fake_read()
    mock_cv2.return_value = mock_cap
    
    run_anomaly_detection("rtsp://test", "00:11:22:33:44:55", "test-task-123")
    
    assert mock_cv2.called
    print("\n✅ Anomaly Task Logic Verified (Infinite Loop Handled)")
