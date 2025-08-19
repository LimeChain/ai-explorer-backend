# This stores Terraform state in Google Cloud Storage for team collaboration

terraform {
  backend "gcs" {
    bucket = "ai-explorer-terraform-state" # Created manually or via bootstrap script
    prefix = "terraform/state"

    # Optional: Enable state locking with Cloud Storage
    # This prevents concurrent modifications
  }
}
