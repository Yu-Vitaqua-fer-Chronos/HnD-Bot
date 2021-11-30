from hata.ext import asyncio
from fastapi.responses import HTMLResponse
import uvicorn

from ext.web import app

@app.get("/")
def read_root():
    return HTMLResponse("Pong")

uvicorn.run(app, host="0.0.0.0", port=8080, log_level="debug")
