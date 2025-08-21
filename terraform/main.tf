terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# Get project data for IAM bindings and service account references
data "google_project" "project" {
  project_id = var.project_id
}

# Enable APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "artifactregistry.googleapis.com",  # Artifact Registry
    "secretmanager.googleapis.com",     # Secret Manager
    "compute.googleapis.com",           # Compute Engine
    "run.googleapis.com",               # Cloud Run
    "sql-component.googleapis.com",     # Cloud SQL
    "sqladmin.googleapis.com",          # Cloud SQL
    "vpcaccess.googleapis.com",         # VPC Access Connector
    "servicenetworking.googleapis.com", # Service Networking
    "redis.googleapis.com",             # Cloud Memorystore Redis
    "cloudbuild.googleapis.com",
    "firebase.googleapis.com",
    "firebasehosting.googleapis.com",
    "storage.googleapis.com",           # Cloud Storage
    "dns.googleapis.com"                # Cloud DNS
  ])

  service            = each.value
  disable_on_destroy = false
}
