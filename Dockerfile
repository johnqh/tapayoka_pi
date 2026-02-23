FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    bluetooth bluez libbluetooth-dev \
    libdbus-1-dev libglib2.0-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/

RUN mkdir -p /root/.tapayoka

CMD ["python", "-m", "src.main"]
