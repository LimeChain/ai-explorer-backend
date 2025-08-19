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

# Database connection string
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

# IAM bindings for secret access
resource "google_secret_manager_secret_iam_binding" "llm_api_key_access" {
  secret_id = google_secret_manager_secret.llm_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"

  members = [
    "serviceAccount:${google_service_account.backend_sa.email}",
    "serviceAccount:${google_service_account.mcp_sa.email}",
  ]
}





resource "google_secret_manager_secret_iam_binding" "bigquery_access" {
  secret_id = google_secret_manager_secret.bigquery_service_account.secret_id
  role      = "roles/secretmanager.secretAccessor"

  members = [
    "serviceAccount:${google_service_account.mcp_sa.email}",
  ]
}

resource "google_secret_manager_secret_iam_binding" "redis_access" {
  secret_id = google_secret_manager_secret.redis_url.secret_id
  role      = "roles/secretmanager.secretAccessor"

  members = [
    "serviceAccount:${google_service_account.backend_sa.email}",
  ]
}

resource "google_secret_manager_secret_iam_binding" "langsmith_access" {
  secret_id = google_secret_manager_secret.langsmith_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"

  members = [
    "serviceAccount:${google_service_account.backend_sa.email}",
    "serviceAccount:${google_service_account.mcp_sa.email}",
  ]
}

resource "google_secret_manager_secret_iam_binding" "database_url_access" {
  secret_id = google_secret_manager_secret.database_url.secret_id
  role      = "roles/secretmanager.secretAccessor"

  members = [
    "serviceAccount:${google_service_account.backend_sa.email}",
    "serviceAccount:${google_service_account.mcp_sa.email}",
  ]
}
