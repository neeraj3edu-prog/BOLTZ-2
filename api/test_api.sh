#!/bin/bash
# Test script for Boltz API

API_URL="http://localhost:8000"

echo "🧪 Testing Boltz API..."
echo ""

# Test 1: Health check
echo "1️⃣  Health Check:"
curl -s "$API_URL/health" | jq
echo ""

# Test 2: Submit a simple prediction
echo "2️⃣  Submitting prediction job..."
RESPONSE=$(curl -s -X POST "$API_URL/predict" \
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
  }')

echo "$RESPONSE" | jq
JOB_ID=$(echo "$RESPONSE" | jq -r '.job_id')
echo ""

# Test 3: Monitor job status
echo "3️⃣  Monitoring job: $JOB_ID"
echo "   (This may take several minutes...)"
echo ""

MAX_CHECKS=60
CHECK_COUNT=0

while [ $CHECK_COUNT -lt $MAX_CHECKS ]; do
    STATUS_RESPONSE=$(curl -s "$API_URL/jobs/$JOB_ID/status")
    STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')
    
    echo "   [$(date +%H:%M:%S)] Status: $STATUS"
    
    if [ "$STATUS" = "completed" ]; then
        echo ""
        echo "✅ Job completed successfully!"
        echo ""
        echo "4️⃣  Results:"
        curl -s "$API_URL/jobs/$JOB_ID/result" | jq
        exit 0
    elif [ "$STATUS" = "failed" ]; then
        echo ""
        echo "❌ Job failed!"
        echo ""
        echo "Error details:"
        echo "$STATUS_RESPONSE" | jq
        exit 1
    fi
    
    sleep 10
    CHECK_COUNT=$((CHECK_COUNT + 1))
done

echo ""
echo "⏱️  Timeout: Job still running after $(($MAX_CHECKS * 10)) seconds"
echo "   Check status manually with:"
echo "   curl $API_URL/jobs/$JOB_ID/status"
