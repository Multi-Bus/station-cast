"""FastAPI application entrypoint.

Endpoints live in api/routers/ and are mounted under /api; the built frontend
is served from / by the same process, so there is no cross-origin hop and no
CORS configuration to keep in sync. /health stays at the root because load
balancers probe it before the app has any business routes.
"""

import asyncio
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from stationcast.api.data import CorridorDataUnavailable
from stationcast.api.routers import arrivals, congestion, stops

# Matches weather_forecast.py's own KMA call timeout (3.0s) -- /stops/{id}/context
# can fall back to that live call, observed up to 1.9s.
REQUEST_TIMEOUT_SECONDS = 3.0

STATIC_DIR = Path("frontend/dist")

app = FastAPI(title="Station Cast API")


@app.exception_handler(CorridorDataUnavailable)
async def corridor_data_unavailable_handler(
    request: Request, exc: CorridorDataUnavailable
) -> JSONResponse:
    """503, not 500 -- the service is fine, it just hasn't been given its
    data yet (e.g. a container started without the data volume mounted)."""
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.middleware("http")
async def enforce_request_timeout(request: Request, call_next):
    """Cut off any request that overruns the response-time budget (issue #18)."""
    try:
        return await asyncio.wait_for(call_next(request), timeout=REQUEST_TIMEOUT_SECONDS)
    except TimeoutError:
        return JSONResponse(status_code=504, content={"detail": "request timed out"})


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


api_router = APIRouter(prefix="/api")
api_router.include_router(stops.router)
api_router.include_router(congestion.router)
api_router.include_router(arrivals.router)
app.include_router(api_router)

# Mounted last so it only catches what the API routes above didn't. Absent in a
# backend-only checkout (nobody has run `npm run build`), which is why this is a
# conditional mount rather than a StaticFiles that would fail at import time.
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
