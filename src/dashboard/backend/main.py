from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

HELLO_MESSAGE = "Hello from the dashboard API"


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": HELLO_MESSAGE}


_static_dir = Path(__file__).resolve().parent / "static"
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
