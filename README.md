# Rawi Vision Platform

> **Graduation Project** | **Supervisor:** Dr. Doaa Shawky

## 🎯 Abstract

Video surveillance systems capture massive amounts of footage daily, making manual review inefficient. **Rawi Vision** is a comprehensive **Real-time Video Analysis Platform** designed to automate the extraction of meaningful insights from surveillance feeds.

By integrating **Face Recognition**, **Video Summarization**, and **Anomaly Detection**, the platform enhances situational awareness, tracks employee attendance/productivity, and detects suspicious behavior automatically. The system features a unified dashboard for real-time alerts and analytical visualization.

---

## ✨ Key Features

### 🔍 Real-time Face Recognition & Tracking
- Automated employee attendance tracking
- Identification of unauthorized personnel (stranger detection)
- Robust tracking across multiple cameras using Re-ID (ReID)
- 512-dimensional facial embeddings stored in pgvector

### 🎬 Adaptive Video Summarization
- Compresses lengthy video streams by removing redundant/idle segments
- Highlights key events based on motion and importance scores
- Generates highlight reels from surveillance footage
- MinIO-based distributed storage for summaries

### 🚨 Suspicious Behavior Detection
- Real-time anomaly detection using YOLOv8
- Detects: violence, theft, vandalism, unusual behavior, boundary violations
- Confidence scoring with instant alerts
- Automated alert notifications

### 📊 Interactive Dashboard
- Live monitoring interface with real-time data
- Analytics: Occupancy trends, efficiency indicators, alert logs
- Semantic video search using 1152D embeddings
- Employee insights and productivity metrics
- Room activity and attendance tracking

### 🔐 Subscription & Licensing
- Tiered license system: Attendance, Search, Summarization
- License key management and validation

---

## 🏗️ Technology Stack

| Component | Technology |
|:----------|:-----------|
| **Backend Language** | Python 3.10+ |
| **Backend Framework** | FastAPI 0.135.1 |
| **Frontend Framework** | React.js |
| **Database** | PostgreSQL with pgvector |
| **Vector Search** | pgvector, FAISS |
| **Computer Vision** | OpenCV, PyTorch, YOLOv8 |
| **Face Recognition** | FaceNet-PyTorch, ArcFace |
| **Video Processing** | FFmpeg, imageio |
| **Object Tracking** | BoxMOT |
| **File Storage** | MinIO (S3-compatible) |
| **Task Queue** | Celery with Redis |
| **Message Broker** | RabbitMQ, Kafka |
| **ORM** | SQLAlchemy 2.0+ |
| **Async** | asyncpg, asyncio |
| **API Documentation** | FastAPI Auto Docs (Swagger) |
| **Containerization** | Docker & Docker Compose |

---

## 👥 Team Members

| Name | ID | Program | Role |
|------|-------|---------|------|
| Abd Elrahman | 202201023 | SWAPD | Software Engineer (Backend/Frontend) |
| Bosy Ayman | 202202076 | DSAI | CV & Video Analytics |
| Shahd Hossam | 202100936 | SWAPD | Software Engineer (Backend/Frontend) |
| Habiba Mohamed | 202201684 | DSAI | CV & Video Analytics |

---

## 📁 Project Structure

