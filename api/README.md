# Boltz API

FastAPI-based REST API for protein structure and protein-ligand binding predictions using Boltz.

## 🚀 Quick Start

### Deploy to Google Cloud

```bash
./deploy_new_server.sh
```

### Test the API

```bash
# Health check
curl http://YOUR_SERVER_IP:8001/health

# GPU status
curl http://YOUR_SERVER_IP:8001/gpu/status

# Run protein-ligand prediction
curl -X POST "http://YOUR_SERVER_IP:8001/protein-ligand-binding-sync" \
  -H "Content-Type: application/json" \
  -d '{"ligand_smiles": "YOUR_SMILES_STRING"}'
```

---

## 📚 Documentation

**Complete documentation is available in [`../docs/api/`](../docs/api/)**

- **[API Guide](../docs/api/API_GUIDE.md)** - Complete API usage guide
- **[Deployment Guide](../docs/api/DEPLOYMENT.md)** - Deployment instructions
- **[Architecture](../docs/api/ARCHITECTURE.md)** - Technical architecture

---

## ✨ Key Features

- 🎯 **Protein-Ligand Binding** - Predict binding affinity (IC50, Kd, ΔG) with confidence scores
- 🔄 **Automatic Replicates** - Runs 3 predictions for statistical confidence
- ⚡ **Intelligent Caching** - Instant results for repeat ligands
- 🚀 **GPU Accelerated** - Fast predictions with NVIDIA GPUs
- 📊 **Comprehensive Metrics** - Affinity, confidence, and quality scores
- 🌐 **RESTful API** - Easy integration with any frontend
- 📁 **Secure File Serving** - Download structure files (CIF format)
- 🧹 **Auto-cleanup** - Automatic removal of old jobs (72 hours)

---

## 🔧 Core Files

| File | Description |
|------|-------------|
| `main.py` | FastAPI application |
| `Dockerfile` | Docker configuration |
| `deploy_new_server.sh` | Automated deployment script |
| `manage_api.sh` | API management utilities |
| `test_api.sh` | API testing script |
| `check_gpu_availability.sh` | Check GPU availability |
| `monitor_job.sh` | Monitor job progress |
| `requirements.txt` | Python dependencies |

---

## 📊 API Endpoints

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | API health status |
| `/gpu/status` | GET | GPU availability |
| `/protein-ligand-binding-sync` | POST | Protein-ligand prediction (recommended) |
| `/predict` | POST | General structure prediction |
| `/jobs/{job_id}/status` | GET | Job status |
| `/jobs/{job_id}/result` | GET | Job results with metrics |
| `/jobs/{job_id}/download/{file_path}` | GET | Download files |
| `/cache/status` | GET | Cache statistics |

### Admin Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/rescan` | POST | Re-scan job directories |
| `/admin/cleanup` | POST | Clean up old jobs |

**Interactive Documentation**: `http://YOUR_SERVER_IP:8001/docs`

---

## 🛠️ Local Development

### Using Docker

```bash
# Build image
docker build -t boltz-api .

# Run container
docker run -d \
  --name boltz-api \
  --gpus all \
  --shm-size=8g \
  -p 8001:8000 \
  -v $(pwd)/api_jobs:/app/api_jobs \
  boltz-api

# View logs
docker logs -f boltz-api
```

### Without Docker

```bash
# Install dependencies
pip install -r requirements.txt
pip install boltz[cuda] -U

# Run API
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 📦 Requirements

- **Python**: 3.10+
- **GPU**: NVIDIA GPU with CUDA support (recommended)
- **Docker**: For containerized deployment
- **Google Cloud SDK**: For cloud deployment

---

## 🔍 Monitoring

### Check API Status

```bash
# Health check
curl http://localhost:8001/health

# GPU status
curl http://localhost:8001/gpu/status

# Cache status
curl http://localhost:8001/cache/status
```

### View Logs

```bash
# Docker logs
docker logs -f boltz-api

# Last 100 lines
docker logs boltz-api --tail 100
```

### Monitor Jobs

```bash
# Monitor specific job
./monitor_job.sh JOB_ID

# Check all jobs
curl http://localhost:8001/jobs
```

---

## 🚨 Troubleshooting

### API Not Starting

```bash
# Check logs
docker logs boltz-api

# Restart container
docker restart boltz-api
```

### GPU Not Detected

```bash
# Check GPU
nvidia-smi

# Test Docker GPU access
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### Empty Predictions

```bash
# Re-scan jobs
curl -X POST http://localhost:8001/admin/rescan
```

For more troubleshooting, see [DEPLOYMENT.md](../docs/api/DEPLOYMENT.md#troubleshooting).

---

## 📖 Learn More

- **[Complete API Guide](../docs/api/API_GUIDE.md)** - Detailed usage instructions
- **[Deployment Guide](../docs/api/DEPLOYMENT.md)** - Step-by-step deployment
- **[Architecture](../docs/api/ARCHITECTURE.md)** - Technical details

---

## 📞 Support

```bash
# Check logs
docker logs boltz-api --tail 100

# Check GPU
curl http://localhost:8001/gpu/status

# Re-scan jobs
curl -X POST http://localhost:8001/admin/rescan

# Restart API
docker restart boltz-api
```
