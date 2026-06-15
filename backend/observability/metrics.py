from prometheus_client import Counter, Histogram, Gauge

# --- Auth Metrics ---
AUTH_LOGIN_COUNTER = Counter(
    "rawi_auth_login_total", 
    "Total login attempts", 
    ["status"] # success or failure
)

# --- Anomaly Metrics ---
ANOMALY_DETECTED_COUNTER = Counter(
    "rawi_anomaly_detected_total", 
    "Total anomalies detected", 
    ["camera_id", "type"]
)

ANOMALY_WEBSOCKET_CLIENTS = Gauge(
    "rawi_anomaly_websocket_clients",
    "Current active websocket clients listening for anomalies"
)

# --- Search Metrics ---
SEARCH_QUERY_LATENCY = Histogram(
    "rawi_search_query_latency_seconds", 
    "Latency of semantic search queries"
)

SEARCH_VIDEOS_INDEXED = Counter(
    "rawi_search_videos_indexed_total",
    "Total videos successfully indexed for semantic search"
)

# --- Summarization Metrics ---
SUMMARIZATION_TASK_STATUS = Counter(
    "rawi_summarization_tasks_total",
    "Video summarization task completion status",
    ["status"] # completed, failed
)

# --- Subscription Metrics ---
SUBSCRIPTION_WEBHOOK_RECEIVED = Counter(
    "rawi_subscription_webhook_total",
    "Total Paymob subscription webhooks received",
    ["status"]
)

# --- Camera Ingestion Metrics ---
CAMERA_STREAM_RECONNECTS = Counter(
    "rawi_camera_stream_reconnects_total",
    "Total RTSP stream reconnections",
    ["camera_id"]
)

CAMERA_ACTIVE_STREAMS = Gauge(
    "rawi_camera_active_streams",
    "Current number of actively ingesting camera streams"
)

# --- Attendance Metrics ---
ATTENDANCE_RECORDS_CREATED = Counter(
    "rawi_attendance_records_created_total",
    "Total attendance records created via RabbitMQ"
)

# --- Employee Onboarding Metrics ---
EMPLOYEE_ONBOARDING_TOTAL = Counter(
    "rawi_employee_onboarding_total",
    "Total employees successfully onboarded"
)
