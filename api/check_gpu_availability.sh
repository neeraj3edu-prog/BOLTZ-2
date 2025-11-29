#!/bin/bash
# Check GPU availability, quota, and pricing across all regions
# Helps you decide which GPU to use for Boltz API

PROJECT_ID="ml-project-477222"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🔍 GPU Availability Checker${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Set project
gcloud config set project $PROJECT_ID --quiet

echo -e "${CYAN}📊 Checking your GPU quotas...${NC}"
echo ""

# Function to check quota for a specific GPU type in a region
check_quota() {
    local region=$1
    local gpu_metric=$2
    
    quota_info=$(gcloud compute regions describe $region \
        --project=$PROJECT_ID \
        --format="json" 2>/dev/null | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    quotas = data.get('quotas', [])
    for q in quotas:
        if q['metric'] == '$gpu_metric':
            print(f\"{q.get('limit', 0)}|{q.get('usage', 0)}\")
            break
    else:
        print('0|0')
except:
    print('0|0')
" 2>/dev/null)
    
    echo "$quota_info"
}

# Function to check if GPU type is available in zone
check_gpu_in_zone() {
    local zone=$1
    local gpu_type=$2
    
    available=$(gcloud compute accelerator-types list \
        --filter="zone:$zone AND name:$gpu_type" \
        --format="value(name)" 2>/dev/null | head -1)
    
    if [ -n "$available" ]; then
        echo "✓"
    else
        echo "✗"
    fi
}

# GPU definitions: name|vram|speed_multiplier|cost_per_hour|quota_metric|gcloud_type
declare -a GPUS=(
    "T4|16GB|0.8x|0.35|NVIDIA_T4_GPUS|nvidia-tesla-t4"
    "P100|16GB|0.9x|1.46|NVIDIA_P100_GPUS|nvidia-tesla-p100"
    "V100|16GB|1.5x|2.48|NVIDIA_V100_GPUS|nvidia-tesla-v100"
    "L4|23GB|1.0x|0.60|NVIDIA_L4_GPUS|nvidia-l4"
    "A100-40GB|40GB|2.0x|3.67|NVIDIA_A100_GPUS|nvidia-tesla-a100"
    "A100-80GB|80GB|2.0x|4.50|NVIDIA_A100_80GB_GPUS|nvidia-a100-80gb"
    "H100|80GB|3.0x|4.50|NVIDIA_H100_80GB_GPUS|nvidia-h100-80gb"
    "H200|141GB|3.5x|6.00|NVIDIA_H200_141GB_GPUS|nvidia-h200-141gb"
)

# Regions to check
declare -a REGIONS=("us-west1" "us-central1" "us-east1" "us-east4" "europe-west1" "asia-southeast1")

echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════════════════${NC}"
printf "${YELLOW}%-12s %-8s %-6s %-8s %-15s %-10s${NC}\n" "GPU" "VRAM" "Speed" "Cost/hr" "Your Quota" "Status"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════════════════${NC}"

for gpu_info in "${GPUS[@]}"; do
    IFS='|' read -r name vram speed cost quota_metric gcloud_type <<< "$gpu_info"
    
    # Check quota in us-west1 (primary region)
    quota_data=$(check_quota "us-west1" "$quota_metric")
    IFS='|' read -r limit usage <<< "$quota_data"
    
    # Determine status
    if (( $(echo "$limit > 0" | bc -l) )); then
        available=$((limit - usage))
        if (( $(echo "$available > 0" | bc -l) )); then
            status="${GREEN}✅ Available${NC}"
            quota_display="${GREEN}${limit} (${available} free)${NC}"
        else
            status="${YELLOW}⚠️  In use${NC}"
            quota_display="${YELLOW}${limit} (all used)${NC}"
        fi
    else
        status="${RED}❌ Need quota${NC}"
        quota_display="${RED}0 (request needed)${NC}"
    fi
    
    printf "%-12s %-8s %-6s ${CYAN}\$%-7s${NC} %-25s %b\n" \
        "$name" "$vram" "$speed" "$cost" "$quota_display" "$status"
done

echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo ""

# Show detailed availability by zone
echo -e "${CYAN}🌍 GPU Availability by Zone (us-west1):${NC}"
echo ""
echo -e "${YELLOW}─────────────────────────────────────────────────────────────${NC}"
printf "${YELLOW}%-12s %-12s %-12s %-12s${NC}\n" "GPU" "Zone A" "Zone B" "Zone C"
echo -e "${YELLOW}─────────────────────────────────────────────────────────────${NC}"

for gpu_info in "${GPUS[@]}"; do
    IFS='|' read -r name vram speed cost quota_metric gcloud_type <<< "$gpu_info"
    
    zone_a=$(check_gpu_in_zone "us-west1-a" "$gcloud_type")
    zone_b=$(check_gpu_in_zone "us-west1-b" "$gcloud_type")
    zone_c=$(check_gpu_in_zone "us-west1-c" "$gcloud_type")
    
    # Color code the availability
    [ "$zone_a" = "✓" ] && zone_a="${GREEN}✓${NC}" || zone_a="${RED}✗${NC}"
    [ "$zone_b" = "✓" ] && zone_b="${GREEN}✓${NC}" || zone_b="${RED}✗${NC}"
    [ "$zone_c" = "✓" ] && zone_c="${GREEN}✓${NC}" || zone_c="${RED}✗${NC}"
    
    printf "%-12s %b            %b            %b\n" "$name" "$zone_a" "$zone_b" "$zone_c"
done

echo -e "${YELLOW}─────────────────────────────────────────────────────────────${NC}"
echo ""

# Recommendations
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}💡 Recommendations${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Find GPUs with available quota
echo -e "${GREEN}✅ Ready to Use (No approval needed):${NC}"
has_available=false
for gpu_info in "${GPUS[@]}"; do
    IFS='|' read -r name vram speed cost quota_metric gcloud_type <<< "$gpu_info"
    quota_data=$(check_quota "us-west1" "$quota_metric")
    IFS='|' read -r limit usage <<< "$quota_data"
    
    if (( $(echo "$limit > $usage" | bc -l) )); then
        available=$((limit - usage))
        echo -e "   • ${GREEN}$name${NC} ($vram VRAM, $speed speed, \$$cost/hr) - ${available} available"
        has_available=true
    fi
done

if [ "$has_available" = false ]; then
    echo -e "   ${YELLOW}None - all quotas are 0 or in use${NC}"
fi

echo ""
echo -e "${YELLOW}⏳ Need Quota Request (1-2 days approval):${NC}"
for gpu_info in "${GPUS[@]}"; do
    IFS='|' read -r name vram speed cost quota_metric gcloud_type <<< "$gpu_info"
    quota_data=$(check_quota "us-west1" "$quota_metric")
    IFS='|' read -r limit usage <<< "$quota_data"
    
    if (( $(echo "$limit == 0" | bc -l) )); then
        echo -e "   • ${YELLOW}$name${NC} ($vram VRAM, $speed speed, \$$cost/hr)"
    fi
done

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🎯 Best Options for Boltz API${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check specific recommendations
v100_quota=$(check_quota "us-west1" "NVIDIA_V100_GPUS")
IFS='|' read -r v100_limit v100_usage <<< "$v100_quota"

t4_quota=$(check_quota "us-west1" "NVIDIA_T4_GPUS")
IFS='|' read -r t4_limit t4_usage <<< "$t4_quota"

a100_quota=$(check_quota "us-west1" "NVIDIA_A100_GPUS")
IFS='|' read -r a100_limit a100_usage <<< "$a100_quota"

if (( $(echo "$v100_limit > $v100_usage" | bc -l) )); then
    echo -e "${GREEN}⭐ RECOMMENDED: V100${NC}"
    echo -e "   • Available NOW (no approval needed)"
    echo -e "   • 16GB VRAM (enough for Boltz)"
    echo -e "   • 1.5x faster than L4"
    echo -e "   • \$2.48/hour"
    echo -e "   • Run: ${CYAN}./create_available_gpu_vm.sh${NC} and select option 1"
    echo ""
fi

if (( $(echo "$t4_limit > $t4_usage" | bc -l) )); then
    echo -e "${GREEN}💰 BUDGET OPTION: T4${NC}"
    echo -e "   • Available NOW (no approval needed)"
    echo -e "   • 16GB VRAM (enough for Boltz)"
    echo -e "   • Similar speed to L4"
    echo -e "   • \$0.35/hour (cheapest!)"
    echo -e "   • Run: ${CYAN}./create_available_gpu_vm.sh${NC} and select option 2"
    echo ""
fi

if (( $(echo "$a100_limit == 0" | bc -l) )); then
    echo -e "${YELLOW}🚀 BEST PERFORMANCE: A100 40GB${NC}"
    echo -e "   • Need to request quota (1-2 days)"
    echo -e "   • 40GB VRAM (both apps + headroom)"
    echo -e "   • 2x faster than L4"
    echo -e "   • \$3.67/hour"
    echo -e "   • Request at: ${CYAN}https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID${NC}"
    echo ""
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}📋 Quick Actions:${NC}"
echo ""
echo -e "  ${GREEN}Use available GPU now:${NC}"
echo -e "    ./create_available_gpu_vm.sh"
echo ""
echo -e "  ${YELLOW}Request quota for better GPU:${NC}"
echo -e "    https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID"
echo ""
echo -e "  ${CYAN}Check current deployments:${NC}"
echo -e "    gcloud compute instances list --project=$PROJECT_ID"
echo ""
