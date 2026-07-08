# Owner: shared (Sprint 2 deployment prep)
FROM python:3.12-slim

WORKDIR /app

# System deps kept minimal on purpose -- add here only if a future
# dependency (e.g. a compiled package) actually needs a build toolchain.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render injects $PORT at runtime and expects the app to bind to it. The
# default is only for local `docker run` without -e PORT=....
ENV PORT=10000 \
    PYTHONUNBUFFERED=1 \
    NUDGE_DB_PATH=/var/data/nudge.db
EXPOSE 10000

# wsgi:app (not app:app) -- see wsgi.py for why. Shell form so $PORT
# actually expands; exec form (a JSON array) would pass the literal
# string "${PORT}" to gunicorn instead of substituting it.
CMD python -m scripts.init_db && gunicorn --worker-class eventlet -w 1 -b 0.0.0.0:${PORT} wsgi:app
