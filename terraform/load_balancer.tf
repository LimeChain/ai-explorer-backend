# Global IP address for the load balancer
resource "google_compute_global_address" "lb_ip" {
  name = "${var.app_name}-lb-ip"
}

# SSL certificate (managed - for custom domain)
resource "google_compute_managed_ssl_certificate" "ssl_cert" {
  name = "${var.app_name}-ssl-cert"

  managed {
    domains = [var.domain_name]
  }

  count = var.domain_name != "" ? 1 : 0
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

# URL map for routing
resource "google_compute_url_map" "url_map" {
  name            = "${var.app_name}-url-map"
  default_service = google_compute_backend_service.backend_service.id

  host_rule {
    hosts        = var.domain_name != "" ? [var.domain_name] : ["*"]
    path_matcher = "allpaths"
  }

  path_matcher {
    name            = "allpaths"
    default_service = google_compute_backend_service.backend_service.id

    path_rule {
      paths   = ["/api/*"]
      service = google_compute_backend_service.backend_service.id
    }

    path_rule {
      paths   = ["/health", "/docs", "/openapi.json", "/"]
      service = google_compute_backend_service.backend_service.id
    }

    # MCP service is internal only - not exposed through load balancer
    # Backend service will communicate with MCP internally
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
