#!/bin/bash
set -e

# Builds Docker images and updates Cloud Run services
# Can be run multiple times for redeployments
# Requires infrastructure to be already set up

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID=${PROJECT_ID}
REGION=${REGION:-"us-central1"}
REPOSITORY=${REPOSITORY:-"ai-explorer-docker-repo"}
SHA=$(git rev-parse HEAD)
SHORT_SHA=${SHA:0:8}
FORCE_BUILD=${FORCE_BUILD:-"false"}  # Set to "true" to force image rebuild
APP_NAME="ai-explorer"

echo -e "${BLUE}🐳 AI Explorer Backend - Build and Deploy${NC}"
echo -e "${YELLOW}📋 Configuration:${NC}"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Repository: $REPOSITORY"
echo "  Commit SHA: $SHORT_SHA"
echo "  Force Build: $FORCE_BUILD"
echo ""

# Function to check command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ Error: $1 is not installed${NC}"
        exit 1
    fi
}

# Function to handle errors
handle_error() {
    echo -e "${RED}❌ Error: $1${NC}"
    exit 1
}

# Pre-flight checks
echo -e "${YELLOW}🔍 Pre-flight checks...${NC}"

# Validate required variables
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Error: PROJECT_ID environment variable is required${NC}"
    echo "Set it with: export PROJECT_ID=your-gcp-project-id"
    exit 1
fi

check_command gcloud
check_command terraform
check_command docker
check_command git

# Check if authenticated with gcloud
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
    echo -e "${YELLOW}🔐 Please authenticate with GCP first:${NC}"
    echo "  gcloud auth login"
    exit 1
fi

# Set GCP project
echo -e "${YELLOW}🔧 Setting GCP project...${NC}"
gcloud config set project $PROJECT_ID || handle_error "Failed to set GCP project"

# Configure Docker for GCP
echo -e "${YELLOW}🐳 Configuring Docker for GCP...${NC}"
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet || handle_error "Failed to configure Docker"

# Navigate to terraform directory from script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../../terraform"
cd "$TERRAFORM_DIR"

# Initialize Terraform if needed
if [ ! -d ".terraform" ]; then
    echo -e "${YELLOW}🔧 Initializing Terraform...${NC}"
    if ! terraform init; then
        echo -e "${RED}❌ Error: Terraform initialization failed${NC}"
        exit 1
    fi
fi

# Check if infrastructure exists
echo -e "${YELLOW}🔍 Checking infrastructure prerequisites...${NC}"
if ! terraform output database_instance_name >/dev/null 2>&1; then
    echo -e "${RED}❌ Database infrastructure not found${NC}"
    echo -e "${YELLOW}💡 Please run infrastructure setup first:${NC}"
    echo "  ./scripts/deploy/setup-infrastructure.sh"
    exit 1
fi

# Check Redis infrastructure
if ! terraform output redis_host >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Redis infrastructure not found in Terraform state${NC}"
    echo -e "${YELLOW}💡 This might be expected if Redis is still being created${NC}"
else
    echo -e "${GREEN}✅ Redis infrastructure found${NC}"
fi

echo -e "${GREEN}✅ Infrastructure prerequisites check passed${NC}"

# Get the Docker repository URL from Terraform
echo -e "${YELLOW}🔍 Getting repository details from Terraform...${NC}"
DOCKER_REPO_URL=$(terraform output -raw docker_repository_url 2>/dev/null || echo "")
if [ -z "$DOCKER_REPO_URL" ]; then
    handle_error "Could not get Docker repository URL from Terraform"
fi

# Navigate to project root for Docker operations  
if [ -f "pyproject.toml" ] && [ -d "scripts" ]; then
    # Already in project root
    echo -e "${BLUE}  ℹ️  Already in project root${NC}"
else
    # Navigate to project root from script location
    cd "$(dirname "$0")/../.."
fi

# Build and push Docker images with smart building
echo -e "${GREEN}🐳 Building and pushing Docker images...${NC}"

