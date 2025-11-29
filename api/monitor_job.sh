#!/bin/bash
# Monitor a Boltz prediction job

if [ -z "$1" ]; then
    echo "Usage: $0 <job_id>"
    echo "Example: $0 job_1da4aa190089_1763932270"
    exit 1
fi

JOB_ID=$1
API_URL="http://136.117.112.142:8001"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Monitoring Job: $JOB_ID"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

while true; do
    # Get job status
    response=$(curl -s "$API_URL/jobs/$JOB_ID/status")
    status=$(echo "$response" | jq -r '.status')
    
    # Clear previous line
    echo -ne "\r\033[K"
    
    if [ "$status" = "pending" ]; then
        echo -ne "⏳ Status: PENDING - Waiting to start..."
    elif [ "$status" = "running" ]; then
        echo -ne "⚡ Status: RUNNING - Prediction in progress..."
    elif [ "$status" = "completed" ]; then
        echo -e "\n"
        echo "✅ Status: COMPLETED!"
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "📊 Results:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        curl -s "$API_URL/jobs/$JOB_ID/result" | jq
        echo ""
        echo "📥 Download results:"
        echo "   curl -O \"$API_URL/jobs/$JOB_ID/download/<filename>\""
        echo ""
        break
    elif [ "$status" = "failed" ]; then
        echo -e "\n"
        echo "❌ Status: FAILED"
        echo ""
        error=$(echo "$response" | jq -r '.error')
        echo "Error: $error"
        echo ""
        break
    else
        echo -ne "❓ Status: $status"
    fi
    
    sleep 5
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
