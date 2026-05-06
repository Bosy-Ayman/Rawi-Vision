# Video Search - Simple, Single File

**Just one Python file.** Index videos, search semantically, get JSON with AI summaries.

## Quick Start

```bash
# 1. Install (one line)
pip install torch transformers sentence-transformers faiss-cpu opencv-python pillow

# 2. Index your video
python video_search.py index video.mp4

# 3. Search and get JSON
python video_search.py search "wooden room with furniture" --output results.json
```

## What You Get

Clean JSON output with **TWO summaries**:

```json
{
  "query": "wooden room with furniture",
  "total_results": 6,
  "results": [
    {
      "frame_id": 32,
      "timestamp": 49.82,
      "description": "The image depicts a scene inside a room with wooden paneling...",
      "similarity": 24.0
    }
  ],
  "summaries": {
    "overall_video": "Complete summary of the entire video...",
    "query_results": "Summary specific to your search query results..."
  }
}
```

## Key Points

✅ **One file** - `video_search.py` (343 lines)
✅ **Semantic search** - Understands meaning, not just keywords
✅ **Query-based summarization** - Summarizes based on what you searched for
✅ **JSON output** - Ready for backend integration
✅ **Fast search** - <100ms after indexing
✅ **Similarity scores** - Percentages (0-100) for clarity

## Commands

```bash
# Index a video
python video_search.py index videos/sample.mp4 --sampling 16

# Search (simple query)
python video_search.py search "wooden room"

# Search with options
python video_search.py search "query" --top-k 20 --output results.json --no-summary

# Use webcam
python video_search.py index 0
```

## Python Usage

```python
from video_search import VideoSearch
import json

vs = VideoSearch()
vs.index_video("video.mp4")

# Get JSON results
result = vs.search("your query", top_k=10, summarize=True)
print(json.dumps(result, indent=2))
```

## Similarity Scores

- **50-100%**: Excellent match
- **30-49%**: Good match  
- **20-29%**: Possible match
- **<20%**: Weak match

*Note: Results are best when your search query matches actual video content.*

## Files

- `video_search.py` - Main module (run this)
- `USAGE.txt` - Detailed usage guide

## Next

Ready to send results to your backend! The JSON format works with any backend.

For detailed info, see `USAGE.txt`