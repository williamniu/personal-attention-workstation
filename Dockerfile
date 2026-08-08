FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN pip install --no-cache-dir uv && uv sync --no-dev
COPY . .
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "hcis.api.app:app", "--host", "0.0.0.0", "--port", "8080"]