```
Rawi-Vision/
├── backend/                          # FastAPI backend application
│   ├── main.py                       # Entry point
│   ├── config.py                     # Configuration settings
│   ├── database.py                   # Database connection
│   ├── requirements.txt               # Python dependencies (381 packages)
│   ├── docker-compose.yaml           # Docker services (PostgreSQL, Redis, etc.)
│   ├── alembic/                      # Database migrations
│   │
│   ├── employee_onboarding/          # Employee management
│   │   ├── models/employee.py        # Employee model with embeddings
│   │   ├── routers/                  # API endpoints
│   │   ├── service/                  # Business logic
│   │   └── schemas/                  # Pydantic schemas
│   │
│   ├── camera_onboarding/            # Camera management
│   │   ├── models/camera.py          # Camera model
│   │   ├── models/camera_metadata.py # Camera metadata
│   │   └── routers/                  # API endpoints
│   │
│   ├── attendance/                   # Attendance tracking
│   │   ├── models/attendance.py      # Attendance model
│   │   ├── service/                  # Duration calculation
│   │   └── routers/                  # API endpoints
│   │
│   ├── anomaly/                      # Anomaly detection
│   │   ├── models/anomaly.py         # Anomaly model with types
│   │   ├── celery_tasks/             # Background tasks
│   │   └── routers/                  # API endpoints
│   │
│   ├── search/                       # Video search & indexing
│   │   ├── models/search.py          # IndexedVideo, VideoFrame models
│   │   ├── routers/search.py         # Search API
│   │   ├── celery_tasks/tasks.py     # Video indexing tasks
│   │   └── core/offline_index.py     # Offline indexing logic
│   │
│   ├── summarization/                # Video summarization
│   │   ├── models/summary.py         # VideoSummary model
│   │   ├── celery_tasks/             # Summarization tasks
│   │   └── routers/                  # API endpoints
│   │
│   ├── auth/                         # Authentication & authorization
│   │   ├── models/system_user.py     # System user model
│   │   └── routers/auth.py           # Auth endpoints
│   │
│   ├── subscription/                 # License management
│   │   ├── models/license.py         # License model
│   │   └── routers/                  # License endpoints
│   │
│   └── camera_ingestion/             # Video ingestion pipeline
│       ├── ai/                       # AI inference
│       └── fusion.py                 # Data fusion
│
├── frontend/                         # React.js frontend
│   ├── src/
│   │   ├── pages/                    # Page components
│   │   │   ├── DashboardMain.js      # Main dashboard
│   │   │   ├── Anomalies.js          # Anomalies page
│   │   │   ├── Summarization.js      # Video summarization
│   │   │   ├── SmartSearch.js        # Vector search
│   │   │   ├── Clips.js              # Video clips
│   │   │   ├── AllCameras.js         # Camera management
│   │   │   ├── AllEmployees.js       # Employee management
│   │   │   └── VideoFeed.js          # Live video feed
│   │   │
│   │   ├── components/               # Reusable components
│   │   │   ├── dashboard/            # Dashboard components
│   │   │   ├── modals/               # Modal dialogs
│   │   │   └── camera/               # Camera components
│   │   │
│   │   ├── api/                      # API client functions
│   │   │   ├── attendance.js         # Attendance API
│   │   │   ├── anomalies.js          # Anomalies API
│   │   │   ├── search.js             # Search API
│   │   │   ├── summarization.js      # Summarization API
│   │   │   └── employees.js          # Employee API
│   │   │
│   │   ├── App.js                    # Main app component
│   │   ├── App.css                   # Global styles
│   │   └── index.js                  # Entry point
│   │
│   ├── package.json                  # Frontend dependencies
│   ├── public/                       # Static assets
│   └── Dockerfile                    # Frontend Docker image
│
├── ai/                               # AI/ML modules
│   ├── search/                       # Search module
│   │   ├── core/                     # Core search logic
│   │   ├── offline_index.py          # Offline indexing
│   │   └── extracted_clips/          # Extracted video clips
│   │
│   └── summarization/                # Summarization module
│       ├── main.py                   # Main entry point
│       ├── frame_processor.py        # Frame processing
│       ├── object_detection.py       # Object detection
│       ├── motion_filter.py          # Motion filtering
│       ├── camera_manager.py         # Camera stream management
│       ├── utils.py                  # Utility functions
│       └── config.yaml               # Configuration
│
├── DATABASE_SCHEMA.md                # Complete database documentation
├── docker-compose.yaml               # Main compose file
├── README.md                         # This file
└── .gitignore                        # Git ignore rules

```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.10+**
- **Node.js 16+** (for frontend)
- **PostgreSQL 13+** with pgvector extension
- **Redis** (for caching & Celery)
- **Docker & Docker Compose** (recommended)
- **CUDA 11.8+** (optional, for GPU acceleration)

### Installation

#### 1. Clone the Repository
```bash
git clone https://github.com/shahdhoss/RawiVision.git
cd Rawi-Vision
```

#### 2. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
alembic upgrade head

# Start the backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 3. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Create .env file
cp .env.example .env