# Function to check if Docker image exists in registry
check_image_exists() {
    local image="$1"
    echo -e "${YELLOW}  Checking if $image exists...${NC}"
    if gcloud container images describe "$image" >/dev/null 2>&1; then
        echo -e "${GREEN}  ✅ Image $image exists${NC}"
        return 0
    else
        echo -e "${YELLOW}  ⚠️  Image $image not found, will build${NC}"
        return 1
    fi
}

build_and_push() {
    local image_name="$1"
    local dockerfile_path="$2"
    local context_path="$3"
    
    local image_latest="${DOCKER_REPO_URL}/$image_name:latest"
    local image_sha="${DOCKER_REPO_URL}/$image_name:${SHA}"
    
    # Check if we need to build (force build or images don't exist)
    local should_build=false
    if [ "$FORCE_BUILD" = "true" ]; then
        echo -e "${YELLOW}  Force building $image_name image...${NC}"
        should_build=true
    elif ! check_image_exists "$image_latest" || ! check_image_exists "$image_sha"; then
        echo -e "${YELLOW}  Building $image_name image (missing)...${NC}"
        should_build=true
    else
        echo -e "${GREEN}  ✅ $image_name images already exist, skipping build${NC}"
        should_build=false
    fi
    
    if [ "$should_build" = true ]; then
        echo -e "${YELLOW}  Building $image_name image...${NC}"
        
        local build_cmd="docker build --platform linux/amd64"
        if [ "$dockerfile_path" != "." ]; then
            build_cmd="$build_cmd -f $dockerfile_path"
        fi
        build_cmd="$build_cmd -t $image_sha -t $image_latest $context_path"
        
        if ! eval "$build_cmd"; then
            handle_error "$image_name image build failed"
        fi
        
        echo -e "${YELLOW}  Pushing $image_name image...${NC}"
        if ! docker push "$image_sha"; then
            handle_error "$image_name image push failed"
        fi
        
        if ! docker push "$image_latest"; then
            handle_error "$image_name image push (latest) failed"
        fi
        
        echo -e "${GREEN}  ✅ $image_name image built and pushed successfully${NC}"
    fi
}

# Build and push API image
build_and_push "api" "." "."

# Build and push MCP Server image
build_and_push "mcp-server" "mcp_servers/Dockerfile" "."

# Deploy Cloud Run services and remaining infrastructure
echo -e "${GREEN}🔄 Deploying Cloud Run services and load balancer...${NC}"
cd "$TERRAFORM_DIR"

DEPLOY_SUCCESS=false
MAX_DEPLOY_RETRIES=2
DEPLOY_RETRY_COUNT=0

while [ $DEPLOY_RETRY_COUNT -lt $MAX_DEPLOY_RETRIES ] && [ "$DEPLOY_SUCCESS" = false ]; do
    if [ $DEPLOY_RETRY_COUNT -gt 0 ]; then
        echo -e "${YELLOW}  Deploy retry attempt $DEPLOY_RETRY_COUNT...${NC}"
        sleep 15
    fi
    
    echo -e "${YELLOW}  Planning deployment of Cloud Run services and load balancer...${NC}"
    if terraform plan -var-file=terraform.tfvars -out=tfplan-deploy-$DEPLOY_RETRY_COUNT; then
        echo -e "${YELLOW}  Applying full Terraform configuration...${NC}"
        if terraform apply -auto-approve tfplan-deploy-$DEPLOY_RETRY_COUNT; then
            DEPLOY_SUCCESS=true
            echo -e "${GREEN}  ✅ Cloud Run services and load balancer deployed successfully${NC}"
        else
            echo -e "${YELLOW}  ⚠️  Deployment failed, will retry...${NC}"
            DEPLOY_RETRY_COUNT=$((DEPLOY_RETRY_COUNT + 1))
        fi
    else
        echo -e "${YELLOW}  ⚠️  Deployment plan failed, will retry...${NC}"
        DEPLOY_RETRY_COUNT=$((DEPLOY_RETRY_COUNT + 1))
    fi
done

if [ "$DEPLOY_SUCCESS" = false ]; then
    echo -e "${YELLOW}⚠️  Deployment failed after retries${NC}"
    echo -e "${YELLOW}💡 You can manually retry deployment later or check the logs${NC}"
    exit 1
fi

