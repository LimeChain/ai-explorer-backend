# Firewall rules for the AI Explorer infrastructure

# Allow internal communication within VPC
resource "google_compute_firewall" "allow_internal" {
  name    = "${var.app_name}-allow-internal"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = ["10.0.0.0/24", "10.8.0.0/28"]
  target_tags   = ["${var.app_name}-internal"]

  description = "Allow internal communication within VPC"
}

# Allow VPC Connector to access Cloud SQL
resource "google_compute_firewall" "allow_vpc_connector_to_sql" {
  name    = "${var.app_name}-allow-vpc-connector-sql"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }

  source_ranges = ["10.8.0.0/28"]
  target_tags   = ["${var.app_name}-database"]

  description = "Allow VPC Connector to access Cloud SQL PostgreSQL"
}

# Allow Load Balancer health checks to Cloud Run services
resource "google_compute_firewall" "allow_lb_to_cloud_run" {
  name    = "${var.app_name}-allow-lb-cloud-run"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["8000", "8001", "8002"]
  }

  # Google Cloud Load Balancer health check source ranges
  source_ranges = [
    "130.211.0.0/22",
    "35.191.0.0/16"
  ]

  target_tags = ["${var.app_name}-service"]

  description = "Allow Load Balancer health checks to reach Cloud Run services"
}

# Allow HTTPS traffic from internet
resource "google_compute_firewall" "allow_https" {
  name    = "${var.app_name}-allow-https"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["${var.app_name}-https-server"]

  description = "Allow HTTPS traffic from internet"
}

# Allow HTTP traffic from internet (for redirect to HTTPS)
resource "google_compute_firewall" "allow_http" {
  name    = "${var.app_name}-allow-http"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["80"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["${var.app_name}-http-server"]

  description = "Allow HTTP traffic from internet (redirects to HTTPS)"
}
