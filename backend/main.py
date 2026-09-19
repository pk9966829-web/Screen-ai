from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pathlib import Path

from pipeline import ScreenPipeline


app = FastAPI(title="Screen AI")


# Allow the Screen AI desktop app to communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Folder where uploaded screenshots are stored
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# Make uploaded screenshots accessible through:
# http://127.0.0.1:8001/uploads/<filename>
app.mount(
    "/uploads",
    StaticFiles(directory="uploads"),
    name="uploads"
)


# Initialize Screen AI processing pipeline
pipeline = ScreenPipeline()


@app.get("/")
def root():
    return {
        "success": True,
        "message": "Screen AI backend is running"
    }


@app.post("/screen")
async def receive_screen(file: UploadFile = File(...)):
    # Save uploaded screenshot
    file_path = UPLOAD_DIR / file.filename

    contents = await file.read()
    file_path.write_bytes(contents)

    # Process screenshot through Screen AI pipeline
    result = pipeline.process_image(
        str(file_path)
    )

    return result