# Use the small, efficient base image
FROM python:3.12-slim

# Avoid interactive prompts and cache bloat
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install required system dependencies for crypto libs (very lightweight)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libssl-dev \
        libffi-dev \
        pkg-config && \
    rm -rf /var/lib/apt/lists/*

# Copy script into container
WORKDIR /app
COPY sui_vanity_grinder.py .

# Install Python dependencies
RUN pip install --no-cache-dir pynacl coincurve cryptography

# Default command (override with docker run args)
ENTRYPOINT ["python", "sui_vanity_grinder.py"]

