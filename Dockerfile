# OctoMarket — production image (18A Phase 1)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENV=production \
    FLASK_DEBUG=False \
    DATA_DIR=/data \
    DEPLOYMENT_GATE=17B \
    PORT=8080

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /data/replay /data/learning /data/research

EXPOSE 8080

CMD ["/app/docker-entrypoint.sh"]
