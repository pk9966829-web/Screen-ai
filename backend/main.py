from fastapi import FastAPI, UploadFile, File
from pathlib import Path

app = FastAPI(title="Screen AI")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


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

    return {
        "filename": file.filename,
        "saved_to": str(file_path),
        "message": "Screen image received and saved!"
    }