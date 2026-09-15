from fastapi import FastAPI, UploadFile, File
from pathlib import Path

from pipeline import ScreenPipeline

app = FastAPI(title="Screen AI")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

pipeline = ScreenPipeline()


@app.get("/")
def home():
    return {
        "message": "Screen AI backend is running!"
    }


@app.post("/screen")
async def receive_screen(file: UploadFile = File(...)):
    file_path = UPLOAD_DIR / file.filename

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    result = pipeline.process_image(str(file_path))

    return {
        "filename": file.filename,
        "pipeline": result
    }