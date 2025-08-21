# VPC for private connectivity
resource "google_compute_network" "vpc" {
  name                    = "${var.app_name}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "${var.app_name}-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc.id
  private_ip_google_access = true
}

resource "google_compute_subnetwork" "serverless_connector" {
  name          = "${var.app_name}-connector-subnet"
  ip_cidr_range = "10.8.0.0/28"
  region        = var.region
  network       = google_compute_network.vpc.id
  private_ip_google_access = true
}


# Private VPC connection
resource "google_compute_global_address" "private_ip_address" {
  name          = "${var.app_name}-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_address.name]
}


resource "google_compute_router" "vpc_router" {
  name = "${var.app_name}-router"
  network = google_compute_network.vpc.name
  region = var.region
}

resource "google_compute_router_nat" "nat" {
  name = "${var.app_name}-nat"
  router = google_compute_router.vpc_router.name
  region = var.region
  nat_ip_allocate_option = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}
