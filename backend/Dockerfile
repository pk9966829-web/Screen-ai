FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

RUN apt-get update && apt-get install -y --no-install-recommends gosu && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd --system vosi && useradd --system --gid vosi --home-dir /app vosi

COPY backend/requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip && pip install -r requirements.txt

COPY backend/ ./
COPY backend/docker-entrypoint.sh /usr/local/bin/vosi-entrypoint
RUN chmod 0755 /usr/local/bin/vosi-entrypoint && \
    mkdir -p /data /app/backend/uploads && \
    chown -R vosi:vosi /app /data

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health/ready', timeout=4)" || exit 1

ENTRYPOINT ["/usr/local/bin/vosi-entrypoint"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers", "--forwarded-allow-ips", "*"]
