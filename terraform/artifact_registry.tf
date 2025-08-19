# Artifact Registry for Docker images
resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = "ai-explorer-docker-repo"
  description   = "Docker repository for ${var.app_name}"
  format        = "DOCKER"

  labels = {
    environment = var.environment
    app         = var.app_name
  }
}

# IAM binding for Cloud Build to push to Artifact Registry
resource "google_artifact_registry_repository_iam_binding" "docker_repo_push" {
  location   = google_artifact_registry_repository.docker_repo.location
  repository = google_artifact_registry_repository.docker_repo.name
  role       = "roles/artifactregistry.writer"

  members = [
    "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com",
  ]
}