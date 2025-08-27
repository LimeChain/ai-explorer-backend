#!/bin/bash
set -e

# Simple script to setup Terraform remote state backend

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID=${PROJECT_ID}
REGION=${REGION:-"us-central1"}
STATE_BUCKET_NAME="ai-explorer-terraform-state"

echo -e "${GREEN}🪣 Setting up Terraform remote state backend${NC}"
echo "  Project: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Bucket: gs://$STATE_BUCKET_NAME"
echo ""

# Validate required variables
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Error: PROJECT_ID environment variable is required${NC}"
    exit 1
fi

# Set GCP project
gcloud config set project $PROJECT_ID

# Check if bucket already exists
if gsutil ls -b gs://$STATE_BUCKET_NAME &>/dev/null; then
    echo -e "${GREEN}✅ Terraform state bucket already exists${NC}"
else
    echo -e "${YELLOW}📦 Creating Terraform state bucket...${NC}"
    
    # Create the bucket
    gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$STATE_BUCKET_NAME
    
    # Enable versioning
    gsutil versioning set on gs://$STATE_BUCKET_NAME
    
    # Set lifecycle policy (keep last 10 versions)
    cat > /tmp/lifecycle.json << EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {
          "numNewerVersions": 10
        }
      }
    ]
  }
}
EOF
    
    gsutil lifecycle set /tmp/lifecycle.json gs://$STATE_BUCKET_NAME
    rm -f /tmp/lifecycle.json
    
    echo -e "${GREEN}✅ Created Terraform state bucket${NC}"
fi

# Set bucket permissions
CURRENT_USER=$(gcloud config get-value account)
if [ ! -z "$CURRENT_USER" ]; then
    gsutil iam ch user:$CURRENT_USER:objectAdmin gs://$STATE_BUCKET_NAME >/dev/null 2>&1 || true
    echo -e "${GREEN}✅ Granted storage permissions${NC}"
fi

echo -e "${GREEN}🎉 Terraform backend setup completed!${NC}"