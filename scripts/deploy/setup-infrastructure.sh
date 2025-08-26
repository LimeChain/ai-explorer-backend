#!/bin/bash
set -e

# Simple script to deploy core infrastructure (VPC, DB, Redis)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID=${PROJECT_ID}

echo -e "${GREEN}🏗️ Setting up core infrastructure${NC}"
echo "  Project: $PROJECT_ID"
echo ""

# Validate environment
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Error: PROJECT_ID environment variable is required${NC}"
    exit 1
fi

if [ ! -f "terraform.tfvars" ]; then
    echo -e "${RED}❌ Error: terraform.tfvars not found${NC}"
    echo "Please copy from template: cp terraform.tfvars.example terraform.tfvars"
    exit 1
fi

# Initialize Terraform (always run to ensure providers are up to date)
echo -e "${YELLOW}🔧 Initializing Terraform...${NC}"
if ! terraform init; then
    echo -e "${RED}❌ Error: Terraform initialization failed${NC}"
    exit 1
fi

# Validate configuration
echo -e "${YELLOW}🔍 Validating Terraform configuration...${NC}"
if ! terraform validate; then
    echo -e "${RED}❌ Error: Terraform configuration validation failed${NC}"
    exit 1
fi

# Plan infrastructure deployment (core resources only)
echo -e "${YELLOW}📋 Planning infrastructure deployment...${NC}"
terraform plan -var-file=terraform.tfvars \
    -target=google_compute_network.vpc \
    -target=google_compute_subnetwork.subnet \
    -target=google_compute_global_address.private_ip_address \
    -target=google_service_networking_connection.private_vpc_connection \
    -target=google_sql_database_instance.postgres \
    -target=google_sql_database.database \
    -target=google_sql_user.database_user \
    -target=google_redis_instance.redis \
    -target=google_secret_manager_secret.database_url \
    -target=google_secret_manager_secret.redis_url \
    -target=google_secret_manager_secret.db_password \
    -target=google_secret_manager_secret_version.database_url \
    -target=google_secret_manager_secret_version.redis_url \
    -target=google_secret_manager_secret_version.db_password \
    -target=google_service_account.backend_sa \
    -target=google_service_account.mcp_sa \
    -target=google_artifact_registry_repository.docker_repo \
    -target=google_vpc_access_connector.connector \
    -out=tfplan-infrastructure

# Apply infrastructure
echo -e "${YELLOW}🚀 Deploying infrastructure...${NC}"
terraform apply -auto-approve tfplan-infrastructure

echo -e "${GREEN}🎉 Core infrastructure deployed successfully!${NC}"
echo ""
echo -e "${YELLOW}📋 Next steps:${NC}"
echo "1. Set up secrets: ./scripts/deploy/secrets.sh"
echo "2. Deploy applications: ./scripts/deploy/deploy.sh"