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

# Create Boltz cache directory
RUN mkdir -p /root/.boltz/ccd

# Download CCD (Chemical Component Dictionary) files required by Boltz
RUN cd /root/.boltz/ccd && \
    wget -q https://files.rcsb.org/pub/pdb/data/monomers/components.cif.gz && \
    gunzip components.cif.gz && \
    echo "CCD files downloaded successfully"

# Set Boltz cache directory
ENV BOLTZ_CACHE=/root/.boltz

# Copy API code
COPY main.py /app/main.py

# Copy receptor-specific templates
COPY template_path /app/template_path

# Create startup script to download models if needed
RUN echo '#!/bin/bash\n\
echo "Checking Boltz model files..."\n\
if [ ! -f "/root/.boltz/boltz1.ckpt" ]; then\n\
  echo "Downloading Boltz model files (this may take a few minutes on first start)..."\n\
  python3 -c "from pathlib import Path; from boltz.main import download_boltz2; download_boltz2(Path(\"/root/.boltz\"))" || echo "Model download failed, will retry on first prediction"\n\
fi\n\
echo "Starting API server..."\n\
exec uvicorn main:app --host 0.0.0.0 --port 8000\n\
' > /app/start.sh && chmod +x /app/start.sh

# Create directories
RUN mkdir -p /app/.boltz /app/api_jobs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run startup script
CMD ["/app/start.sh"]