# Start the frontend
npm start
# Frontend runs on http://localhost:3000
```

#### 4. Docker Setup (Recommended)
```bash
# Build and start all services
docker-compose up -d

# Services will be available at:
# - Backend API: http://localhost:8000
# - Frontend: http://localhost:3000
# - PostgreSQL: localhost:5432
# - Redis: localhost:6379
# - MinIO: http://localhost:9000
```

---

## 📊 Database Schema

The database consists of **10 tables** with comprehensive schema for surveillance data:

**Core Tables:**
- `employees` - Employee records with face embeddings (512D)
- `cameras` - Camera device information
- `attendance` - Attendance tracking with duration calculation
- `anomalies` - Detected security anomalies

**Search & Indexing:**
- `indexed_videos` - Video files in MinIO storage
- `video_frames` - Extracted frames with embeddings (1152D)

**Management:**
- `video_summaries` - AI-generated video summaries
- `system_users` - Admin/manager accounts
- `license_info` - Subscription and licensing

For complete schema documentation, see [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)

---

## 🔌 API Endpoints

### Authentication
```
POST   /auth/login              - Login with email/password
POST   /auth/logout             - Logout user
POST   /auth/google             - Google OAuth login
GET    /auth/me                 - Get current user
```

### Employees
```
GET    /employees               - List all employees
GET    /employees/{id}          - Get employee details
POST   /employees               - Create new employee
PUT    /employees/{id}          - Update employee
DELETE /employees/{id}          - Delete employee
POST   /employees/{id}/embed    - Generate face embedding
```

### Cameras
```
GET    /cameras                 - List all cameras
GET    /cameras/{id}            - Get camera details
POST   /cameras                 - Register new camera
PUT    /cameras/{id}            - Update camera
DELETE /cameras/{id}            - Delete camera
```

### Attendance
```
GET    /attendance              - List attendance records
GET    /attendance/today        - Get today's attendance
POST   /attendance              - Record attendance
GET    /employees/{id}/attendance - Get employee attendance history
```

### Anomalies
```
GET    /anomalies               - List anomalies
GET    /anomalies/{id}          - Get anomaly details
DELETE /anomalies/{id}          - Delete anomaly
GET    /anomalies/type/{type}   - Filter by type
```

### Search (Vector Search)
```
POST   /search/query            - Semantic video search
GET    /search/videos           - List indexed videos
POST   /search/index            - Start video indexing
GET    /search/video/{id}/stream - Stream video
```

### Summarization
```
POST   /summarization/generate  - Generate video summary
GET    /summarization/summary/{id} - Get summary details
GET    /summarization/summary/{id}/stream - Stream summary
DELETE /summarization/summary/{id} - Delete summary
```

### API Documentation
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## ⚙️ Configuration

### Backend (.env)
```
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/rawi_vision
DATABASE_POOL_SIZE=20

# Redis
REDIS_URL=redis://localhost:6379

# MinIO
MINIO_URL=http://localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=rawi-vision

# JWT
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION=86400

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

### Frontend (.env)
```
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
REACT_APP_ENV=development
```

---

## 🎮 Running the Project

### Development Mode

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm start
```

**Terminal 3 - Celery Worker (optional, for background tasks):**
```bash
cd backend
celery -A celery_app worker -l info
```

### Docker Mode
```bash
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop services
docker-compose down
```

---

## 📖 API Documentation

### Interactive API Docs
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### Example Request
```bash
# Get all employees
curl -X GET "http://localhost:8000/employees" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Search for videos
curl -X POST "http://localhost:8000/search/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "person entering room", "limit": 10}'

# Generate video summary
curl -X POST "http://localhost:8000/summarization/generate" \
  -H "Content-Type: application/json" \
  -d '{"video_id": "uuid", "camera_id": "camera-1"}'
```

---

## 🔄 Background Tasks

### Celery Workers
The system uses Celery for async tasks:

**Available Tasks:**
- `record_and_index_task` - Index video frames with embeddings
- `summarize_video_task` - Generate video summaries
- `detect_anomalies_task` - Real-time anomaly detection
- `track_attendance_task` - Update attendance records

### Running Workers
```bash
# Start Celery worker
celery -A celery_app worker -l info

