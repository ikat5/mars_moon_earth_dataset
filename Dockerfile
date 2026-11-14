# TerraTwin server image: analog-search API + globe page. Requires real release Parquet files (run `git lfs pull`
# before building). The lunar DEM (1.06 GB) is optional and mounted at runtime; see analysis/RUNBOOK.md.
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    TERRATWIN_LDEM=/data/ldem_64.tif TERRATWIN_TILE_CACHE=/data/tile_cache
WORKDIR /srv/terratwin
COPY processing/requirements.txt processing/requirements.txt
COPY frontend/requirements.txt frontend/requirements.txt
RUN pip install --no-cache-dir -r processing/requirements.txt -r frontend/requirements.txt
COPY . .
RUN python -c "from processing.test_support import has_release_data as h; \
    assert h('prepared/0.2.0'), 'prepared/0.2.0 Parquet files are Git LFS pointers: run git lfs pull before docker build'" \
 && useradd --create-home --uid 10001 terratwin && mkdir -p /data && chown terratwin /data \
 && chown terratwin frontend
USER terratwin
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c \
    "import urllib.request,sys; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health').status != 200)"
CMD ["uvicorn", "--app-dir", "frontend", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
