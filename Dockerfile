FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
 && rm -rf /var/lib/apt/lists/*

ARG INSTALL_DEV=false

RUN pip install --no-cache-dir openai pytz
COPY requirements-dev.txt /tmp/requirements-dev.txt
RUN if [ "$INSTALL_DEV" = "true" ]; then pip install --no-cache-dir -r /tmp/requirements-dev.txt; fi

COPY . /app

CMD ["python", "main.py"]
