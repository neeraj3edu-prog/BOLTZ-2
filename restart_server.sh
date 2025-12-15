#!/bin/bash
# Script to restart the Boltz API server

echo "🔄 Restarting Boltz API server..."

# Make sure we're using the correct account
gcloud config set account neeraj3shop@gmail.com

# Restart the container
gcloud compute ssh instance-20251125-143144 \
  --zone=us-east4-c \
  --project=ml-project-479314 \
  --command "docker restart boltz-api"

echo ""
echo "⏳ Waiting for server to start..."
sleep 10

echo ""
echo "🔍 Checking server status..."
gcloud compute ssh instance-20251125-143144 \
  --zone=us-east4-c \
  --project=ml-project-479314 \
  --command "docker ps | grep boltz-api"

echo ""
echo "🏥 Testing health endpoint..."
curl -s http://35.236.240.79:8001/health | python3 -m json.tool

echo ""
echo "✅ Server restart complete!"
