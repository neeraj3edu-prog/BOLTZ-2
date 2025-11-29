FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    BOLTZ_CACHE=/app/.boltz \
    BOLTZ_API_JOBS_DIR=/app/api_jobs

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip3 install --upgrade pip

# Set working directory
WORKDIR /app

# Install Boltz first (includes all dependencies)
RUN pip3 install boltz[cuda] -U

# Install additional API dependencies
RUN pip3 install fastapi uvicorn pydantic python-multipart pyyaml aiofiles

# Copy API code
COPY api/main.py /app/main.py

# Create directories
RUN mkdir -p /app/.boltz /app/api_jobs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
