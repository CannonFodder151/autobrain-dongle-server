FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir fastapi==0.133.0 "uvicorn[standard]==0.34.0"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY dongle_server ./dongle_server
EXPOSE 8000
CMD ["uvicorn", "dongle_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
