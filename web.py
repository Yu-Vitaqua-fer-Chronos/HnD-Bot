from ext.web import app

uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info"")
