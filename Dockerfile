FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY reviewer/ reviewer/
COPY registry/ registry/
COPY scripts/ scripts/

ENTRYPOINT ["python", "-m", "reviewer.main"]
