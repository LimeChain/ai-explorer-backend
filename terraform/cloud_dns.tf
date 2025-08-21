# Cloud DNS managed zone
resource "google_dns_managed_zone" "main_zone" {
  name        = "${replace(var.domain_name, ".", "-")}-zone"
  dns_name    = "${var.domain_name}."
  description = "DNS zone for ${var.domain_name}"

  labels = {
    environment = var.environment
    app         = var.app_name
  }

  count = var.domain_name != "" ? 1 : 0
}

# A record for main domain pointing to load balancer
resource "google_dns_record_set" "main_domain_a" {
  name = google_dns_managed_zone.main_zone[0].dns_name
  type = "A"
  ttl  = 300

  managed_zone = google_dns_managed_zone.main_zone[0].name

  rrdatas = [google_compute_global_address.lb_ip.address]

  count = var.domain_name != "" ? 1 : 0
}

# A record for www subdomain
resource "google_dns_record_set" "www_domain_a" {
  name = "www.${google_dns_managed_zone.main_zone[0].dns_name}"
  type = "A"
  ttl  = 300

  managed_zone = google_dns_managed_zone.main_zone[0].name

  rrdatas = [google_compute_global_address.lb_ip.address]

  count = var.domain_name != "" ? 1 : 0
}

# A record for API subdomain
resource "google_dns_record_set" "api_domain_a" {
  name = "api.${google_dns_managed_zone.main_zone[0].dns_name}"
  type = "A"
  ttl  = 300

  managed_zone = google_dns_managed_zone.main_zone[0].name

  rrdatas = [google_compute_global_address.lb_ip.address]

  count = var.domain_name != "" ? 1 : 0
}
