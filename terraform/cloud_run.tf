# VPC Connector for Cloud Run to access VPC resources
resource "google_vpc_access_connector" "connector" {
  name          = "${var.app_name}-vpc-conn"
  # ip_cidr_range = "10.8.0.0/28"
  # network       = google_compute_network.vpc.name
  region        = var.region

  subnet {
    name = google_compute_subnetwork.serverless_connector.name
  }
  min_instances = 2
  max_instances = 3

  depends_on = [google_project_service.apis]
}

# Backend API Cloud Run Service
resource "google_cloud_run_v2_service" "backend_api" {
  name     = "${var.app_name}-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  invoker_iam_disabled = true


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

      startup_probe {
        initial_delay_seconds = 60
        timeout_seconds = 240
        period_seconds = 240 
        tcp_socket {
          port = 8000
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
        name = "PER_USER_COST_LIMIT"
        value = tostring(var.per_user_cost_limit)
      }

      env {
        name = "PER_USER_COST_PERIOD_SECONDS"
        value = tostring(var.per_user_cost_period_seconds)
      }

      env {
        name = "GLOBAL_COST_LIMIT"
        value = tostring(var.global_cost_limit)
      }

      env {
        name = "GLOBAL_COST_PERIOD_SECONDS"
        value = tostring(var.global_cost_period_seconds)
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
        value = ""
        # value_source {
        #   secret_key_ref {
        #     secret  = google_secret_manager_secret.langsmith_api_key.secret_id
        #     version = "latest"
        #   }
        # }
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
    google_sql_database_instance.postgres,
    google_compute_router_nat.nat
  ]
}

# MCP Servers Cloud Run Service
resource "google_cloud_run_v2_service" "mcp_servers" {
  name     = "${var.app_name}-mcp-server"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  invoker_iam_disabled = true

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



      # env {
      #   name = "BIGQUERY_SERVICE_ACCOUNT"
      #   value_source {
      #     secret_key_ref {
      #       secret  = google_secret_manager_secret.bigquery_service_account.secret_id
      #       version = "latest"
      #     }
      #   }
      # }
    }
  }

  depends_on = [google_project_service.apis, google_compute_router_nat.nat]
}

