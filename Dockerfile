# GramArogya AI — single-image deploy (Hugging Face Docker Space, Render, etc.)
# FastAPI serves both the API and the built React app on one port → one URL, no CORS.

# ---------- Stage 1: build the React frontend ----------
FROM node:22-slim AS frontend
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build          # outputs /fe/dist

# ---------- Stage 2: Python backend + bundled frontend ----------
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# libgomp1 is required at runtime by XGBoost.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code, trained model, and seed data.
COPY backend/ ./backend/
COPY data/ ./data/

# Bundled production frontend from stage 1.
COPY --from=frontend /fe/dist ./frontend/dist

# Listens on $PORT when the host provides one (Render), else 7860 (Hugging Face).
EXPOSE 7860

# Seed on first boot (idempotent, non-fatal), then serve the app.
CMD ["sh", "-c", "python -m backend.startup_seed; exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
