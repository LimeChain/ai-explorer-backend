#!/bin/bash
set -e

# This script helps clean up GCP resources and recover from failed Terraform deployments

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID=${PROJECT_ID}
REGION=${REGION:-"us-central1"}

echo -e "${BLUE}🧹 AI Explorer Backend - Terraform Cleanup${NC}"
echo -e "${YELLOW}📋 Configuration:${NC}"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"
echo ""

# Validate required variables
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Error: PROJECT_ID environment variable is required${NC}"
    echo "Set it with: export PROJECT_ID=your-gcp-project-id"
    exit 1
fi

# Function to handle errors
handle_error() {
    echo -e "${RED}❌ Error: $1${NC}"
    exit 1
}

# Function to track failed operations
FAILED_OPERATIONS=()
track_failure() {
    local operation="$1"
    FAILED_OPERATIONS+=("$operation")
    echo -e "${RED}    ❌ Failed: $operation${NC}"
}

# Function to safely delete resource with better error handling
safe_delete_resource() {
    local resource_type="$1"
    local resource_name="$2"
    local delete_command="$3"
    
    echo -e "${YELLOW}    Deleting $resource_type $resource_name...${NC}"
    if eval "$delete_command" >/dev/null 2>&1; then
        echo -e "${GREEN}    ✅ Successfully deleted $resource_type $resource_name${NC}"
        return 0
    else
        track_failure "$resource_type: $resource_name"
        return 1
    fi
}

