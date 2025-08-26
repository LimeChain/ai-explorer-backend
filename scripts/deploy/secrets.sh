#!/bin/bash
set -e

# This script helps set up secrets in Google Cloud Secret Manager

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID=${PROJECT_ID}
APP_NAME=${APP_NAME:-"ai-explorer"}

echo -e "${GREEN}🔐 Setting up secrets in Google Cloud Secret Manager${NC}"

# Validate required environment variables
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Error: PROJECT_ID environment variable is required${NC}"
    echo "Set it with: export PROJECT_ID=your-gcp-project-id"
    exit 1
fi

echo -e "${YELLOW}📋 Configuration:${NC}"
echo "  Project ID: $PROJECT_ID"
echo "  App Name: $APP_NAME"
echo ""

# Set the project
gcloud config set project $PROJECT_ID

# Function to create or update secret
create_or_update_secret() {
    local secret_name=$1
    local description=$2
    local prompt_message=$3
    
    echo -e "${YELLOW}🔑 Setting up secret: $secret_name${NC}"
    
    # Check if secret already exists
    if gcloud secrets describe $secret_name &>/dev/null; then
        echo "  Secret $secret_name already exists"
        read -p "  Update existing secret? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "  Skipping $secret_name"
            return
        fi
    fi
    
    echo "  $prompt_message"
    echo "  (Paste your key and press Enter. Leading/trailing whitespace will be automatically trimmed.)"
    read -s secret_value
    echo
    
    # Trim whitespace from the input (read already handles newlines by stopping at the first one)
    secret_value=$(echo -n "$secret_value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    
    if [ -z "$secret_value" ]; then
        echo -e "${YELLOW}⚠️  Empty value, skipping $secret_name${NC}"
        return
    fi
    
    # Create or update the secret
    if gcloud secrets describe $secret_name &>/dev/null; then
        echo -n "$secret_value" | gcloud secrets versions add $secret_name --data-file=-
        echo -e "${GREEN}✅ Updated secret: $secret_name${NC}"
    else
        echo -n "$secret_value" | gcloud secrets create $secret_name --data-file=- --replication-policy=automatic
        echo -e "${GREEN}✅ Created secret: $secret_name${NC}"
    fi
}

echo -e "${YELLOW}🔧 Required secrets for AI Explorer Backend:${NC}"
echo ""

# LLM API Key (supports OpenAI, Anthropic, Google, etc.)
create_or_update_secret \
    "${APP_NAME}-llm-api-key" \
    "LLM API key for AI integration" \
    "Enter your LLM API key (OpenAI, Anthropic, Google, etc.):"



# LangSmith API Key
create_or_update_secret \
    "${APP_NAME}-langsmith-api-key" \
    "LangSmith API key for tracing" \
    "Enter your LangSmith API key:"

# BigQuery Service Account (if needed)
echo -e "${YELLOW}🔑 Setting up BigQuery Service Account Key${NC}"
echo "If you have a BigQuery service account JSON key file, provide the path:"
read -p "Path to BigQuery service account JSON file (or press Enter to skip): " bigquery_key_path

# Trim whitespace from the path
bigquery_key_path=$(echo "$bigquery_key_path" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

if [ ! -z "$bigquery_key_path" ]; then
    echo "  Checking file: $bigquery_key_path"
    if [ -f "$bigquery_key_path" ]; then
        echo "  File exists, proceeding with secret creation/update..."
        if gcloud secrets describe "${APP_NAME}-bigquery-sa-key" &>/dev/null; then
            echo "  Secret already exists"
            read -p "  Update existing BigQuery secret? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                gcloud secrets versions add "${APP_NAME}-bigquery-sa-key" --data-file="$bigquery_key_path"
                echo -e "${GREEN}✅ Updated BigQuery service account key${NC}"
            else
                echo -e "${YELLOW}⚠️  Skipping BigQuery secret update${NC}"
            fi
        else
            echo "  Creating new secret..."
            gcloud secrets create "${APP_NAME}-bigquery-sa-key" --data-file="$bigquery_key_path" --replication-policy=automatic
            echo -e "${GREEN}✅ Created BigQuery service account key${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  File not found: $bigquery_key_path${NC}"
        echo "  Please check the file path and try again"
    fi
else
    echo -e "${YELLOW}⚠️  No file path provided, skipping BigQuery service account key${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Secret setup completed!${NC}"
echo -e "${YELLOW}📋 Next steps:${NC}"
echo "1. Review the secrets in the Google Cloud Console"
echo "2. Ensure your Terraform configuration references these secrets correctly"
echo "3. Run the deployment script: ./scripts/deploy.sh"