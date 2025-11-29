#!/bin/bash

# Deployment script for new Boltz API server
# New server: instance-20251125-143144 (us-east4-c, ml-project-479314)
# Old server: rsgpt-server-l4 (us-west1-a, ml-project-477222)

set -e

echo "=========================================="
echo "Boltz API Migration to New Server"
echo "=========================================="
echo ""

NEW_SERVER="instance-20251125-143144"
NEW_ZONE="us-east4-c"
NEW_PROJECT="ml-project-479314"

OLD_SERVER="rsgpt-server-l4"
OLD_ZONE="us-west1-a"
OLD_PROJECT="ml-project-477222"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Step 1: Checking new server...${NC}"
gcloud compute ssh $NEW_SERVER --zone=$NEW_ZONE --project=$NEW_PROJECT --command='echo "✓ New server accessible"'

echo ""
echo -e "${YELLOW}Step 2: Installing Docker on new server...${NC}"
gcloud compute ssh $NEW_SERVER --zone=$NEW_ZONE --project=$NEW_PROJECT --command='
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        echo "Installing Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker $USER
        rm get-docker.sh
        echo "✓ Docker installed"
    else
        echo "✓ Docker already installed"
    fi
    
    # Install NVIDIA Docker runtime
    if ! docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
        echo "Installing NVIDIA Docker runtime..."
        distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
        curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
        curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
        sudo apt-get update
        sudo apt-get install -y nvidia-docker2
        sudo systemctl restart docker
        echo "✓ NVIDIA Docker runtime installed"
    else
        echo "✓ NVIDIA Docker runtime already configured"
    fi
'

echo ""
echo -e "${YELLOW}Step 3: Creating directories on new server...${NC}"
gcloud compute ssh $NEW_SERVER --zone=$NEW_ZONE --project=$NEW_PROJECT --command='
    mkdir -p ~/boltz/api
    mkdir -p ~/boltz/api/api_jobs
    mkdir -p ~/boltz/templates
    mkdir -p ~/.boltz
    echo "✓ Directories created"
'

echo ""
echo -e "${YELLOW}Step 4: Copying files to new server...${NC}"
echo "Copying main.py..."
gcloud compute scp main.py $NEW_SERVER:~/boltz/api/main.py --zone=$NEW_ZONE --project=$NEW_PROJECT

echo "Copying Dockerfile..."
gcloud compute scp Dockerfile $NEW_SERVER:~/boltz/Dockerfile --zone=$NEW_ZONE --project=$NEW_PROJECT

echo "Copying template (if exists)..."
if [ -f "../templates/ligand_free_processed.cif" ]; then
    gcloud compute scp ../templates/ligand_free_processed.cif $NEW_SERVER:~/boltz/templates/ --zone=$NEW_ZONE --project=$NEW_PROJECT
    echo "✓ Template copied"
else
    echo "⚠ Template not found locally, will need to copy from old server"
fi

echo ""
echo -e "${YELLOW}Step 5: Copying template from old server (if needed)...${NC}"
gcloud compute ssh $OLD_SERVER --zone=$OLD_ZONE --project=$OLD_PROJECT --command='
    if [ -f ~/boltz/templates/ligand_free_processed.cif ]; then
        cat ~/boltz/templates/ligand_free_processed.cif
    fi
' > /tmp/template.cif 2>/dev/null || true

if [ -s /tmp/template.cif ]; then
    gcloud compute scp /tmp/template.cif $NEW_SERVER:~/boltz/templates/ligand_free_processed.cif --zone=$NEW_ZONE --project=$NEW_PROJECT
    rm /tmp/template.cif
    echo "✓ Template copied from old server"
fi

echo ""
echo -e "${YELLOW}Step 6: Building Docker image on new server...${NC}"
gcloud compute ssh $NEW_SERVER --zone=$NEW_ZONE --project=$NEW_PROJECT --command='
    cd ~/boltz
    docker build -t api-boltz-api -f Dockerfile .
    echo "✓ Docker image built"
'

echo ""
echo -e "${YELLOW}Step 7: Starting Boltz API on new server...${NC}"
gcloud compute ssh $NEW_SERVER --zone=$NEW_ZONE --project=$NEW_PROJECT --command='
    # Stop existing container if running
    docker stop boltz-api 2>/dev/null || true
    docker rm boltz-api 2>/dev/null || true
    
    # Run new container
    docker run -d \
      --name boltz-api \
      --gpus all \
      --shm-size=8g \
      -p 8001:8000 \
      -v ~/boltz/api/api_jobs:/app/api_jobs \
      -v ~/boltz/templates:/app/templates \
      -v ~/.boltz:/app/.boltz \
      --restart unless-stopped \
      api-boltz-api
    
    echo "✓ Boltz API started"
    echo ""
    echo "Waiting for API to be ready..."
    sleep 10
'

echo ""
echo -e "${YELLOW}Step 8: Checking new server status...${NC}"
NEW_IP=$(gcloud compute instances describe $NEW_SERVER --zone=$NEW_ZONE --project=$NEW_PROJECT --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
echo "New server IP: $NEW_IP"

gcloud compute ssh $NEW_SERVER --zone=$NEW_ZONE --project=$NEW_PROJECT --command='
    echo "Docker containers:"
    docker ps
    echo ""
    echo "GPU status:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv
    echo ""
    echo "API health check:"
    sleep 5
    curl -s http://localhost:8001/health | python3 -m json.tool || echo "API not ready yet"
'

echo ""
echo -e "${GREEN}=========================================="
echo "New server deployment complete!"
echo "==========================================${NC}"
echo ""
echo "New server details:"
echo "  Server: $NEW_SERVER"
echo "  Zone: $NEW_ZONE"
echo "  Project: $NEW_PROJECT"
echo "  IP: $NEW_IP"
echo "  API URL: http://$NEW_IP:8001"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Test the new API: curl http://$NEW_IP:8001/health"
echo "2. Update your frontend to use new IP: $NEW_IP"
echo "3. Run: ./stop_old_server.sh to stop the old server"
echo ""
