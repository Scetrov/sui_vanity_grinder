# Use the small, efficient base image. Python 3.13 is pinned because the
# coincurve runtime dependency does not yet publish a Python 3.14 wheel.
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

# Avoid interactive prompts and cache bloat
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install fully hash-pinned Python dependencies before application code so
# dependency layers can be reused safely.
COPY requirements.txt .
RUN pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements.txt

# Copy script into container
COPY sui_vanity_grinder.py .

# Default command (override with docker run args)
ENTRYPOINT ["python", "sui_vanity_grinder.py"]

