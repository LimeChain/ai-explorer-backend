# Secret Manager secrets for application configuration

# API Keys and External Service Credentials
resource "google_secret_manager_secret" "llm_api_key" {
  secret_id = "${var.app_name}-llm-api-key"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    app         = var.app_name
  }
}

resource "google_secret_manager_secret_version" "llm_api_key" {
  secret      = google_secret_manager_secret.llm_api_key.id
  secret_data = var.llm_api_key
}


# Store database password in Secret Manager
resource "google_secret_manager_secret" "db_password" {
  secret_id = "${var.app_name}-database-password"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    app         = var.app_name
  }
}

resource "google_secret_manager_secret" "database_url" {
  secret_id = "${var.app_name}-database-url"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    app         = var.app_name
  }
}

# Redis connection string (if using external Redis)
resource "google_secret_manager_secret" "redis_url" {
  secret_id = "${var.app_name}-redis-url"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    app         = var.app_name
  }
}

resource "google_secret_manager_secret" "langsmith_api_key" {
  secret_id = "${var.app_name}-langsmith-api-key"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    app         = var.app_name
  }
}

# resource "google_secret_manager_secret_version" "langsmith_api_key" {
#   secret      = google_secret_manager_secret.langsmith_api_key.id
#   secret_data = var.langsmith_api_key
# }



# BigQuery service account key (if needed)
resource "google_secret_manager_secret" "bigquery_service_account" {
  secret_id = "${var.app_name}-bigquery-sa-key"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    app         = var.app_name
  }
}

