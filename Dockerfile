FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install wheel

COPY requirements/base.txt .

RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r base.txt

FROM python:3.11-slim

WORKDIR /app

COPY requirements/base.txt .

COPY --from=builder /app/wheels /wheels

RUN pip install --no-cache-dir --no-index --find-links=/wheels -r base.txt

COPY src/ .

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]