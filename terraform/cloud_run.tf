# VPC Connector for Cloud Run to access VPC resources
resource "google_vpc_access_connector" "connector" {
  name          = "${var.app_name}-vpc-conn"
  ip_cidr_range = "10.8.0.0/28"
  network       = google_compute_network.vpc.name
  region        = var.region

  depends_on = [google_project_service.apis]
}

# Backend API Cloud Run Service
resource "google_cloud_run_v2_service" "backend_api" {
  name     = "${var.app_name}-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account = google_service_account.backend_sa.email

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "ALL_TRAFFIC"
    }

    scaling {
      max_instance_count = var.cloud_run_max_instances
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}/api:latest"

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = var.cloud_run_cpu
          memory = var.cloud_run_memory
        }
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "REDIS_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.redis_url.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "COLLECTION_NAME"
        value = var.collection_name
      }

      env {
        name  = "ALLOWED_ORIGINS"
        value = jsonencode(var.allowed_origins)
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "LOG_LEVEL"
        value = var.log_level
      }

      env {
        name  = "LANGSMITH_ENDPOINT"
        value = var.langsmith_endpoint
      }

      env {
        name  = "RATE_LIMIT_MAX_REQUESTS"
        value = tostring(var.rate_limit_max_requests)
      }

      env {
        name  = "RATE_LIMIT_WINDOW_SECONDS"
        value = tostring(var.rate_limit_window_seconds)
      }

      env {
        name  = "GLOBAL_RATE_LIMIT_MAX_REQUESTS"
        value = tostring(var.global_rate_limit_max_requests)
      }

      env {
        name  = "GLOBAL_RATE_LIMIT_WINDOW_SECONDS"
        value = tostring(var.global_rate_limit_window_seconds)
      }

      env {
        name = "LLM_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.llm_api_key.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "LLM_PROVIDER"
        value = var.llm_provider
      }

      env {
        name  = "LLM_MODEL"
        value = var.llm_model
      }

      env {
        name = "LANGSMITH_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.langsmith_api_key.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "LANGSMITH_TRACING"
        value = tostring(var.langsmith_tracing)
      }

      env {
        name  = "LANGSMITH_PROJECT"
        value = var.app_name
      }

      env {
        name  = "MCP_ENDPOINT"
        value = google_cloud_run_v2_service.mcp_servers.uri
      }

      env {
        name  = "EMBEDDING_MODEL"
        value = var.embedding_model
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_sql_database_instance.postgres
  ]
}

# MCP Servers Cloud Run Service
resource "google_cloud_run_v2_service" "mcp_servers" {
  name     = "${var.app_name}-mcp-server"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.mcp_sa.email

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "ALL_TRAFFIC"
    }

    scaling {
      max_instance_count = var.cloud_run_max_instances
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}/mcp-server:latest"

      ports {
        container_port = 8001
      }

      resources {
        limits = {
          cpu    = var.cloud_run_cpu
          memory = var.cloud_run_memory
        }
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "LLM_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.llm_api_key.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "COLLECTION_NAME"
        value = var.collection_name
      }

      env {
        name  = "EMBEDDING_MODEL"
        value = var.embedding_model
      }



      env {
        name = "BIGQUERY_SERVICE_ACCOUNT"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.bigquery_service_account.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [google_project_service.apis]
}

# Service Accounts
resource "google_service_account" "backend_sa" {
  account_id   = "${var.app_name}-backend-sa"
  display_name = "Backend Service Account"
  description  = "Service account for backend Cloud Run service"
}

resource "google_service_account" "mcp_sa" {
  account_id   = "${var.app_name}-mcp-sa"
  display_name = "MCP Servers Service Account"
  description  = "Service account for MCP servers Cloud Run service"
}

# IAM bindings for service accounts
resource "google_project_iam_binding" "backend_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"

  members = [
    "serviceAccount:${google_service_account.backend_sa.email}",
  ]
}

resource "google_secret_manager_secret_iam_binding" "backend_secret_access" {
  secret_id = google_secret_manager_secret.db_password.secret_id
  role      = "roles/secretmanager.secretAccessor"

  members = [
    "serviceAccount:${google_service_account.backend_sa.email}",
  ]
}

resource "google_project_iam_binding" "mcp_bigquery_user" {
  project = var.project_id
  role    = "roles/bigquery.user"

  members = [
    "serviceAccount:${google_service_account.mcp_sa.email}",
  ]
}

# IAM for Load Balancer access to Cloud Run services
# Only the Load Balancer and internal services can invoke Cloud Run
resource "google_cloud_run_service_iam_binding" "backend_lb_access" {
  location = google_cloud_run_v2_service.backend_api.location
  service  = google_cloud_run_v2_service.backend_api.name
  role     = "roles/run.invoker"

  members = [
    "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com", # Load Balancer
    "serviceAccount:${google_service_account.backend_sa.email}",                                  # Backend service
  ]
}

resource "google_cloud_run_service_iam_binding" "mcp_lb_access" {
  location = google_cloud_run_v2_service.mcp_servers.location
  service  = google_cloud_run_v2_service.mcp_servers.name
  role     = "roles/run.invoker"

  members = [
    "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com", # Load Balancer
    "serviceAccount:${google_service_account.backend_sa.email}",                                  # Backend can call MCP
  ]
}



