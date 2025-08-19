# Output important resource information

output "project_id" {
  description = "GCP Project ID"
  value       = var.project_id
}

output "region" {
  description = "GCP Region"
  value       = var.region
}

# Database outputs
output "database_instance_name" {
  description = "Cloud SQL instance name"
  value       = google_sql_database_instance.postgres.name
}

output "database_connection_name" {
  description = "Cloud SQL connection name"
  value       = google_sql_database_instance.postgres.connection_name
}

output "database_private_ip" {
  description = "Cloud SQL private IP address"
  value       = google_sql_database_instance.postgres.private_ip_address
}

output "database_public_ip" {
  description = "Cloud SQL public IP address"
  value       = google_sql_database_instance.postgres.public_ip_address
}

# Redis outputs
output "redis_host" {
  description = "Redis instance host"
  value       = google_redis_instance.redis.host
}

output "redis_port" {
  description = "Redis instance port"
  value       = google_redis_instance.redis.port
}

# Cloud Run outputs
output "backend_api_url" {
  description = "Backend API Cloud Run service URL"
  value       = google_cloud_run_v2_service.backend_api.uri
}

output "mcp_servers_url" {
  description = "MCP Servers Cloud Run service URL"
  value       = google_cloud_run_v2_service.mcp_servers.uri
}

# Load Balancer outputs
output "load_balancer_ip" {
  description = "Load balancer external IP address"
  value       = google_compute_global_address.lb_ip.address
}

output "load_balancer_url" {
  description = "Load balancer URL"
  value       = var.domain_name != "" ? "https://${var.domain_name}" : "http://${google_compute_global_address.lb_ip.address}"
}

# Artifact Registry outputs
output "docker_repository_url" {
  description = "Docker repository URL in Artifact Registry"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}"
}

# Firebase outputs (disabled)
# output "firebase_hosting_url" {
#   description = "Firebase Hosting URL"
#   value       = "https://${google_firebase_hosting_site.default.site_id}.web.app"
# }

# output "firebase_project_id" {
#   description = "Firebase project ID"
#   value       = google_firebase_project.default.project
# }

# Secret Manager outputs
output "secret_names" {
  description = "Names of secrets created in Secret Manager"
  value = {
    database_password = google_secret_manager_secret.db_password.secret_id

    llm_api_key              = google_secret_manager_secret.llm_api_key.secret_id
    langsmith_api_key        = google_secret_manager_secret.langsmith_api_key.secret_id
    bigquery_service_account = google_secret_manager_secret.bigquery_service_account.secret_id
    redis_url                = google_secret_manager_secret.redis_url.secret_id
  }
}

# Service Account outputs
output "service_accounts" {
  description = "Service account emails"
  value = {
    backend_sa = google_service_account.backend_sa.email
    mcp_sa     = google_service_account.mcp_sa.email
  }
}

# Network outputs
output "vpc_network_name" {
  description = "VPC network name"
  value       = google_compute_network.vpc.name
}

output "vpc_subnet_name" {
  description = "VPC subnet name"
  value       = google_compute_subnetwork.subnet.name
}
