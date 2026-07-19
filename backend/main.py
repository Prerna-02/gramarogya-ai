"""GramArogya AI — FastAPI application entry point.

Run locally:
    conda activate gramarogya
    uvicorn backend.main:app --reload

Interactive docs: http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

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


@app.get("/", include_in_schema=False)
def root():
    """Bare URL has no page — send visitors to the interactive API docs."""
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
