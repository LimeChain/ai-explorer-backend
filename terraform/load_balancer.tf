# Global IP address for the load balancer
resource "google_compute_global_address" "lb_ip" {
  name = "${var.app_name}-lb-ip"
}

# SSL certificate (managed - for custom domain)
resource "google_compute_managed_ssl_certificate" "ssl_cert" {
  name = "${var.app_name}-ssl-cert"

  managed {
    domains = compact([
      var.domain_name,
      var.domain_name != "" ? "www.${var.domain_name}" : "",
      var.domain_name != "" ? "api.${var.domain_name}" : "",
      var.frontend_domain_name != "" && var.frontend_domain_name != var.domain_name ? var.frontend_domain_name : ""
    ])
  }

  count = var.domain_name != "" ? 1 : 0

  lifecycle {
    create_before_destroy = true
  }
}

# Self-signed SSL certificate for IP-based access (when no domain)
resource "google_compute_ssl_certificate" "self_signed_cert" {
  name        = "${var.app_name}-self-signed-cert"
  private_key = tls_private_key.ssl_key[0].private_key_pem
  certificate = tls_self_signed_cert.ssl_cert[0].cert_pem

  count = var.domain_name == "" ? 1 : 0

  lifecycle {
    create_before_destroy = true
  }
}

# Generate private key for self-signed certificate
resource "tls_private_key" "ssl_key" {
  algorithm = "RSA"
  rsa_bits  = 2048

  count = var.domain_name == "" ? 1 : 0
}

# Generate self-signed certificate
resource "tls_self_signed_cert" "ssl_cert" {
  private_key_pem = tls_private_key.ssl_key[0].private_key_pem

  subject {
    common_name  = "ai-explorer"
    organization = "AI Explorer"
  }

  validity_period_hours = 8760 # 1 year

  allowed_uses = [
    "key_encipherment",
    "digital_signature",
    "server_auth",
  ]

  count = var.domain_name == "" ? 1 : 0
}

# URL map for routing (unified for backend API and frontend)
resource "google_compute_url_map" "url_map" {
  name            = "${var.app_name}-url-map"
  default_service = var.frontend_domain_name != "" ? google_compute_backend_bucket.frontend_backend.id : google_compute_backend_service.backend_service.id

  # Main domain routing
  host_rule {
    hosts        = var.domain_name != "" ? [var.domain_name, "www.${var.domain_name}"] : ["*"]
    path_matcher = "main_paths"
  }

  # Frontend domain routing (if different from main domain)
  dynamic "host_rule" {
    for_each = var.frontend_domain_name != "" && var.frontend_domain_name != var.domain_name ? [1] : []
    content {
      hosts        = [var.frontend_domain_name]
      path_matcher = "frontend_paths"
    }
  }

  # API subdomain routing
  dynamic "host_rule" {
    for_each = var.domain_name != "" ? [1] : []
    content {
      hosts        = ["api.${var.domain_name}"]
      path_matcher = "api_paths"
    }
  }

  # Main domain path matcher
  path_matcher {
    name            = "main_paths"
    default_service = var.frontend_domain_name != "" ? google_compute_backend_bucket.frontend_backend.id : google_compute_backend_service.backend_service.id

    # API routes go to backend service
    path_rule {
      paths   = ["/api/*"]
      service = google_compute_backend_service.backend_service.id
    }

    # Backend-specific routes
    path_rule {
      paths   = ["/health", "/docs", "/openapi.json"]
      service = google_compute_backend_service.backend_service.id
    }

    # Static assets from frontend bucket (if frontend is configured)
    dynamic "path_rule" {
      for_each = var.frontend_domain_name != "" ? [1] : []
      content {
        paths   = ["/static/*", "/assets/*", "/_next/static/*", "/favicon.ico", "/robots.txt", "/sitemap.xml"]
        service = google_compute_backend_bucket.frontend_backend.id
      }
    }

    # Default route - frontend if configured, otherwise backend
    path_rule {
      paths   = ["/*"]
      service = var.frontend_domain_name != "" ? google_compute_backend_bucket.frontend_backend.id : google_compute_backend_service.backend_service.id
    }
  }

  # Frontend-specific path matcher (when using separate frontend domain)
  dynamic "path_matcher" {
    for_each = var.frontend_domain_name != "" && var.frontend_domain_name != var.domain_name ? [1] : []
    content {
      name            = "frontend_paths"
      default_service = google_compute_backend_bucket.frontend_backend.id

      # API requests should still go to backend
      path_rule {
        paths   = ["/api/*"]
        service = google_compute_backend_service.backend_service.id
      }

      # All other paths serve from frontend bucket
      path_rule {
        paths   = ["/*"]
        service = google_compute_backend_bucket.frontend_backend.id
      }
    }
  }

  # API-specific path matcher
  dynamic "path_matcher" {
    for_each = var.domain_name != "" ? [1] : []
    content {
      name            = "api_paths"
      default_service = google_compute_backend_service.backend_service.id

      # All API subdomain traffic goes to backend
      path_rule {
        paths   = ["/*"]
        service = google_compute_backend_service.backend_service.id
      }
    }
  }
}

# Backend services
resource "google_compute_backend_service" "backend_service" {
  name                  = "${var.app_name}-api-service"
  protocol              = "HTTP"
  timeout_sec           = 30
  enable_cdn            = false
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.backend_neg.id
  }

  # Note: Health checks are not supported for serverless NEG backends (Cloud Run)
  # Backend service for Cloud Run is automatically managed by Google
}

# MCP service is internal only - no external backend service needed
# Backend service communicates with MCP directly via internal networking

# Network Endpoint Groups for Cloud Run services
resource "google_compute_region_network_endpoint_group" "backend_neg" {
  name                  = "${var.app_name}-api-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region

  cloud_run {
    service = google_cloud_run_v2_service.backend_api.name
  }
}

# HTTPS proxy - always created (uses managed cert for domain, self-signed for IP)
resource "google_compute_target_https_proxy" "https_proxy" {
  name             = "${var.app_name}-https-proxy"
  url_map          = google_compute_url_map.url_map.id
  ssl_certificates = var.domain_name != "" ? [google_compute_managed_ssl_certificate.ssl_cert[0].id] : [google_compute_ssl_certificate.self_signed_cert[0].id]
}

# HTTP proxy (for redirect to HTTPS)
resource "google_compute_target_http_proxy" "http_proxy" {
  name    = "${var.app_name}-http-proxy"
  url_map = google_compute_url_map.redirect_url_map.id
}

# URL map for HTTP to HTTPS redirect
resource "google_compute_url_map" "redirect_url_map" {
  name = "${var.app_name}-redirect-url-map"

  default_url_redirect {
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    https_redirect         = true
    strip_query            = false
  }
}

# Global forwarding rules
# HTTPS forwarding rule - always created
resource "google_compute_global_forwarding_rule" "https_forwarding_rule" {
  name       = "${var.app_name}-https-forwarding-rule"
  target     = google_compute_target_https_proxy.https_proxy.id
  port_range = "443"
  ip_address = google_compute_global_address.lb_ip.address
}

# HTTP forwarding rule - always created (redirects to HTTPS)
resource "google_compute_global_forwarding_rule" "http_forwarding_rule" {
  name       = "${var.app_name}-http-forwarding-rule"
  target     = google_compute_target_http_proxy.http_proxy.id
  port_range = "80"
  ip_address = google_compute_global_address.lb_ip.address
}