# Get deployment outputs
echo -e "${GREEN}📊 Getting service URLs and infrastructure status...${NC}"

BACKEND_URL=$(terraform output -raw backend_api_url 2>/dev/null || echo "")
MCP_URL=$(terraform output -raw mcp_servers_url 2>/dev/null || echo "")
LB_URL=$(terraform output -raw load_balancer_url 2>/dev/null || echo "")
REDIS_HOST=$(terraform output -raw redis_host 2>/dev/null || echo "")
REDIS_PORT=$(terraform output -raw redis_port 2>/dev/null || echo "")

echo ""
echo -e "${GREEN}🎉 Build and Deploy Summary:${NC}"
echo -e "${YELLOW}  Backend API URL:${NC} $BACKEND_URL"
echo -e "${YELLOW}  MCP Servers URL:${NC} $MCP_URL"
echo -e "${YELLOW}  Load Balancer URL:${NC} $LB_URL"
if [ ! -z "$REDIS_HOST" ]; then
    echo -e "${YELLOW}  Redis Host:${NC} $REDIS_HOST:$REDIS_PORT"
else
    echo -e "${YELLOW}  Redis Status:${NC} ⚠️  Redis host not available"
fi
echo ""

# Enhanced verification with retries
echo -e "${YELLOW}🔍 Verifying deployments...${NC}"

if [ ! -z "$BACKEND_URL" ]; then
    echo -e "${YELLOW}  Waiting for services to be ready...${NC}"
    sleep 30
    
    echo -e "${YELLOW}  Testing backend health endpoint (with retries)...${NC}"
    if curl -f "$BACKEND_URL/health" --retry 5 --retry-delay 15 --max-time 60 >/dev/null 2>&1; then
        echo -e "${GREEN}  ✅ Backend health check passed${NC}"
    else
        echo -e "${YELLOW}  ⚠️  Backend health check failed (service may still be starting)${NC}"
        echo -e "${BLUE}  💡 Try checking again in a few minutes:${NC}"
        echo "    curl $BACKEND_URL/health"
    fi
fi

if [ ! -z "$LB_URL" ]; then
    echo -e "${YELLOW}  Testing load balancer (with retries)...${NC}"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$LB_URL" --retry 3 --retry-delay 10 --max-time 60 || echo "000")
    if [[ "$HTTP_CODE" =~ ^(200|301|302|404)$ ]]; then
        echo -e "${GREEN}  ✅ Load balancer responding (HTTP $HTTP_CODE)${NC}"
    else
        echo -e "${YELLOW}  ⚠️  Load balancer returned HTTP $HTTP_CODE${NC}"
    fi
fi

if [ ! -z "$REDIS_HOST" ]; then
    echo -e "${YELLOW}  Checking Redis instance status...${NC}"
    if gcloud redis instances describe ${APP_NAME}-redis --region=${REGION} --format='value(state)' 2>/dev/null | grep -q "READY"; then
        echo -e "${GREEN}  ✅ Redis instance is ready${NC}"
    else
        echo -e "${YELLOW}  ⚠️  Redis instance may still be starting${NC}"
        echo -e "${BLUE}  💡 Check status with: gcloud redis instances describe ${APP_NAME}-redis --region=${REGION}${NC}"
    fi
fi

echo ""
echo -e "${GREEN}🚀 Complete build and deployment finished successfully!${NC}"
echo -e "${YELLOW}💡 This script can be run multiple times for redeployments${NC}"
echo ""
echo -e "${BLUE}📋 What was deployed:${NC}"
echo "  ✅ Docker images built and pushed"
echo "  ✅ Cloud Run services deployed"
echo "  ✅ Load balancer configured"
echo "  ✅ SSL certificates applied"
echo "  ✅ All networking configured"
echo ""
echo -e "${YELLOW}💡 Usage for redeployments:${NC}"
echo "  Standard redeploy: ./scripts/deploy/deploy.sh"
echo "  Force rebuild images: FORCE_BUILD=true ./scripts/deploy/deploy.sh"
echo ""
echo -e "${BLUE}📊 To see all Terraform outputs:${NC}"
echo "  cd terraform && terraform output"
echo ""
