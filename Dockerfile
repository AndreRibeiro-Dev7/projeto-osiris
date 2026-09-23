FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

RUN addgroup --system osiris && adduser --system --ingroup osiris osiris

COPY pyproject.toml README.md alembic.ini /app/
COPY app /app/app
COPY migrations /app/migrations
COPY dist /app/dist
COPY scripts /app/scripts

RUN pip install --upgrade pip && pip install . && chown -R osiris:osiris /app

USER osiris

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT', '8000') + '/api/v1/health', timeout=3)"

CMD ["sh", "-c", "alembic upgrade head && if [ \"${SEED_DEMO_HISTORY:-false}\" = \"true\" ]; then python scripts/seed_demo_history.py; fi && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
