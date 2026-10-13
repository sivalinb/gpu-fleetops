FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 GRADIO_ANALYTICS_ENABLED=False \
    FLEETOPS_DATABASE_URL=sqlite:////data/fleetops.db PORT=7860
WORKDIR /app
COPY requirements.lock requirements-postgres.txt ./
RUN pip install --no-cache-dir -r requirements.lock -r requirements-postgres.txt
COPY pyproject.toml README.md ./
COPY src ./src
COPY app.py ./
RUN pip install --no-cache-dir --no-deps . \
    && useradd --create-home --uid 1000 fleetops \
    && mkdir -p /data && chown -R fleetops:fleetops /data /app
USER fleetops
EXPOSE 7860
HEALTHCHECK --interval=15s --timeout=5s --start-period=45s --retries=8 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/readyz', timeout=4)"
CMD ["python", "app.py"]
