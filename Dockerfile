# RolnikSzukaWody: one image with the API and the built frontend (plan, decision 8).

# --- 1. Frontend build -------------------------------------------------------------------------------------
FROM node:22.23.5-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 2. Runtime: Python + WeasyPrint system libraries --------------------------------------------------------
FROM python:3.12.16-slim-trixie AS runtime
# CURL_CA_BUNDLE: GDAL's bundled curl (rasterio wheel) must find Debian's CA bundle for HTTPS COG reads.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
# Pango/HarfBuzz for WeasyPrint; DejaVu + Liberation fonts carry the Polish characters used in the PDF.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/app ./app
COPY backend/scripts/warm_cache.py ./scripts/warm_cache.py
COPY --from=frontend /build/frontend/dist /app/frontend/dist

# Unprivileged user; /data holds the disk cache and the SQLite reports (a volume in docker-compose.yml).
# Font cache built as root, so WeasyPrint does not rescan fonts (and warn) on every start as the app user.
RUN fc-cache -f && useradd --system --uid 10001 --home-dir /app app && mkdir -p /data/cache && chown -R app /data
USER app

ENV RSW_CACHE_DIR=/data/cache \
    RSW_DB_PATH=/data/reports.sqlite3 \
    RSW_FRONTEND_DIST=/app/frontend/dist \
    RSW_CORS_ORIGINS=[] \
    XDG_CACHE_HOME=/data/cache/xdg

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

# One worker only: analysis jobs live in this process's memory (app/api/jobs.py).
# --proxy-headers: the client address seen by the rate limiter is the real one, not Caddy's.
# --no-access-log: no IP addresses in the logs (CLAUDE.md rule 10).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--no-access-log"]
# "*" is safe only because the port is reachable solely from Caddy, which overwrites X-Forwarded-For. Never
# publish port 8000 directly (docker run -p 8000:8000) on a public host.
