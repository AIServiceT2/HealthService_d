# 전운시 AI 내부 API (rep_engine + service). 실행: uvicorn service.app:app --port 8001
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements-service.txt .
RUN pip install -r requirements-service.txt

COPY rep_engine/ rep_engine/
COPY service/ service/
COPY config/ config/

RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8001
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8001"]
