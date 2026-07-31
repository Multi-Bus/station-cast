"""FastAPI application entrypoint."""

from fastapi import FastAPI

app = FastAPI(title="Station Cast API")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
