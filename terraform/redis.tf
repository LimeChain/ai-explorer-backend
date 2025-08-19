# Cloud Memorystore Redis instance
resource "google_redis_instance" "redis" {
  name           = "${var.app_name}-redis"
  memory_size_gb = var.redis_memory_size_gb
  region         = var.region

  # Use configured tier
  tier = var.redis_tier

  redis_version = "REDIS_7_0"

  # Private network configuration
  authorized_network = google_compute_network.vpc.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  # Security configuration
  auth_enabled = true

  # Configuration
  redis_configs = {
    maxmemory-policy = "allkeys-lru"
  }

  labels = {
    environment = var.environment
    app         = var.app_name
  }

  depends_on = [
    google_service_networking_connection.private_vpc_connection
  ]
}

# Store Redis URL with authentication in Secret Manager
resource "google_secret_manager_secret_version" "redis_url" {
  secret      = google_secret_manager_secret.redis_url.id
  secret_data = "redis://:${google_redis_instance.redis.auth_string}@${google_redis_instance.redis.host}:${google_redis_instance.redis.port}/0"
}
