FROM python:3.13-slim AS build
ENV UV_CACHE_DIR=/build/.cache/uv UV_PYTHON_DOWNLOADS=never
WORKDIR /build
RUN pip install --no-cache-dir uv==0.12.19
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/app/.venv/bin:$PATH APP_RUNTIME=/app/runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends nodejs && rm -rf /var/lib/apt/lists/* && useradd --uid 10001 --create-home app
COPY --from=build /build/.venv /app/.venv
COPY app ./app
COPY schemas ./schemas
COPY scripts/validate_math.cjs ./scripts/validate_math.cjs
RUN mkdir -p runtime staticfiles && chown -R 10001:10001 runtime staticfiles && python app/manage.py collectstatic --noinput
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/', timeout=3)" || exit 1
CMD ["gunicorn", "--chdir", "app", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--access-logfile", "-", "--error-logfile", "-"]
