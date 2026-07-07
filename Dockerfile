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

# Render (and most PaaS targets) inject $PORT at runtime and expect the
# app to bind to it -- do not hardcode a port here. 5000 is just the
# documented default for local `docker run` without -e PORT=....
ENV PORT=5000
EXPOSE 5000

# wsgi:app (not app:app) -- see wsgi.py for why. Shell form so $PORT
# actually expands; exec form (a JSON array) would pass the literal
# string "${PORT}" to gunicorn instead of substituting it.
CMD gunicorn --worker-class eventlet -w 1 -b 0.0.0.0:${PORT} wsgi:app
