from ext.web import app

@app.get("/")
def read_root():
    return "Pong"

uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