# Start Celery beat scheduler
celery -A celery_app beat -l info

# Monitor tasks
celery -A celery_app events
```

---

## 📝 Development Guidelines

### Code Structure
- **Models:** Database schemas using SQLAlchemy ORM
- **Routers:** FastAPI route handlers and endpoint definitions
- **Services:** Business logic and data processing
- **Schemas:** Pydantic schemas for request/response validation
- **Repositories:** Database operations and queries

### Adding New Features

1. **Create Model** (`models/`)
2. **Create Schema** (`schemas/`)
3. **Create Repository** (`repository/`)
4. **Create Service** (`service/`)
5. **Create Router** (`routers/`)
6. **Add Tests** (`tests/`)

### Database Migrations
```bash
# Create migration
alembic revision --autogenerate -m "Add new column"

# Apply migration
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

---

## 🧪 Testing

### Run Backend Tests
```bash
cd backend
pytest

# With coverage
pytest --cov=.

# Specific test file
pytest tests/test_attendance.py -v
```

### Run Frontend Tests
```bash
cd frontend
npm test

# With coverage
npm test -- --coverage
```

---

## 🔐 Security Considerations

1. **Environment Variables** - Store sensitive data in `.env` files (added to `.gitignore`)
2. **JWT Tokens** - Use secure token-based authentication
3. **Database** - PostgreSQL with encrypted passwords
4. **CORS** - Restrict cross-origin requests to trusted domains
5. **Rate Limiting** - Implement rate limits on API endpoints
6. **Input Validation** - Pydantic schema validation on all inputs
7. **HTTPS** - Use HTTPS in production environments

---

## 📈 Performance Optimization

1. **Vector Indexes** - IVFFlat indexes on pgvector embeddings
2. **Database Partitioning** - Partition large tables by date
3. **Connection Pooling** - Use asyncpg connection pool
4. **Caching** - Redis for session and data caching
5. **Batch Operations** - Bulk insert/update for frames
6. **GPU Acceleration** - CUDA for AI inference

---

## 🐛 Troubleshooting

### Database Connection Error
```bash
# Check PostgreSQL is running
psql -U postgres -d rawi_vision

# Check pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
```

### Redis Connection Error
```bash
# Check Redis is running
redis-cli ping
# Should return: PONG
```

### Video Upload Error
```bash
# Check MinIO is running
curl http://localhost:9000/minio/health/live

# Check bucket exists
aws s3 ls s3://rawi-vision --endpoint-url http://localhost:9000
```

---

## 📚 Documentation

- [Database Schema](./DATABASE_SCHEMA.md) - Complete PostgreSQL schema documentation
- [API Documentation](http://localhost:8000/docs) - Interactive Swagger UI
- [Design Resources - Figma](https://www.figma.com/design/o6mXzHKVRwtDFwYj66FZQI/CCTV-Website-s-Project---Portfolio--Community-?node-id=0-1&p=f&t=vfTXifMfQLfhQKvz-0)

---

## 🤝 Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Commit changes: `git commit -am 'Add feature'`
3. Push to branch: `git push origin feature/your-feature`
4. Open a pull request to `main` branch
5. Ensure all tests pass and code is formatted

---

## 📄 License

This project is part of a graduation project at [Your University]. All rights reserved.

---

## 📞 Support

For issues, questions, or feedback:
- **GitHub Issues:** [Create an issue](https://github.com/shahdhoss/RawiVision/issues)
- **Email:** [contact information]
- **Discord/Slack:** [community link]

---

## 🎓 Acknowledgments

- **Supervisor:** Dr. Doaa Shawky
- **Team:** Abd Elrahman, Bosy Ayman, Shahd Hossam, Habiba Mohamed
- **Dependencies:** OpenCV, PyTorch, FastAPI, React, PostgreSQL, and the open-source community

---

## 📅 Version History

- **v1.0** (2026-06-15) - Initial release
  - Real-time face recognition & tracking
  - Adaptive video summarization
  - Anomaly detection system
  - Interactive dashboard
  - Vector search capability
  - License management

---

**Last Updated:** 2026-06-15  
**Status:** ✅ Production Ready
