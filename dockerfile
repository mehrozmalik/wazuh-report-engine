# syntax=docker/dockerfile:1
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Long timeouts + automatic retries for slow connections
ENV PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=10 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .

# The cache mount keeps already-downloaded wheels, so a retry resumes instead of starting over
RUN --mount=type=cache,target=/root/.cache/pip \
    n=0; until pip install -r requirements.txt; do \
      n=$((n+1)); [ "$n" -ge 5 ] && exit 1; echo "pip failed, retry $n/5"; sleep 5; \
    done

COPY app.py report.html.j2 ./
CMD ["gunicorn","-b","0.0.0.0:5055","-t","120","app:app"]
