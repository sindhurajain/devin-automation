from fastapi import FastAPI

app = FastAPI(title="Devin Automation Boilerplate")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status")
async def status() -> dict[str, str]:
    return {"status": "ready", "message": "Minimal deployment boilerplate is running."}
