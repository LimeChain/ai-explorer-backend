# Artifact Registry for Docker images
resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = "${var.app_name}-docker-repo"
  description   = "Docker repository for ${var.app_name}"
  format        = "DOCKER"

  labels = {
    environment = var.environment
    app         = var.app_name
  }
}
