# PostgreSQL Database Schema - Rawi Vision

Complete PostgreSQL database structure for the Rawi Vision surveillance and monitoring system.

## Overview
- **Total Tables:** 10
- **Total Columns:** 80+
- **Database Type:** PostgreSQL with pgvector extension
- **ORM Framework:** SQLAlchemy 2.0+

---

## Table of Contents
1. [employees](#1-employees-table)
2. [cameras](#2-cameras-table)
3. [camera_metadata](#3-camera_metadata-table)
4. [attendance](#4-attendance-table)
5. [anomalies](#5-anomalies-table)
6. [indexed_videos](#6-indexed_videos-table)
7. [video_frames](#7-video_frames-table)
8. [video_summaries](#8-video_summaries-table)
9. [system_users](#9-system_users-table)
10. [license_info](#10-license_info-table)

---

## 1. employees Table
**Purpose:** Store employee information with facial embeddings for identification

```sql
CREATE TABLE employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name VARCHAR NOT NULL,
    last_name VARCHAR NOT NULL,
    role VARCHAR NOT NULL,
    embedding vector(512),                    -- 512-dimensional face embedding (pgvector)
    embedding_status VARCHAR NOT NULL,         -- Status of face embedding generation
    profile_image_url VARCHAR,
    assigned_camera_ids VARCHAR[],             -- Array of camera IDs for boundary checking
    assigned_days INTEGER[],                   -- Array of 0-6 (Mon-Sun) for shift days
    assigned_shift_start VARCHAR,              -- HH:MM format
    assigned_shift_end VARCHAR,                -- HH:MM format
    date_created TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Fields:
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique employee identifier |
| first_name | VARCHAR | Employee first name |
| last_name | VARCHAR | Employee last name |
| role | VARCHAR | Job role/position |
| embedding | Vector(512) | Facial embedding for recognition (pgvector) |
| embedding_status | VARCHAR | Status: pending, completed, failed |
| profile_image_url | VARCHAR | URL to employee profile image |
| assigned_camera_ids | VARCHAR[] | Cameras employee is authorized for |
| assigned_days | INTEGER[] | Work days (0=Monday, 6=Sunday) |
| assigned_shift_start | VARCHAR | Shift start time (HH:MM) |
| assigned_shift_end | VARCHAR | Shift end time (HH:MM) |
| date_created | TIMESTAMP | Record creation time (TZ-aware) |

---

## 2. cameras Table
**Purpose:** Store camera device information

```sql
CREATE TABLE cameras (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room VARCHAR NOT NULL,
    building VARCHAR NOT NULL,
    mac_address VARCHAR NOT NULL,
    username VARCHAR NOT NULL,
    password VARCHAR NOT NULL,
    date_created TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Fields:
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique camera identifier |
| room | VARCHAR | Room/location name |
| building | VARCHAR | Building name |
| mac_address | VARCHAR | Camera MAC address |
| username | VARCHAR | Camera login username |
| password | VARCHAR | Camera login password |
| date_created | TIMESTAMP | Record creation time (TZ-aware) |

---

## 3. camera_metadata Table
**Purpose:** Extended metadata for cameras (RTSP URLs, network info)

```sql
CREATE TABLE camera_metadata (
    mac_address VARCHAR PRIMARY KEY,
    room VARCHAR NOT NULL,
    building VARCHAR NOT NULL,
    ip_address VARCHAR NOT NULL,
    rtsp_urls JSON NOT NULL,                   -- Array of RTSP stream URLs
    username VARCHAR NOT NULL,
    password VARCHAR NOT NULL,
    date_created TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Fields:
| Field | Type | Description |
|-------|------|-------------|
| mac_address | VARCHAR | Camera MAC address (PK) |
| room | VARCHAR | Room/location name |
| building | VARCHAR | Building name |
| ip_address | VARCHAR | Camera IP address |
| rtsp_urls | JSON | Array of RTSP stream URLs |
| username | VARCHAR | Camera login username |
| password | VARCHAR | Camera login password |
| date_created | TIMESTAMP | Record creation time (TZ-aware) |

---

## 4. attendance Table
**Purpose:** Track employee presence and duration at work

```sql
CREATE TABLE attendance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL,                 -- Foreign key to employees.id
    camera_id VARCHAR,
    day DATE NOT NULL DEFAULT CURRENT_DATE,
    date_created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    look_count INTEGER DEFAULT 1,              -- Number of sessions/visits on this day
    duration_seconds FLOAT DEFAULT 0.0,        -- Total time on-site (seconds)
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW() ON UPDATE NOW()
);
```

### Fields:
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique attendance record ID |
| employee_id | UUID | Reference to employees.id |
| camera_id | VARCHAR | Camera where attendance was recorded |
| day | DATE | Date of attendance (YYYY-MM-DD) |
| date_created | TIMESTAMP | Record creation time (TZ-aware) |
| look_count | INTEGER | Number of check-ins/sessions |
| duration_seconds | FLOAT | Total duration in seconds (20-min grace period merged) |
| last_seen | TIMESTAMP | Last detection time (TZ-aware) |

**Note:** Duration calculation merges intervals with a 20-minute grace period to handle gaps.

---

## 5. anomalies Table
**Purpose:** Store detected security anomalies and incidents

```sql
CREATE TABLE anomalies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    anomaly_type VARCHAR NOT NULL DEFAULT 'unknown',  -- ENUM: violence, theft, vandalism, 
                                                       -- unusual_behavior, out_of_bounds, unknown
    description TEXT NOT NULL,
    confidence_score FLOAT NOT NULL DEFAULT 0.0,      -- 0-1 confidence level
    camera_id VARCHAR NOT NULL DEFAULT 'default',
    image_url VARCHAR,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    employee_id VARCHAR                               -- Filled by face recognition module
);
```

### Fields:
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER | Auto-increment anomaly ID |
| anomaly_type | ENUM | Type: violence, theft, vandalism, unusual_behavior, out_of_bounds, unknown |
| description | TEXT | Detailed description of the anomaly |
| confidence_score | FLOAT | AI confidence (0.0-1.0) |
| camera_id | VARCHAR | Camera ID where anomaly was detected |
| image_url | VARCHAR | URL to captured image/frame |
| detected_at | TIMESTAMP | Detection timestamp (TZ-aware) |
| employee_id | VARCHAR | Employee ID (if face recognized) |

---

## 6. indexed_videos Table
**Purpose:** Track video files stored in MinIO and their processing status

```sql
CREATE TABLE indexed_videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id UUID NOT NULL,                   -- Foreign key to cameras.id
    storage_path VARCHAR NOT NULL,             -- MinIO object key (e.g., camera-archive-videos/uuid.mp4)
    filename VARCHAR NOT NULL,                 -- Original filename
    status VARCHAR NOT NULL DEFAULT 'pending', -- pending, indexing, completed, failed
    sampling_rate INTEGER NOT NULL DEFAULT 16, -- Frames per second for indexing
    date_created TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Fields:
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique video ID |
| camera_id | UUID | Reference to cameras.id |
| storage_path | VARCHAR | MinIO path (camera-archive-videos/...) |
| filename | VARCHAR | Original video filename |
| status | VARCHAR | Processing status: pending, indexing, completed, failed |
| sampling_rate | INTEGER | FPS sampling rate for frame extraction |
| date_created | TIMESTAMP | Record creation time (TZ-aware) |

---

## 7. video_frames Table
**Purpose:** Store extracted frames with embeddings for semantic search

```sql
CREATE TABLE video_frames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id UUID NOT NULL,                    -- Foreign key to indexed_videos.id
    frame_number INTEGER NOT NULL,
    timestamp_offset FLOAT NOT NULL,           -- Offset in seconds from start
    description VARCHAR NOT NULL,              -- Fused AI description
    tracks VARCHAR,                            -- Comma-separated track IDs
    embedding vector(1152) NOT NULL,           -- 1152-dimensional embedding (pgvector)
    face_detections VARCHAR                    -- JSON: [{"emp_id", "name", "confidence", "x1", "y1", "x2", "y2"}]
);
```

### Fields:
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER | Auto-increment frame ID |
| video_id | UUID | Reference to indexed_videos.id |
| frame_number | INTEGER | Frame sequence number |
| timestamp_offset | FLOAT | Seconds from video start |
| description | VARCHAR | Fused description from AI |
| tracks | VARCHAR | Comma-separated object track IDs |
| embedding | Vector(1152) | Semantic embedding (pgvector) for search |
| face_detections | VARCHAR | JSON array of detected faces |

**Note:** 1152-dimensional embeddings enable similarity search via pgvector.

---

## 8. video_summaries Table
**Purpose:** Store AI-generated video summaries

```sql
CREATE TABLE video_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id VARCHAR NOT NULL,                 -- Reference to indexed_videos.id
    camera_id VARCHAR NOT NULL,
    summary_storage_path VARCHAR,              -- MinIO path to summary video
    status VARCHAR NOT NULL DEFAULT 'pending', -- pending, completed, failed
    generation_type VARCHAR NOT NULL DEFAULT 'manual', -- auto, manual
    date_created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    date_completed TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_video_summaries_video_id ON video_summaries(video_id);
CREATE INDEX idx_video_summaries_camera_id ON video_summaries(camera_id);
```

### Fields:
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique summary ID |
| video_id | VARCHAR | Reference to video ID |
| camera_id | VARCHAR | Camera ID (indexed) |
| summary_storage_path | VARCHAR | MinIO path to summary video |
| status | VARCHAR | Processing status: pending, completed, failed |
| generation_type | VARCHAR | auto or manual generation |
| date_created | TIMESTAMP | Creation timestamp (TZ-aware) |
| date_completed | TIMESTAMP | Completion timestamp (TZ-aware) |

---

## 9. system_users Table
**Purpose:** Store admin/manager user accounts with OAuth integration

```sql
CREATE TABLE system_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR NOT NULL UNIQUE,
    full_name VARCHAR NOT NULL,
    role VARCHAR NOT NULL,                     -- ENUM: HR, Manager
    google_id VARCHAR,                         -- Google OAuth ID
    date_created TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_system_users_email ON system_users(email);
```

### Fields:
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique user ID |
| email | VARCHAR | User email (unique, indexed) |
| full_name | VARCHAR | User full name |
| role | VARCHAR | Role: HR, Manager |
| google_id | VARCHAR | Google OAuth identifier |
| date_created | TIMESTAMP | Account creation time (TZ-aware) |

---

## 10. license_info Table
**Purpose:** Store subscription and licensing information

```sql
CREATE TABLE license_info (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    installation_uuid VARCHAR NOT NULL UNIQUE,
    status VARCHAR NOT NULL DEFAULT 'trial',   -- active, suspended, expired, canceled
    tier VARCHAR NOT NULL DEFAULT '0',         -- "0"=Attendance, "1"=Search, "2"=Summarization
    last_checked TIMESTAMP WITH TIME ZONE DEFAULT NOW() ON UPDATE NOW()
);

CREATE INDEX idx_license_info_installation_uuid ON license_info(installation_uuid);
```

### Fields:
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique license record ID |
| installation_uuid | VARCHAR | Installation identifier (unique, indexed) |
| status | VARCHAR | License status: active, suspended, expired, canceled |
| tier | VARCHAR | Feature tier: "0" (Attendance), "1" (Search), "2" (Summarization) |
| last_checked | TIMESTAMP | Last license check time (TZ-aware) |

---

## Database Features

### Vector Search (pgvector)
- **Employee embeddings:** 512 dimensions for face recognition
- **Video frame embeddings:** 1152 dimensions for semantic search
- Enables similarity search: `SELECT * FROM video_frames WHERE embedding <-> query_embedding < 0.5 LIMIT 10`

### ENUM Types
```sql
-- Anomaly types
CREATE TYPE anomalytype AS ENUM (
    'violence', 'theft', 'vandalism', 'unusual_behavior', 'out_of_bounds', 'unknown'
);

-- System roles
CREATE TYPE systemrole AS ENUM ('HR', 'Manager');
```

### Array Types
- `assigned_camera_ids VARCHAR[]` - Multiple cameras per employee
- `assigned_days INTEGER[]` - Weekdays (0=Mon, 6=Sun)
- `rtsp_urls JSON` - Multiple stream URLs

### Indexing Strategy
- **Unique indexes:** email, installation_uuid, mac_address
- **Search indexes:** video_id, camera_id (in video_summaries)
- **Foreign key relationships:** camera_id, video_id, employee_id

### Timezone Handling
All `TIMESTAMP` columns use `TIMESTAMP WITH TIME ZONE` for UTC storage and proper timezone conversion.

---

## Relationships Diagram

```
employees
├── attendance (employee_id → id)
├── camera_metadata (assigned_camera_ids → cameras)
└── anomalies (employee_id → id)

cameras
├── camera_metadata (id → mac_address)
└── indexed_videos (id → camera_id)

indexed_videos
└── video_frames (id → video_id)
    └── video_summaries (video_id → id)

system_users
└── (authentication/authorization)

license_info
└── (subscription tracking)
```

---

## Query Examples

### Get employee attendance for today
```sql
SELECT e.first_name, e.last_name, a.camera_id, a.duration_seconds, a.look_count
FROM employees e
JOIN attendance a ON e.id = a.employee_id
WHERE a.day = CURRENT_DATE
ORDER BY a.last_seen DESC;
```

### Find similar video frames
```sql
SELECT id, timestamp_offset, description, (embedding <-> query_embedding) AS distance
FROM video_frames
WHERE video_id = 'video-uuid'
ORDER BY embedding <-> query_embedding
LIMIT 10;
```

### Get anomalies by type with confidence
```sql
SELECT id, anomaly_type, description, confidence_score, detected_at, camera_id
FROM anomalies
WHERE anomaly_type = 'violence' AND confidence_score > 0.8
ORDER BY detected_at DESC
LIMIT 50;
```

### Check license status
```sql
SELECT installation_uuid, status, tier, last_checked
FROM license_info
WHERE installation_uuid = 'install-uuid'
AND status = 'active';
```

---

## Migration Management

Migrations are managed using **Alembic** (`backend/alembic/`):
```bash
# Create new migration
alembic revision --autogenerate -m "Add new column"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## Performance Considerations

1. **pgvector Indexing:** Consider IVFFlat index for large embeddings:
   ```sql
   CREATE INDEX ON video_frames USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
   ```

2. **Partitioning:** Consider partitioning large tables by date:
   ```sql
   CREATE TABLE attendance_2024_06 PARTITION OF attendance
   FOR VALUES FROM ('2024-06-01') TO ('2024-07-01');
   ```

3. **Connection Pooling:** Use asyncpg with connection pooling for optimal performance

4. **Batch Inserts:** Use bulk insert operations for frame data

---

## Version History
- **v1.0** - Initial schema (10 tables, pgvector support)
- Date: 2026-06-15

---

## Dependencies
- PostgreSQL 13+ with pgvector extension
- SQLAlchemy 2.0+
- asyncpg for async database operations
- Alembic for migrations
