# Random suffix for bucket name to ensure global uniqueness
resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

# Cloud Storage bucket for frontend hosting
resource "google_storage_bucket" "frontend_bucket" {
  name          = "${var.app_name}-frontend-${random_string.bucket_suffix.result}"
  location      = var.region
  force_destroy = true

  # Enable uniform bucket-level access
  uniform_bucket_level_access = true

  # Website configuration
  website {
    main_page_suffix = "index.html"
    not_found_page   = "404.html"
  }

  # CORS configuration for web access
  cors {
    origin          = var.frontend_cors_origins
    method          = ["GET", "HEAD", "PUT", "POST", "DELETE"]
    response_header = ["*"]
    max_age_seconds = 3600
  }

  # Lifecycle rule to manage old versions
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }

  # Versioning
  versioning {
    enabled = true
  }

  labels = {
    environment = var.environment
    app         = var.app_name
    purpose     = "frontend-hosting"
  }
}

# Make bucket publicly readable for website hosting
resource "google_storage_bucket_iam_member" "public_access" {
  bucket = google_storage_bucket.frontend_bucket.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# Backend bucket for CDN
resource "google_compute_backend_bucket" "frontend_backend" {
  name        = "${var.app_name}-frontend-backend"
  bucket_name = google_storage_bucket.frontend_bucket.name
  enable_cdn  = true

  cdn_policy {
    cache_mode        = "CACHE_ALL_STATIC"
    default_ttl       = 3600
    max_ttl           = 86400
    client_ttl        = 3600
    negative_caching  = true
    serve_while_stale = 86400

    # Negative caching policy
    negative_caching_policy {
      code = 404
      ttl  = 120
    }

    negative_caching_policy {
      code = 410
      ttl  = 120
    }
  }
}

# Note: SSL certificates, URL maps, and load balancer configuration
# are handled in load_balancer.tf for unified routing
