# Random password for database user
resource "random_password" "db_password" {
  length  = 32
  special = true
}

# Cloud SQL PostgreSQL instance
resource "google_sql_database_instance" "postgres" {
  name             = "${var.app_name}-postgres"
  database_version = "POSTGRES_17"
  region           = var.region

  settings {
    tier                  = var.database_instance_tier
    availability_type     = "ZONAL"
    disk_type             = "PD_SSD"
    disk_size             = var.database_disk_size
    disk_autoresize       = true
    disk_autoresize_limit = 500

    backup_configuration {
      enabled                        = true
      start_time                     = "03:00"
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
      backup_retention_settings {
        retained_backups = 30
        retention_unit   = "COUNT"
      }
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }


    maintenance_window {
      day          = 7
      hour         = 3
      update_track = "stable"
    }
  }

  deletion_protection = false

  depends_on = [google_service_networking_connection.private_vpc_connection]
}

# Database
resource "google_sql_database" "database" {
  name     = var.database_name
  instance = google_sql_database_instance.postgres.name
}

# Database user
resource "google_sql_user" "database_user" {
  name     = var.database_user
  instance = google_sql_database_instance.postgres.name
  password = random_password.db_password.result
}


resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}

resource "google_secret_manager_secret_version" "database_url" {
  secret      = google_secret_manager_secret.database_url.id
  secret_data = "postgresql://${google_sql_user.database_user.name}:${random_password.db_password.result}@${google_sql_database_instance.postgres.private_ip_address}:5432/${google_sql_database.database.name}"
}