# Function to show cleanup summary
show_cleanup_summary() {
    echo ""
    if [ ${#FAILED_OPERATIONS[@]} -eq 0 ]; then
        echo -e "${GREEN}🎉 All cleanup operations completed successfully!${NC}"
    else
        echo -e "${YELLOW}⚠️  Cleanup completed with ${#FAILED_OPERATIONS[@]} failures:${NC}"
        for failed_op in "${FAILED_OPERATIONS[@]}"; do
            echo -e "${RED}  - $failed_op${NC}"
        done
        echo ""
        echo -e "${YELLOW}💡 Failed resources may need manual cleanup or may not have existed.${NC}"
    fi
}

# Check if we're in the right directory
if [ ! -f "terraform.tfvars" ]; then
    echo -e "${RED}❌ Error: Please run this script from the terraform directory${NC}"
    echo "  cd terraform && ../scripts/fix-terraform-state.sh"
    exit 1
fi

echo -e "${YELLOW}🔍 Current state of terraform directory:${NC}"
ls -la

echo ""

# Support non-interactive mode via environment variables
# Usage: CLEANUP_MODE=destroy_all ../scripts/deploy/terraform-cleanup.sh
if [ "$CLEANUP_MODE" = "destroy_all" ]; then
    choice=1
    confirm="yes"
    echo -e "${BLUE}🤖 Running in automated mode: Destroy all resources${NC}"
elif [ "$CLEANUP_MODE" = "state_only" ]; then
    choice=2
    echo -e "${BLUE}🤖 Running in automated mode: Clean state only${NC}"
elif [ "$CLEANUP_MODE" = "local_only" ]; then
    choice=3
    echo -e "${BLUE}🤖 Running in automated mode: Clean local files only${NC}"
elif [ "$CLEANUP_MODE" = "import" ]; then
    choice=4
    echo -e "${BLUE}🤖 Running in automated mode: Import existing resources${NC}"
else
    echo -e "${BLUE}What would you like to do?${NC}"
    echo "1) Clean slate: Destroy existing resources and start fresh (DESTRUCTIVE)"
    echo "2) Clean terraform state and reinitialize (keeps resources, loses state)"
    echo "3) Just clean local state files and retry"
    echo "4) Import existing resources into Terraform state"
    echo "5) Exit"
    echo ""
    echo -e "${YELLOW}💡 For automated mode, use: CLEANUP_MODE=import ./terraform-cleanup.sh${NC}"
    echo -e "${YELLOW}💡 To list resources, use: ./scripts/deploy/list.sh${NC}"
    
    read -p "Choose an option (1-5): " choice
fi

case $choice in
    1)
        if [ "$CLEANUP_MODE" != "destroy_all" ]; then
            echo -e "${RED}🚨 WARNING: This will DESTROY all existing resources!${NC}"
            read -p "Are you sure? Type 'yes' to continue: " confirm
            if [ "$confirm" != "yes" ]; then
                echo "Cancelled."
                exit 0
            fi
        else
            echo -e "${RED}🚨 Automated mode: DESTROYING all existing resources!${NC}"
        fi
        
        echo -e "${YELLOW}🗑️ Destroying existing resources...${NC}"
        
        # Delete load balancer components in proper dependency order
        echo -e "${YELLOW}  Step 1: Deleting forwarding rules...${NC}"
        FORWARDING_RULES=(
            "ai-explorer-https-forwarding-rule"
            "ai-explorer-http-forwarding-rule"
        )
        for rule in "${FORWARDING_RULES[@]}"; do
            if gcloud compute forwarding-rules describe $rule --global >/dev/null 2>&1; then
                safe_delete_resource "forwarding rule" "$rule" "gcloud compute forwarding-rules delete $rule --global --quiet"
            fi
        done
        
        echo -e "${YELLOW}  Step 2: Deleting target proxies...${NC}"
        TARGET_PROXIES=(
            "ai-explorer-https-proxy"
            "ai-explorer-http-proxy"
        )
        for proxy in "${TARGET_PROXIES[@]}"; do
            if gcloud compute target-https-proxies describe $proxy --global >/dev/null 2>&1; then
                safe_delete_resource "HTTPS proxy" "$proxy" "gcloud compute target-https-proxies delete $proxy --global --quiet"
            elif gcloud compute target-http-proxies describe $proxy --global >/dev/null 2>&1; then
                safe_delete_resource "HTTP proxy" "$proxy" "gcloud compute target-http-proxies delete $proxy --global --quiet"
            fi
        done
        
        echo -e "${YELLOW}  Step 3: Deleting URL maps...${NC}"
        URL_MAPS=(
            "ai-explorer-url-map"
            "ai-explorer-redirect-url-map"
        )
        for urlmap in "${URL_MAPS[@]}"; do
            if gcloud compute url-maps describe $urlmap --global >/dev/null 2>&1; then
                safe_delete_resource "URL map" "$urlmap" "gcloud compute url-maps delete $urlmap --global --quiet"
            fi
        done
        
        echo -e "${YELLOW}  Step 4: Deleting backend services...${NC}"
        BACKEND_SERVICES=(
            "ai-explorer-api-service"
        )
        for service in "${BACKEND_SERVICES[@]}"; do
            if gcloud compute backend-services describe $service --global >/dev/null 2>&1; then
                safe_delete_resource "backend service" "$service" "gcloud compute backend-services delete $service --global --quiet"
            fi
        done
        
        echo -e "${YELLOW}  Step 5: Deleting network endpoint groups...${NC}"
        NEGS=(
            "ai-explorer-api-neg"
        )
        for neg in "${NEGS[@]}"; do
            if gcloud compute network-endpoint-groups describe $neg --region=$REGION >/dev/null 2>&1; then
                safe_delete_resource "NEG" "$neg" "gcloud compute network-endpoint-groups delete $neg --region=$REGION --quiet"
            fi
        done
        
        echo -e "${YELLOW}  Step 6: Deleting SSL certificates...${NC}"
        SSL_CERTS=(
            "ai-explorer-self-signed-cert"
        )
        for cert in "${SSL_CERTS[@]}"; do
            if gcloud compute ssl-certificates describe $cert --global >/dev/null 2>&1; then
                safe_delete_resource "SSL certificate" "$cert" "gcloud compute ssl-certificates delete $cert --global --quiet"
            fi
        done
        
        echo -e "${YELLOW}  Step 7: Deleting health checks...${NC}"
        HEALTH_CHECKS=(
            "ai-explorer-api-health-check"
        )
        for hc in "${HEALTH_CHECKS[@]}"; do
            if gcloud compute health-checks describe $hc --global >/dev/null 2>&1; then
                safe_delete_resource "health check" "$hc" "gcloud compute health-checks delete $hc --global --quiet"
            fi
        done
        
        echo -e "${YELLOW}  Step 8: Deleting global addresses...${NC}"
        ADDRESSES=(
            "ai-explorer-lb-ip"
            "ai-explorer-private-ip"
        )
        for address in "${ADDRESSES[@]}"; do
            if gcloud compute addresses describe $address --global >/dev/null 2>&1; then
                safe_delete_resource "global address" "$address" "gcloud compute addresses delete $address --global --quiet"
            fi
        done
        
        echo -e "${YELLOW}  Step 9: Deleting firewall rules...${NC}"
        # Get all firewall rules for the VPC - try multiple methods to capture all rules
        echo -e "${YELLOW}    Searching for firewall rules...${NC}"
        FIREWALL_RULES=$(gcloud compute firewall-rules list --filter="network:ai-explorer-vpc" --format="value(name)" 2>/dev/null || echo "")
        
        # Also check for rules that might contain ai-explorer in the name
        ADDITIONAL_RULES=$(gcloud compute firewall-rules list --filter="name~.*ai.*explorer.*" --format="value(name)" 2>/dev/null || echo "")
        
        # Combine and deduplicate rules
        ALL_RULES=$(echo -e "$FIREWALL_RULES\n$ADDITIONAL_RULES" | sort -u | grep -v '^$' || echo "")
        
        if [ ! -z "$ALL_RULES" ]; then
            echo -e "${YELLOW}    Found $(echo "$ALL_RULES" | wc -l) firewall rules to delete${NC}"
            for rule in $ALL_RULES; do
                if [ ! -z "$rule" ] && gcloud compute firewall-rules describe "$rule" >/dev/null 2>&1; then
                    safe_delete_resource "firewall rule" "$rule" "gcloud compute firewall-rules delete '$rule' --quiet"
                fi
            done
        else
            echo -e "${BLUE}    ℹ️  No firewall rules found${NC}"
        fi
        
        # Also try to delete the specific rule mentioned in the error
        SPECIFIC_RULE="aet-uscentral1-ai--explorer--vpc--conn-earfw"
        if gcloud compute firewall-rules describe "$SPECIFIC_RULE" >/dev/null 2>&1; then
            safe_delete_resource "specific firewall rule" "$SPECIFIC_RULE" "gcloud compute firewall-rules delete '$SPECIFIC_RULE' --quiet"
        fi
        
        echo -e "${YELLOW}  Step 10: Deleting subnets and VPC network...${NC}"
        # Delete subnets first
        echo -e "${YELLOW}    Searching for subnets...${NC}"
        SUBNETS=$(gcloud compute networks subnets list --filter="network:ai-explorer-vpc" --format="value(name,region)" 2>/dev/null || echo "")
        if [ ! -z "$SUBNETS" ]; then
            echo -e "${YELLOW}    Found subnets to delete${NC}"
            echo "$SUBNETS" | while read subnet_name subnet_region; do
                if [ ! -z "$subnet_name" ] && [ ! -z "$subnet_region" ]; then
                    safe_delete_resource "subnet" "$subnet_name (region: $subnet_region)" "gcloud compute networks subnets delete '$subnet_name' --region='$subnet_region' --quiet"
                fi
            done
        else
            echo -e "${BLUE}    ℹ️  No subnets found${NC}"
        fi
        
        # Try to delete VPC network
        if gcloud compute networks describe ai-explorer-vpc >/dev/null 2>&1; then
            echo -e "${YELLOW}    Deleting VPC network ai-explorer-vpc...${NC}"
            if gcloud compute networks delete ai-explorer-vpc --quiet >/dev/null 2>&1; then
                echo -e "${GREEN}    ✅ Successfully deleted VPC network ai-explorer-vpc${NC}"
            else
                track_failure "VPC network: ai-explorer-vpc (may have phantom firewall rules)"
                echo -e "${YELLOW}    ⚠️  VPC deletion failed (phantom firewall rule issue) - this is a known GCP issue${NC}"
                echo -e "${YELLOW}    The VPC may need manual deletion or may self-resolve later${NC}"
            fi
        else
            echo -e "${BLUE}    ℹ️  VPC network not found${NC}"
        fi
        
        echo -e "${YELLOW}  Step 11: Deleting service accounts...${NC}"
        SERVICE_ACCOUNTS=(
            "ai-explorer-backend-sa"
            "ai-explorer-mcp-sa"
        )
        for sa in "${SERVICE_ACCOUNTS[@]}"; do
            if gcloud iam service-accounts describe "${sa}@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1; then
                safe_delete_resource "service account" "$sa" "gcloud iam service-accounts delete '${sa}@${PROJECT_ID}.iam.gserviceaccount.com' --quiet"
            fi
        done
        
        echo -e "${YELLOW}  Step 12: Cleaning up Cloud Run services...${NC}"
        CLOUD_RUN_SERVICES=(
            "ai-explorer-api"
            "ai-explorer-mcp-server"
        )
        for service in "${CLOUD_RUN_SERVICES[@]}"; do
            if gcloud run services describe $service --platform=managed --region=$REGION >/dev/null 2>&1; then
                safe_delete_resource "Cloud Run service" "$service" "gcloud run services delete $service --platform=managed --region=$REGION --quiet"
            fi
        done
        
        echo -e "${YELLOW}  Step 13: Cleaning up additional resources...${NC}"
        
        # Clean up Cloud SQL instances
        echo -e "${YELLOW}    Checking for Cloud SQL instances...${NC}"
        CLOUD_SQL_INSTANCES=$(gcloud sql instances list --filter="name~ai-explorer.*" --format="value(name)" 2>/dev/null || echo "")
        if [ ! -z "$CLOUD_SQL_INSTANCES" ]; then
            for instance in $CLOUD_SQL_INSTANCES; do
                if [ ! -z "$instance" ]; then
                    safe_delete_resource "Cloud SQL instance" "$instance" "gcloud sql instances delete $instance --quiet"
                fi
            done
        else
            echo -e "${BLUE}    ℹ️  No Cloud SQL instances found${NC}"
        fi
        
        # Clean up Redis instances
        echo -e "${YELLOW}    Checking for Redis instances...${NC}"
        REDIS_INSTANCES=$(gcloud redis instances list --region=$REGION --filter="name~ai-explorer.*" --format="value(name)" 2>/dev/null || echo "")
        if [ ! -z "$REDIS_INSTANCES" ]; then
            for instance in $REDIS_INSTANCES; do
                if [ ! -z "$instance" ]; then
                    safe_delete_resource "Redis instance" "$instance" "gcloud redis instances delete $instance --region=$REGION --quiet"
                fi
            done
        else
            echo -e "${BLUE}    ℹ️  No Redis instances found${NC}"
        fi
        
        # Clean up Artifact Registry repositories
        echo -e "${YELLOW}    Checking for Artifact Registry repositories...${NC}"
        AR_REPOS=$(gcloud artifacts repositories list --filter="name~.*ai-explorer.*" --format="value(name.basename())" 2>/dev/null || echo "")
        if [ ! -z "$AR_REPOS" ]; then
            for repo in $AR_REPOS; do
                if [ ! -z "$repo" ]; then
                    safe_delete_resource "Artifact Registry repository" "$repo" "gcloud artifacts repositories delete $repo --location=$REGION --quiet"
                fi
            done
        else
            echo -e "${BLUE}    ℹ️  No Artifact Registry repositories found${NC}"
        fi
        
        # Clean up VPC Access Connectors
        echo -e "${YELLOW}    Checking for VPC Access Connectors...${NC}"
        VPC_CONNECTORS=$(gcloud compute networks vpc-access connectors list --region=$REGION --filter="name~ai-explorer.*" --format="value(name)" 2>/dev/null || echo "")
        if [ ! -z "$VPC_CONNECTORS" ]; then
            for connector in $VPC_CONNECTORS; do
                if [ ! -z "$connector" ]; then
                    safe_delete_resource "VPC Access Connector" "$connector" "gcloud compute networks vpc-access connectors delete $connector --region=$REGION --quiet"
                fi
            done
        else
            echo -e "${BLUE}    ℹ️  No VPC Access Connectors found${NC}"
        fi
        
        # Clean up Secret Manager secrets
        echo -e "${YELLOW}    Checking for Secret Manager secrets...${NC}"
        SECRETS=$(gcloud secrets list --filter="name~ai-explorer.*" --format="value(name.basename())" 2>/dev/null || echo "")
        if [ ! -z "$SECRETS" ]; then
            for secret in $SECRETS; do
                if [ ! -z "$secret" ]; then
                    safe_delete_resource "secret" "$secret" "gcloud secrets delete $secret --quiet"
                fi
            done
        else
            echo -e "${BLUE}    ℹ️  No Secret Manager secrets found${NC}"
        fi
        
        show_cleanup_summary
        ;;
        
    2)
        echo -e "${YELLOW}🧹 Cleaning terraform state and reinitializing...${NC}"
        
        # Backup existing state files
        if [ -f "terraform.tfstate" ]; then
            echo -e "${YELLOW}  Backing up terraform.tfstate...${NC}"
            cp terraform.tfstate "terraform.tfstate.backup.$(date +%s)"
        fi
        
        if [ -f "errored.tfstate" ]; then
            echo -e "${YELLOW}  Backing up errored.tfstate...${NC}"
            cp errored.tfstate "errored.tfstate.backup.$(date +%s)"
        fi
        
        # Clean terraform files
        echo -e "${YELLOW}  Removing state files...${NC}"
        rm -f terraform.tfstate*
        rm -f errored.tfstate*
        rm -f .terraform.lock.hcl
        rm -rf .terraform/
        
        # Reinitialize
        echo -e "${YELLOW}  Reinitializing terraform...${NC}"
        terraform init || handle_error "Terraform init failed"
        
        echo -e "${GREEN}✅ Terraform reinitialized${NC}"
        echo -e "${YELLOW}💡 You can now run terraform plan to see what needs to be created${NC}"
        ;;
        
    3)
        echo -e "${YELLOW}🧹 Cleaning local state files only...${NC}"
        
        # Backup and remove problematic state files
        if [ -f "errored.tfstate" ]; then
            echo -e "${YELLOW}  Backing up errored.tfstate...${NC}"
            cp errored.tfstate "errored.tfstate.backup.$(date +%s)"
            rm -f errored.tfstate
        fi
        
        # Remove tfplan files
        rm -f tfplan*
        
        echo -e "${GREEN}✅ Local cleanup completed${NC}"
        echo -e "${YELLOW}💡 Try running terraform plan again${NC}"
        ;;
        
    4)
        echo -e "${YELLOW}🔄 Importing existing resources into Terraform state...${NC}"
        
        # Initialize terraform if needed
        if [ ! -d ".terraform" ]; then
            echo -e "${YELLOW}  Initializing terraform...${NC}"
            terraform init || handle_error "Terraform init failed"
        fi
        
        # Track import operations
        IMPORT_FAILURES=()
        
        # Function to safely import resources
        safe_import_resource() {
            local resource_type="$1"
            local terraform_resource="$2"
            local resource_id="$3"
            
            echo -e "${YELLOW}    Importing $resource_type...${NC}"
            if terraform import "$terraform_resource" "$resource_id" >/dev/null 2>&1; then
                echo -e "${GREEN}    ✅ Successfully imported $resource_type${NC}"
                return 0
            else
                IMPORT_FAILURES+=("$resource_type")
                echo -e "${YELLOW}    ⚠️  Import failed or already exists: $resource_type${NC}"
                return 1
            fi
        }
        
        # Check for existing VPC Access Connector
        echo -e "${YELLOW}  Checking for VPC Access Connector...${NC}"
        VPC_CONNECTOR_NAME=$(gcloud compute networks vpc-access connectors list --region=$REGION --filter="name~.*ai.*explorer.*" --format="value(name)" 2>/dev/null | head -1)
        
        if [ ! -z "$VPC_CONNECTOR_NAME" ]; then
            echo -e "${YELLOW}    Found VPC Access Connector: $VPC_CONNECTOR_NAME${NC}"
            safe_import_resource "VPC Access Connector" "google_vpc_access_connector.connector" "projects/$PROJECT_ID/locations/$REGION/connectors/$VPC_CONNECTOR_NAME"
        else
            echo -e "${BLUE}    ℹ️  No VPC Access Connector found${NC}"
        fi
        
        # Check for other existing resources and import them
        echo -e "${YELLOW}  Checking for other resources to import...${NC}"
        
        # Service accounts  
        echo -e "${YELLOW}  Checking for Service Accounts...${NC}"
        SA_BACKEND=$(gcloud iam service-accounts describe "ai-explorer-backend-sa@${PROJECT_ID}.iam.gserviceaccount.com" --format="value(email)" 2>/dev/null || echo "")
        if [ ! -z "$SA_BACKEND" ]; then
            echo -e "${YELLOW}    Found backend service account: $SA_BACKEND${NC}"
            safe_import_resource "Backend Service Account" "google_service_account.backend_sa" "projects/$PROJECT_ID/serviceAccounts/$SA_BACKEND"
        else
            echo -e "${BLUE}    ℹ️  Backend service account not found${NC}"
        fi
        
        SA_MCP=$(gcloud iam service-accounts describe "ai-explorer-mcp-sa@${PROJECT_ID}.iam.gserviceaccount.com" --format="value(email)" 2>/dev/null || echo "")
        if [ ! -z "$SA_MCP" ]; then
            echo -e "${YELLOW}    Found MCP service account: $SA_MCP${NC}"
            safe_import_resource "MCP Service Account" "google_service_account.mcp_sa" "projects/$PROJECT_ID/serviceAccounts/$SA_MCP"
        else
            echo -e "${BLUE}    ℹ️  MCP service account not found${NC}"
        fi
        
        # VPC and subnet
        VPC_NAME=$(gcloud compute networks describe ai-explorer-vpc --format="value(name)" 2>/dev/null || true)
        if [ ! -z "$VPC_NAME" ]; then
            echo -e "${YELLOW}    Importing VPC network...${NC}"
            terraform import google_compute_network.vpc "projects/$PROJECT_ID/global/networks/$VPC_NAME" || echo "    Import failed or already exists"
        fi
        
        SUBNET_NAME=$(gcloud compute networks subnets describe ai-explorer-subnet --region=$REGION --format="value(name)" 2>/dev/null || true)
        if [ ! -z "$SUBNET_NAME" ]; then
            echo -e "${YELLOW}    Importing subnet...${NC}"
            terraform import google_compute_subnetwork.subnet "projects/$PROJECT_ID/regions/$REGION/subnetworks/$SUBNET_NAME" || echo "    Import failed or already exists"
        fi
        
        # Show import summary
        echo ""
        if [ ${#IMPORT_FAILURES[@]} -eq 0 ]; then
            echo -e "${GREEN}🎉 All import operations completed successfully!${NC}"
        else
            echo -e "${YELLOW}⚠️  Import completed with ${#IMPORT_FAILURES[@]} failures:${NC}"
            for failed_import in "${IMPORT_FAILURES[@]}"; do
                echo -e "${YELLOW}  - $failed_import${NC}"
            done
            echo ""
            echo -e "${YELLOW}💡 Failed imports may indicate resources don't exist or are already in state.${NC}"
        fi
        echo -e "${YELLOW}💡 You can now run terraform plan to see remaining resources to create${NC}"
        ;;
        
    5)
        echo "Exiting..."
        exit 0
        ;;
        
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. If you chose option 1 or 2, you can now run: ./scripts/deploy/deploy.sh"
echo "2. If you chose option 3, try: terraform plan -var-file=terraform.tfvars"  
echo "3. If you chose option 4, try: terraform plan -var-file=terraform.tfvars"
echo "4. For deployment with auto-recovery: ./scripts/deploy/deploy.sh"
echo "5. To force image rebuild: FORCE_BUILD=true ./scripts/deploy/deploy.sh"
echo "6. To import existing resources: CLEANUP_MODE=import ./scripts/deploy/cleanup.sh"
echo "7. To list all resources: ./scripts/deploy/list.sh"
echo "8. Monitor the deployment carefully"
