#!/bin/bash
set -e

# Lists all deployed resources for the AI Explorer project

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID=${PROJECT_ID}
REGION=${REGION:-"us-central1"}
APP_NAME=${APP_NAME:-"ai-explorer"}

echo -e "${BLUE}📋 AI Explorer - Resource Listing${NC}"
echo -e "${YELLOW}Project: $PROJECT_ID${NC}"
echo -e "${YELLOW}Region: $REGION${NC}"
echo ""

# Validate required variables
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Error: PROJECT_ID environment variable is required${NC}"
    echo "Set it with: export PROJECT_ID=your-gcp-project-id"
    exit 1
fi

# Set GCP project
gcloud config set project $PROJECT_ID >/dev/null 2>&1

# Function to list resources with error handling
list_resources() {
    local resource_type="$1"
    local command="$2"
    local filter="$3"
    
    echo -e "${GREEN}📦 $resource_type:${NC}"
    if [ ! -z "$filter" ]; then
        command="$command --filter=\"$filter\""
    fi
    
    if eval "$command" 2>/dev/null; then
        echo ""
    else
        echo -e "${YELLOW}  ⚠️  No $resource_type found or access denied${NC}"
        echo ""
    fi
}

# List Cloud Run Services
list_resources "Cloud Run Services" \
    "gcloud run services list --platform=managed --region=$REGION --format='table(metadata.name,status.url,spec.template.spec.containers[0].image)'" \
    "metadata.name~.*$APP_NAME.*"

# List Cloud SQL Instances
list_resources "Cloud SQL Instances" \
    "gcloud sql instances list --format='table(name,database_version,region,settings.tier,state)'" \
    "name~.*$APP_NAME.*"

# List Redis Instances
list_resources "Redis Instances" \
    "gcloud redis instances list --region=$REGION --format='table(name,version,tier,memorySizeGb,state)'" \
    "name~.*$APP_NAME.*"

# List VPC Networks
list_resources "VPC Networks" \
    "gcloud compute networks list --format='table(name,subnet_mode,bgp_routing_mode.regional_dynamic_routing)'" \
    "name~.*$APP_NAME.*"

# List Subnets
list_resources "VPC Subnets" \
    "gcloud compute networks subnets list --format='table(name,region,network.basename(),range)'" \
    "name~.*$APP_NAME.*"

# List VPC Access Connectors
list_resources "VPC Access Connectors" \
    "gcloud compute networks vpc-access connectors list --region=$REGION --format='table(name,region,network,state)'" \
    "name~.*$APP_NAME.*"

# List Load Balancer Components
echo -e "${GREEN}🌐 Load Balancer Components:${NC}"
echo -e "${YELLOW}Global Addresses:${NC}"
gcloud compute addresses list --global --filter="name~.*$APP_NAME.*" --format='table(name,address,status)' 2>/dev/null || echo "  No global addresses found"

echo -e "${YELLOW}Backend Services:${NC}"
gcloud compute backend-services list --global --filter="name~.*$APP_NAME.*" --format='table(name,protocol,backends[].group.basename())' 2>/dev/null || echo "  No backend services found"

echo -e "${YELLOW}URL Maps:${NC}"
gcloud compute url-maps list --filter="name~.*$APP_NAME.*" --format='table(name,defaultService.basename())' 2>/dev/null || echo "  No URL maps found"

echo -e "${YELLOW}SSL Certificates:${NC}"
gcloud compute ssl-certificates list --filter="name~.*$APP_NAME.*" --format='table(name,type,managed.status)' 2>/dev/null || echo "  No SSL certificates found"
echo ""

# List Service Accounts
list_resources "Service Accounts" \
    "gcloud iam service-accounts list --format='table(email,displayName,disabled)'" \
    "email~.*$APP_NAME.*"

# List Artifact Registry Repositories
list_resources "Artifact Registry Repositories" \
    "gcloud artifacts repositories list --format='table(name,format,description)'" \
    "name~.*$APP_NAME.*"

# List Secret Manager Secrets
list_resources "Secret Manager Secrets" \
    "gcloud secrets list --format='table(name,created)'" \
    "name~.*$APP_NAME.*"

# List Firewall Rules
list_resources "Firewall Rules" \
    "gcloud compute firewall-rules list --format='table(name,direction,priority,sourceRanges.list():label=SRC_RANGES,allowed[].map().firewall_rule().list():label=ALLOW)'" \
    "name~.*$APP_NAME.*"

# Show Terraform State (if available)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../../terraform"
if [ -f "$TERRAFORM_DIR/.terraform/terraform.tfstate" ] || [ -f "$TERRAFORM_DIR/terraform.tfstate" ]; then
    echo -e "${GREEN}🏗️ Terraform Resources:${NC}"
    cd "$TERRAFORM_DIR"
    
    # Initialize terraform if needed for show command
    if [ ! -d ".terraform" ]; then
        echo -e "${YELLOW}  Initializing Terraform...${NC}"
        terraform init >/dev/null 2>&1
    fi
    
    if terraform show -json 2>/dev/null | jq -r '.values.root_module.resources[]? | select(.type != null) | "\(.type).\(.name)"' 2>/dev/null; then
        echo ""
    else
        echo "  Terraform state not accessible or empty"
        echo ""
    fi
else
    echo -e "${GREEN}🏗️ Terraform Resources:${NC}"
    echo "  Terraform state not found"
    echo ""
fi

echo -e "${BLUE}✅ Resource listing completed${NC}"
echo ""
echo -e "${YELLOW}💡 To get more details about specific resources:${NC}"
echo "  gcloud run services describe <service-name> --region=$REGION"
echo "  gcloud sql instances describe <instance-name>"
echo "  gcloud redis instances describe <instance-name> --region=$REGION"
echo "  cd terraform && terraform output"