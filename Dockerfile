# Use the small, efficient base image. Python 3.13 is pinned because the
# coincurve runtime dependency does not yet publish a Python 3.14 wheel.
FROM python:3.13-slim@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285

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

