FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir requests

COPY openclaw.py /app/openclaw.py

CMD ["python", "/app/openclaw.py"]

