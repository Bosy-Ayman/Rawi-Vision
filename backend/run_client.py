import uvicorn

if __name__ == "__main__":
    print("🚀 Starting Client Backend on port 8000...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
