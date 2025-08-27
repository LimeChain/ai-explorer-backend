# AI Explorer Deployment Scripts

This directory contains scripts for deploying the AI Explorer backend infrastructure and applications to Google Cloud Platform.

## Script Overview

### Recommended Approach (New - Simplified)

#### 1. `init-simple.sh` - Orchestrated Setup (Run Once)
Simple orchestrator that runs the setup process step by step with clear error handling.

#### 2. `setup-backend.sh` - Terraform Backend Only
Sets up only the Terraform remote state backend (GCS bucket).

#### 3. `setup-infrastructure.sh` - Core Infrastructure Only  
Deploys core infrastructure:
- VPC and networking
- Cloud SQL database
- Redis (Cloud Memorystore) instance
- Secret Manager integration
- Artifact Registry
- Service accounts and IAM
- VPC connector

**Simple Workflow:**
```bash
export PROJECT_ID=your-gcp-project-id
./scripts/deploy/init-simple.sh
```

### Legacy Approach (Complex)

#### 1. `init.sh` - Complex All-in-One Setup (587 lines)
⚠️ **Not recommended** - Overly complex script that tries to handle too many scenarios and can fail silently due to extensive error handling.

### 2. `deploy.sh` - Build and Deploy (Run Multiple Times)
Handles application deployment including:
- Building Docker images
- Pushing images to Artifact Registry  
- Deploying Cloud Run services
- Configuring load balancer
- SSL certificates
- Service verification

**Usage:**
```bash
./scripts/deploy/deploy.sh

# Force rebuild all images
FORCE_BUILD=true ./scripts/deploy/deploy.sh
```

This script can be run **multiple times** for redeployments after code changes.

### 3. `secrets.sh` - Secret Management
Interactive script for managing application secrets in Secret Manager.

### 4. `cleanup.sh` - Resource Cleanup
Cleans up deployed resources.

## Deployment Workflow

### Recommended: Simple Workflow

1. **First Time Setup:**
   ```bash
   # 1. Set your GCP project ID
   export PROJECT_ID=your-actual-gcp-project-id
   
   # 2. Run simple orchestrated setup
   ./scripts/deploy/init-simple.sh
   
   # 3. Set up secrets (interactive)
   cd terraform && ../scripts/deploy/secrets.sh
   
   # 4. Build and deploy applications
   cd terraform && ../scripts/deploy/deploy.sh
   ```

### Alternative: Step-by-Step

1. **Manual Step-by-Step Setup:**
   ```bash
   export PROJECT_ID=your-actual-gcp-project-id
   
   # 1. Setup Terraform backend
   ./scripts/deploy/setup-backend.sh
   
   # 2. Setup infrastructure
   cd terraform && ../scripts/deploy/setup-infrastructure.sh
   
   # 3. Setup secrets
   ../scripts/deploy/secrets.sh
   
   # 4. Deploy applications
   ../scripts/deploy/deploy.sh
   ```

2. **Subsequent Deployments (after code changes):**
   ```bash
   # Just build and deploy applications
   ./scripts/deploy/deploy.sh
   ```

## Environment Variables

- `PROJECT_ID` - GCP project ID (required)
- `REGION` - GCP region (default: "us-central1")
- `REPOSITORY` - Artifact Registry repository name (default: "ai-explorer-docker-repo")
- `FORCE_BUILD` - Force rebuild of Docker images (default: "false")

## Prerequisites

- `gcloud` CLI authenticated and configured (`gcloud auth login`)
- `gsutil` for Cloud Storage operations (included with gcloud)
- `terraform` installed
- `docker` installed
- `git` repository with committed changes
- GCP project with required APIs enabled
- `PROJECT_ID` environment variable set to your actual GCP project ID

## Troubleshooting

If deployment fails:

1. Check Terraform state:
   ```bash
   cd terraform && terraform show
   ```

2. View Terraform outputs:
   ```bash
   cd terraform && terraform output
   ```

3. Check Cloud Run service logs:
   ```bash
   gcloud logs read --service=ai-explorer-backend-api
   ```

4. Check Redis instance status:
   ```bash
   gcloud redis instances describe ai-explorer-redis --region=us-central1
   ```

5. Manual cleanup if needed:
   ```bash
   ./scripts/deploy/cleanup.sh
   ```
