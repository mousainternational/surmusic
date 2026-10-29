# Sur Music website — production image (by Mousa International Software House)
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STORAGE_DIR=/data/storage \
    GEOIP_DB=/data/storage/geoip.sqlite

WORKDIR /srv/surmusic

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY wsgi.py .

# Run as an unprivileged user; uploads go to a separate volume that is never executed.
RUN useradd --system --uid 10001 --home /srv/surmusic surmusic \
    && mkdir -p /data/storage \
    && chown -R surmusic:surmusic /data
USER surmusic

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT', '8000') + '/ping', timeout=4).status == 200 else 1)"

# --preload creates tables once before workers start.
# PORT is set by hosts such as Render (default 8000); WEB_CONCURRENCY = number of workers (default 3).
CMD ["sh", "-c", "exec gunicorn --preload --workers ${WEB_CONCURRENCY:-3} --threads 4 --worker-class gthread --timeout 300 --bind 0.0.0.0:${PORT:-8000} --forwarded-allow-ips '*' --access-logfile - wsgi:app"]
