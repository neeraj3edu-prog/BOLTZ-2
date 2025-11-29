# Boltz GPU Deployment Guide

This guide provides step-by-step instructions for deploying and running Boltz on GPU machines.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running Predictions](#running-predictions)
- [Deployment Scenarios](#deployment-scenarios)
- [Web API Deployment](#web-api-deployment)
- [Optimization](#optimization)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Hardware Requirements
- **GPU**: NVIDIA GPU with CUDA support (16GB+ VRAM recommended)
- **CUDA**: Version 11.8 or higher
- **RAM**: 32GB+ system RAM recommended
- **Storage**: 50GB+ free space (for models, cache, and outputs)

### Software Requirements
- **OS**: Linux (Ubuntu 20.04+), macOS, or Windows with WSL2
- **Python**: 3.8, 3.9, 3.10, or 3.11
- **CUDA Toolkit**: Installed and configured
- **Internet**: Required for initial setup and MSA generation

### Verify GPU Access
```bash
# Check NVIDIA driver
nvidia-smi

# Expected output should show GPU details
# If command not found, install NVIDIA drivers first
```

---

## Installation

### Step 1: Set Up Python Environment

#### Option A: Using Conda (Recommended)
```bash
# Create new environment
conda create -n boltz python=3.10 -y
conda activate boltz
```

#### Option B: Using venv
```bash
# Create virtual environment
python3.10 -m venv boltz_env
source boltz_env/bin/activate  # Linux/macOS
# boltz_env\Scripts\activate   # Windows
```

### Step 2: Install Boltz

#### Option A: Install from PyPI (Stable)
```bash
pip install boltz[cuda] -U
```

#### Option B: Install from Source (Latest)
```bash
# Clone repository
git clone https://github.com/jwohlwend/boltz.git
cd boltz

# Install in editable mode
pip install -e .[cuda]
```

#### Option C: CPU-Only Installation
```bash
# For machines without CUDA
pip install boltz -U
```

### Step 3: Verify Installation
```bash
# Check Boltz installation
boltz --help

# Verify CUDA availability
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'GPU count: {torch.cuda.device_count()}'); print(f'GPU name: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
```

Expected output:
```
CUDA available: True
GPU count: 1
GPU name: NVIDIA A100-SXM4-40GB
```

---

## Configuration

### Set Cache Directory

By default, Boltz downloads models to `~/.boltz`. For GPU clusters, you may want to use a different location.

```bash
# Set environment variable
export BOLTZ_CACHE=/path/to/storage/.boltz

# Make it permanent (add to ~/.bashrc or ~/.zshrc)
echo 'export BOLTZ_CACHE=/path/to/storage/.boltz' >> ~/.bashrc
source ~/.bashrc
```

### Pre-download Models (Optional)

```bash
# First run will automatically download models (~2-3GB)
# To pre-download, run a test prediction:
boltz predict --help
```

### MSA Server Configuration (Optional)

If using a custom MSA server with authentication:

```bash
# Basic authentication
export BOLTZ_MSA_USERNAME=your_username
export BOLTZ_MSA_PASSWORD=your_password

# Or API key authentication
export MSA_API_KEY_VALUE=your_api_key
```

---

## Running Predictions

### Basic Prediction

1. **Create input YAML file** (`input.yaml`):
```yaml
version: 1
sequences:
  - protein:
      id: A
      sequence: MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL
```

2. **Run prediction**:
```bash
boltz predict input.yaml --use_msa_server --out_dir ./results
```

3. **Check outputs**:
```bash
ls -lh ./results/predictions/input/
```

### Command Options

```bash
# Standard prediction
boltz predict input.yaml \
    --use_msa_server \
    --devices 1 \
    --accelerator gpu \
    --out_dir ./results

# High-quality prediction (AlphaFold3 settings)
boltz predict input.yaml \
    --use_msa_server \
    --devices 1 \
    --accelerator gpu \
    --recycling_steps 10 \
    --diffusion_samples 25 \
    --out_dir ./results

# With inference-time potentials (better physical quality)
boltz predict input.yaml \
    --use_msa_server \
    --use_potentials \
    --devices 1 \
    --accelerator gpu \
    --out_dir ./results

# Multiple samples for diversity
boltz predict input.yaml \
    --use_msa_server \
    --diffusion_samples 5 \
    --devices 1 \
    --accelerator gpu \
    --out_dir ./results
```

### Batch Processing

```bash
# Process all YAML files in a directory
boltz predict ./input_directory/ \
    --use_msa_server \
    --devices 1 \
    --accelerator gpu \
    --out_dir ./batch_results
```

---

## Deployment Scenarios

### Scenario 1: Interactive Session

For quick predictions on a GPU workstation:

```bash
# SSH into GPU machine
ssh user@gpu-machine

# Activate environment
conda activate boltz

# Run prediction
boltz predict input.yaml --use_msa_server --out_dir ./results
```

### Scenario 2: Background Job

For long-running predictions:

```bash
# Using nohup
nohup boltz predict input.yaml \
    --use_msa_server \
    --out_dir ./results \
    > boltz.log 2>&1 &

# Check progress
tail -f boltz.log

# Using screen
screen -S boltz_session
boltz predict input.yaml --use_msa_server --out_dir ./results
# Press Ctrl+A, then D to detach
# Reattach with: screen -r boltz_session

# Using tmux
tmux new -s boltz_session
boltz predict input.yaml --use_msa_server --out_dir ./results
# Press Ctrl+B, then D to detach
# Reattach with: tmux attach -t boltz_session
```

### Scenario 3: SLURM Cluster

Create a SLURM job script (`boltz_job.sh`):

```bash
#!/bin/bash
#SBATCH --job-name=boltz_predict
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1
#SBATCH --mem=32G
#SBATCH --time=24:00:00
#SBATCH --output=boltz_%j.log
#SBATCH --error=boltz_%j.err

# Load required modules (adjust for your cluster)
module load cuda/11.8
module load python/3.10

# Activate environment
source /path/to/boltz_env/bin/activate

# Set cache directory (use scratch or fast storage)
export BOLTZ_CACHE=/scratch/$USER/.boltz

# Run prediction
boltz predict input.yaml \
    --use_msa_server \
    --devices 1 \
    --accelerator gpu \
    --out_dir ./results \
    --recycling_steps 3 \
    --diffusion_samples 5

echo "Job completed at $(date)"
```

Submit the job:
```bash
sbatch boltz_job.sh

# Check job status
squeue -u $USER

# View output
tail -f boltz_*.log
```

### Scenario 4: Docker Deployment

#### Create Dockerfile

```dockerfile
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip3 install --upgrade pip

# Install Boltz
RUN pip3 install boltz[cuda] -U

# Create workspace
WORKDIR /workspace

# Set cache directory
ENV BOLTZ_CACHE=/workspace/.boltz

# Entry point
ENTRYPOINT ["boltz"]
CMD ["--help"]
```

#### Build and Run

```bash
# Build Docker image
docker build -t boltz-gpu:latest .

# Run prediction
docker run --gpus all \
    -v $(pwd)/inputs:/workspace/inputs \
    -v $(pwd)/outputs:/workspace/outputs \
    -v $(pwd)/.boltz:/workspace/.boltz \
    boltz-gpu:latest \
    predict /workspace/inputs/input.yaml \
    --use_msa_server \
    --out_dir /workspace/outputs

# Interactive mode
docker run --gpus all -it \
    -v $(pwd):/workspace \
    boltz-gpu:latest \
    bash
```

### Scenario 5: Kubernetes Deployment

Create a Kubernetes job (`boltz-job.yaml`):

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: boltz-prediction
spec:
  template:
    spec:
      containers:
      - name: boltz
        image: boltz-gpu:latest
        command: ["boltz"]
        args:
          - "predict"
          - "/data/input.yaml"
          - "--use_msa_server"
          - "--out_dir"
          - "/data/results"
        resources:
          limits:
            nvidia.com/gpu: 1
            memory: "32Gi"
            cpu: "8"
        volumeMounts:
        - name: data-volume
          mountPath: /data
        - name: cache-volume
          mountPath: /workspace/.boltz
      restartPolicy: Never
      volumes:
      - name: data-volume
        persistentVolumeClaim:
          claimName: boltz-data-pvc
      - name: cache-volume
        persistentVolumeClaim:
          claimName: boltz-cache-pvc
  backoffLimit: 2
```

Deploy:
```bash
kubectl apply -f boltz-job.yaml
kubectl logs -f job/boltz-prediction
```

---

## Web API Deployment

Boltz includes a REST API that allows you to access predictions via HTTP endpoints from anywhere. This is ideal for:
- Remote access to GPU servers
- Integration with web applications
- Building prediction pipelines
- Multi-user environments

### Quick Start - API Deployment

#### Option 1: Docker Compose (Recommended)

1. **Deploy the API with GPU support**:
```bash
cd api
docker-compose up -d
```

2. **Verify the API is running**:
```bash
# Check health
curl http://localhost:8000/health

# View logs
docker-compose logs -f boltz-api
```

3. **Access interactive documentation**:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

#### Option 2: Local Development

1. **Install API dependencies**:
```bash
cd api
pip install -r requirements.txt
```

2. **Run the API server**:
```bash
python main.py
```

3. **API will be available at**: http://localhost:8000

### API Usage Examples

#### Submit a Prediction Job

```bash
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "sequences": [
      {
        "protein": {
          "id": "A",
          "sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL"
        }
      }
    ],
    "use_msa_server": true,
    "recycling_steps": 3,
    "diffusion_samples": 1
  }'
```

Response:
```json
{
  "job_id": "job_a1b2c3d4e5f6_1234567890",
  "status": "pending",
  "created_at": "2025-01-21T10:30:00"
}
```

#### Submit with YAML File

```bash
curl -X POST "http://localhost:8000/predict/yaml" \
  -F "yaml_file=@input.yaml" \
  -F "use_msa_server=true" \
  -F "diffusion_samples=5"
```

#### Check Job Status

```bash
curl "http://localhost:8000/jobs/job_a1b2c3d4e5f6_1234567890/status"
```

#### Get Results

```bash
curl "http://localhost:8000/jobs/job_a1b2c3d4e5f6_1234567890/result"
```

#### Download Structure File

```bash
curl "http://localhost:8000/jobs/job_a1b2c3d4e5f6_1234567890/download/output/predictions/input/input_model_0.cif" \
  -o structure.cif
```

#### List All Jobs

```bash
curl "http://localhost:8000/jobs?status_filter=completed&limit=10"
```

#### Delete a Job

```bash
curl -X DELETE "http://localhost:8000/jobs/job_a1b2c3d4e5f6_1234567890"
```

### Python Client Example

```python
import requests
import time

BASE_URL = "http://localhost:8000"

# Submit prediction
response = requests.post(
    f"{BASE_URL}/predict",
    json={
        "sequences": [
            {"protein": {"id": "A", "sequence": "MKTAYIAKQRQISFVKSHFSRQLE..."}}
        ],
        "use_msa_server": True,
        "diffusion_samples": 1,
    },
)
job_id = response.json()["job_id"]
print(f"Job submitted: {job_id}")

# Poll for completion
while True:
    status_response = requests.get(f"{BASE_URL}/jobs/{job_id}/status")
    status = status_response.json()["status"]
    print(f"Status: {status}")
    
    if status in ["completed", "failed"]:
        break
    time.sleep(10)

# Get results
if status == "completed":
    result = requests.get(f"{BASE_URL}/jobs/{job_id}/result").json()
    print(f"Confidence: {result['confidence_scores']['confidence_score']:.4f}")
    
    # Download structure
    structure_url = f"{BASE_URL}/jobs/{job_id}/download/{result['predictions'][0]}"
    with open("structure.cif", "wb") as f:
        f.write(requests.get(structure_url).content)
```

See `api/client_example.py` for a complete working example.

### API Configuration

Configure via environment variables:

```bash
# Set jobs directory
export BOLTZ_API_JOBS_DIR=/path/to/jobs

# Set max job retention (hours)
export BOLTZ_API_MAX_JOB_AGE_HOURS=72

# Set model cache directory
export BOLTZ_CACHE=/path/to/.boltz
```

### Production API Deployment

#### Using Docker with Custom Configuration

```bash
docker run -d \
  --name boltz-api \
  --gpus all \
  -p 8000:8000 \
  -v /data/boltz/jobs:/app/api_jobs \
  -v /data/boltz/cache:/app/.boltz \
  -e BOLTZ_API_JOBS_DIR=/app/api_jobs \
  -e BOLTZ_API_MAX_JOB_AGE_HOURS=48 \
  -e BOLTZ_CACHE=/app/.boltz \
  boltz-api:latest
```

#### Behind Nginx Reverse Proxy

Create `/etc/nginx/sites-available/boltz-api`:

```nginx
server {
    listen 80;
    server_name boltz-api.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Increase timeouts for long predictions
        proxy_read_timeout 3600s;
        proxy_connect_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

Enable and restart:
```bash
sudo ln -s /etc/nginx/sites-available/boltz-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### With SSL/HTTPS (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d boltz-api.yourdomain.com
```

#### Systemd Service (Non-Docker)

Create `/etc/systemd/system/boltz-api.service`:

```ini
[Unit]
Description=Boltz Structure Prediction API
After=network.target

[Service]
Type=simple
User=boltz
WorkingDirectory=/opt/boltz/api
Environment="BOLTZ_CACHE=/var/cache/boltz"
Environment="BOLTZ_API_JOBS_DIR=/var/lib/boltz/jobs"
ExecStart=/opt/boltz/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable boltz-api
sudo systemctl start boltz-api
sudo systemctl status boltz-api
```

### API Monitoring

#### Check API Health

```bash
# Basic health check
curl http://localhost:8000/health

# Monitor continuously
watch -n 5 'curl -s http://localhost:8000/health | jq'
```

#### View API Logs

```bash
# Docker logs
docker-compose logs -f boltz-api

# Systemd logs
sudo journalctl -u boltz-api -f
```

#### Monitor Job Queue

```bash
# List all jobs
curl http://localhost:8000/jobs | jq

# Count by status
curl http://localhost:8000/jobs | jq '.jobs | group_by(.status) | map({status: .[0].status, count: length})'
```

### API Security Considerations

For production deployments:

1. **Add Authentication**: Implement API key or OAuth2 authentication
2. **Rate Limiting**: Prevent abuse with rate limits
3. **CORS Configuration**: Restrict allowed origins in `api/main.py`
4. **Input Validation**: Already implemented via Pydantic models
5. **HTTPS Only**: Use SSL certificates for encrypted communication
6. **Firewall Rules**: Restrict access to trusted IPs if possible
7. **Job Cleanup**: Configure `BOLTZ_API_MAX_JOB_AGE_HOURS` appropriately
8. **Resource Limits**: Set Docker memory/CPU limits
9. **Monitoring**: Set up logging and alerting (e.g., Prometheus, Grafana)
10. **Backup**: Regular backups of job results if needed

### API Endpoints Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information |
| `/health` | GET | Health check |
| `/predict` | POST | Submit prediction (JSON) |
| `/predict/yaml` | POST | Submit prediction (YAML file) |
| `/jobs/{job_id}/status` | GET | Get job status |
| `/jobs/{job_id}/result` | GET | Get job results |
| `/jobs/{job_id}/download/{file_path}` | GET | Download output file |
| `/jobs` | GET | List all jobs |
| `/jobs/{job_id}` | DELETE | Delete a job |
| `/admin/cleanup` | POST | Clean up old jobs |

For complete API documentation, visit http://localhost:8000/docs after starting the API.

---

## Optimization

### GPU Memory Optimization

For limited VRAM:

```bash
# Reduce memory usage
boltz predict input.yaml \
    --use_msa_server \
    --devices 1 \
    --accelerator gpu \
    --diffusion_samples 1 \
    --max_parallel_samples 1 \
    --subsample_msa \
    --num_subsampled_msa 1024 \
    --out_dir ./results
```

### Multi-GPU Setup

```bash
# Use multiple GPUs for batch processing
boltz predict ./input_directory/ \
    --use_msa_server \
    --devices 4 \
    --accelerator gpu \
    --out_dir ./results
```

### Performance Monitoring

```bash
# Monitor GPU usage in real-time
watch -n 1 nvidia-smi

# Detailed monitoring
nvidia-smi dmon -i 0 -s pucvmet

# Log GPU metrics
nvidia-smi --query-gpu=timestamp,name,utilization.gpu,utilization.memory,memory.used,memory.total \
    --format=csv -l 5 > gpu_metrics.csv
```

### Pre-compute MSAs

For repeated predictions with the same proteins:

```bash
# Generate MSA once
boltz predict input.yaml --use_msa_server --out_dir ./results

# Reuse MSA from processed directory
# MSAs are cached in ./results/processed/
# Reference them in subsequent YAML files:
```

```yaml
sequences:
  - protein:
      id: A
      sequence: YOUR_SEQUENCE
      msa: ./results/processed/msa/YOUR_MSA.a3m
```

---

## Troubleshooting

### Issue 1: CUDA Out of Memory

**Error**: `RuntimeError: CUDA out of memory`

**Solutions**:
```bash
# Reduce batch size
boltz predict input.yaml \
    --use_msa_server \
    --max_parallel_samples 1 \
    --diffusion_samples 1

# Subsample MSA
boltz predict input.yaml \
    --use_msa_server \
    --subsample_msa \
    --num_subsampled_msa 512

# Use CPU as fallback
boltz predict input.yaml \
    --use_msa_server \
    --accelerator cpu
```

### Issue 2: Old GPU Architecture

**Error**: `cuEquivariance` related errors

**Solution**:
```bash
# Disable cuEquivariance kernels
boltz predict input.yaml \
    --use_msa_server \
    --no_kernels
```

### Issue 3: CUDA Not Detected

**Error**: `CUDA available: False`

**Solutions**:
```bash
# Check NVIDIA driver
nvidia-smi

# Reinstall PyTorch with CUDA
pip uninstall torch
pip install torch --index-url https://download.pytorch.org/whl/cu118

# Verify CUDA installation
python -c "import torch; print(torch.version.cuda)"
```

### Issue 4: MSA Server Timeout

**Error**: MSA generation fails or times out

**Solutions**:
```bash
# Use custom MSA server
boltz predict input.yaml \
    --use_msa_server \
    --msa_server_url https://your-msa-server.com

# Or provide pre-computed MSA
# Add to YAML:
# msa: ./path/to/precomputed.a3m
```

### Issue 5: Model Download Fails

**Error**: Failed to download model weights

**Solutions**:
```bash
# Check internet connection
ping huggingface.co

# Manually download and specify checkpoint
wget https://huggingface.co/boltz-community/boltz-2/resolve/main/boltz2_conf.ckpt
boltz predict input.yaml \
    --use_msa_server \
    --checkpoint ./boltz2_conf.ckpt

# Use different cache location
export BOLTZ_CACHE=/tmp/.boltz
```

### Issue 6: Permission Denied

**Error**: Cannot write to output directory

**Solutions**:
```bash
# Check permissions
ls -ld ./results

# Create directory with proper permissions
mkdir -p ./results
chmod 755 ./results

# Use absolute path
boltz predict input.yaml \
    --use_msa_server \
    --out_dir /absolute/path/to/results
```

---

## Monitoring and Logging

### Enable Verbose Logging

```bash
# Set logging level
export BOLTZ_LOG_LEVEL=DEBUG

# Run with verbose output
boltz predict input.yaml --use_msa_server 2>&1 | tee prediction.log
```

### Track Progress

```bash
# Monitor output directory
watch -n 5 'ls -lh ./results/predictions/'

# Check GPU utilization
watch -n 1 'nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used --format=csv'
```

### Performance Benchmarking

```bash
# Time prediction
time boltz predict input.yaml --use_msa_server --out_dir ./results

# Profile GPU usage
nsys profile -o boltz_profile \
    boltz predict input.yaml --use_msa_server --out_dir ./results
```

---

## Best Practices

1. **Use `--use_potentials`** for production predictions (better quality)
2. **Start with default settings** before optimizing
3. **Pre-download models** before batch processing
4. **Use scratch/fast storage** for cache on clusters
5. **Monitor GPU memory** during first runs
6. **Keep logs** for debugging and reproducibility
7. **Version control** input YAML files
8. **Backup predictions** regularly
9. **Test with small proteins** before large complexes
10. **Use `--override`** flag when re-running with different parameters

---

## Quick Reference

### Common Commands

```bash
# Basic prediction
boltz predict input.yaml --use_msa_server

# High quality
boltz predict input.yaml --use_msa_server --use_potentials --recycling_steps 10 --diffusion_samples 25

# Memory efficient
boltz predict input.yaml --use_msa_server --max_parallel_samples 1 --subsample_msa

# Batch processing
boltz predict ./inputs/ --use_msa_server --out_dir ./outputs

# Multi-GPU
boltz predict input.yaml --use_msa_server --devices 4

# CPU fallback
boltz predict input.yaml --use_msa_server --accelerator cpu
```

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--devices` | 1 | Number of GPUs |
| `--accelerator` | gpu | Hardware type |
| `--recycling_steps` | 3 | Recycling iterations |
| `--sampling_steps` | 200 | Diffusion steps |
| `--diffusion_samples` | 1 | Number of samples |
| `--use_potentials` | False | Use inference potentials |
| `--max_parallel_samples` | 5 | Parallel samples |
| `--subsample_msa` | False | Reduce MSA size |
| `--no_kernels` | False | Disable cuEquivariance |

---

## Support and Resources

- **Documentation**: [docs/prediction.md](docs/prediction.md)
- **GitHub Issues**: https://github.com/jwohlwend/boltz/issues
- **Slack Community**: https://boltz.bio/join-slack
- **Papers**: 
  - Boltz-1: https://doi.org/10.1101/2024.11.19.624167
  - Boltz-2: https://doi.org/10.1101/2025.06.14.659707

---

## Changelog

- **v1.0** (2025-01-21): Initial deployment guide
- Add your deployment notes and customizations here

---

**Last Updated**: 2025-01-21
