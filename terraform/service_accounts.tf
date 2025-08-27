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

resource "google_cloud_run_service_iam_binding" "mcp_lb_access" {
  location = google_cloud_run_v2_service.mcp_servers.location
  service  = google_cloud_run_v2_service.mcp_servers.name
  role     = "roles/run.invoker"

  members = [
    # "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com", # Load Balancer
    "serviceAccount:${google_service_account.backend_sa.email}", # Backend can call MCP
  ]
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
