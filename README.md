# Rawi Vision Platform
> **Graduation Project** > **Supervisor:** Dr. Doaa Shawky
## Abstract

Video surveillance systems capture massive amounts of footage daily, making manual review inefficient. This project is a **Real-time Video Analysis Platform** designed to automate the extraction of meaningful insights from surveillance feeds.

By integrating **Face Recognition**, **Video Summarization**, and **Anomaly Detection**, the platform enhances situational awareness, tracks employee attendance/productivity, and detects suspicious behavior automatically. The system features a unified dashboard for real-time alerts and analytical visualization.
## Key Features

* **Real-time Face Recognition & Tracking:**
    * Automated attendance tracking.
    * Identification of unauthorized personnel (stranger detection).
    * Robust tracking across multiple cameras using Re-ID.
* **Adaptive Video Summarization:**
    * compresses lengthy video streams by removing redundant or idle segments.
    * Highlights key events based on motion and importance scores.
* **Suspicious Behavior Detection:**
    * Instant alerts for anomalies (e.g., fighting, vandalism) using deep learning.
* **Interactive Dashboard:**
    * Live monitoring interface.
    * Analytics: Occupancy trends, efficiency indicators, and alert logs.
    * Face search functionality (using Vector Search).
## Technology Stack

| Component | Technology |
| :--- | :--- |
| **Language** | Python |
| **Computer Vision** | OpenCV, PyTorch / TensorFlow |
| **Backend API** | FastAPI |
| **Frontend** | React.js |
| **Database/Storage** | SQL (Metadata), FAISS (Vector Embeddings) |
| **Inference Acceleration** | CUDA |

## Team Members

|**Name**|**ID**|**Program**|**Role**|
|---|---|---|---|
|**Abd Elrahman**|202201023|SWAPD|Software Engineer (Backend/Frontend)|
|**Bosy Ayman**|202202076|DSAI|CV & Video Analytics|
|**Shahd Hossam**|202100936|SWAPD|Software Engineer (Backend/Frontend)|
|**Habiba Mohamed**|202201684|DSAI|CV & Video Analytics|


## Design Resources

*   **Figma Playground:** [View Playground](https://www.figma.com/design/o6mXzHKVRwtDFwYj66FZQI/CCTV-Website-s-Project---Portfolio--Community-?node-id=0-1&p=f&t=vfTXifMfQLfhQKvz-0)
*   **Final Design:** [View Final Design](https://www.figma.com/board/sFoKmAZY2RjSbnqmEHr9Ch/RawiVision?node-id=1-1841&t=q65dio1v1cJkUEyn-0)
