"""GramArogya AI — FastAPI application entry point.

Run locally:
    conda activate gramarogya
    uvicorn backend.main:app --reload

Interactive docs: http://localhost:8000/docs
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings

app = FastAPI(
    title="GramArogya AI",
    description="Rural healthcare operations and patient-access prototype.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# When the React app has been built (production / container image), serve it from
# the same origin as the API so there is one URL and no CORS. In local dev the
# folder is absent and the bare URL redirects to the API docs instead.
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
_SERVE_FRONTEND = _FRONTEND_DIST.is_dir()


@app.get("/", include_in_schema=False)
def root():
    """Serve the built app if present, otherwise the interactive API docs."""
    if _SERVE_FRONTEND:
        return FileResponse(_FRONTEND_DIST / "index.html")
    return RedirectResponse(url="/docs")


@app.get("/api", tags=["system"])
def api_index() -> dict:
    """Small index so /api doesn't 404."""
    return {"app": "gramarogya-ai", "version": app.version, "docs": "/docs",
            "health": "/api/health"}


@app.get("/api/health", tags=["system"])
def health() -> dict:
    """Liveness probe. Phase 2 completion check expects a success response."""
    return {"status": "ok", "app": "gramarogya-ai", "version": app.version}


from backend.routes import router  # noqa: E402

app.include_router(router)

# Static frontend must be mounted AFTER the API router so /api/* keeps priority.
if _SERVE_FRONTEND:
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        """Serve built static files; fall back to index.html for client-side routes."""
        if full_path.startswith(("api", "docs", "redoc")) or full_path == "openapi.json":
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (_FRONTEND_DIST / full_path).resolve()
        if full_path and _FRONTEND_DIST in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
