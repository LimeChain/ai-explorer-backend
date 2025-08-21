# Cloud DNS managed zone
resource "google_dns_managed_zone" "main_zone" {
  name        = "${replace(var.domain_name, ".", "-")}-zone"
  dns_name    = "${var.domain_name}."
  description = "DNS zone for ${var.domain_name}"

  # Enable DNSSEC for security
  dnssec_config {
    state = "on"
  }

  labels = {
    environment = var.environment
    app         = var.app_name
  }

  count = var.domain_name != "" ? 1 : 0
}

# A record for main domain pointing to backend load balancer
resource "google_dns_record_set" "main_domain_a" {
  name = google_dns_managed_zone.main_zone[0].dns_name
  type = "A"
  ttl  = 300

  managed_zone = google_dns_managed_zone.main_zone[0].name

  rrdatas = [google_compute_global_address.lb_ip.address]

  count = var.domain_name != "" ? 1 : 0
}

# A record for www subdomain pointing to backend load balancer
resource "google_dns_record_set" "www_domain_a" {
  name = "www.${google_dns_managed_zone.main_zone[0].dns_name}"
  type = "A"
  ttl  = 300

  managed_zone = google_dns_managed_zone.main_zone[0].name

  rrdatas = [google_compute_global_address.lb_ip.address]

  count = var.domain_name != "" ? 1 : 0
}

# A record for frontend subdomain (if different from main domain)
resource "google_dns_record_set" "frontend_domain_a" {
  name = var.frontend_domain_name != var.domain_name ? "${var.frontend_domain_name}." : "app.${google_dns_managed_zone.main_zone[0].dns_name}"
  type = "A"
  ttl  = 300

  managed_zone = google_dns_managed_zone.main_zone[0].name

  # All traffic goes through the main load balancer for unified routing
  rrdatas = [google_compute_global_address.lb_ip.address]

  count = var.domain_name != "" && var.frontend_domain_name != "" ? 1 : 0
}

# CNAME record for API subdomain
resource "google_dns_record_set" "api_domain_cname" {
  name = "api.${google_dns_managed_zone.main_zone[0].dns_name}"
  type = "CNAME"
  ttl  = 300

  managed_zone = google_dns_managed_zone.main_zone[0].name

  rrdatas = [var.domain_name]

  count = var.domain_name != "" ? 1 : 0
}

# TXT record for domain verification and SPF
resource "google_dns_record_set" "txt_records" {
  name = google_dns_managed_zone.main_zone[0].dns_name
  type = "TXT"
  ttl  = 300

  managed_zone = google_dns_managed_zone.main_zone[0].name

  rrdatas = [
    "\"v=spf1 include:_spf.google.com ~all\"",
    "\"google-site-verification=${var.google_site_verification}\""
  ]

  count = var.domain_name != "" && var.google_site_verification != "" ? 1 : 0
}

# CAA records for certificate authority authorization
resource "google_dns_record_set" "caa_records" {
  name = google_dns_managed_zone.main_zone[0].dns_name
  type = "CAA"
  ttl  = 300

  managed_zone = google_dns_managed_zone.main_zone[0].name

  rrdatas = [
    "0 issue \"letsencrypt.org\"",
    "0 issue \"pki.goog\"",
    "0 iodef \"mailto:admin@${var.domain_name}\""
  ]

  count = var.domain_name != "" ? 1 : 0
}
