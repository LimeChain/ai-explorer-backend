variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The GCP region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "The GCP zone"
  type        = string
  default     = "us-central1-a"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "ai-explorer"
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = ""
}

variable "database_instance_tier" {
  description = "The machine type for the database instance"
  type        = string
  default     = "db-custom-1-3840" # 1 CPU, 3.75GB RAM (MVP appropriate)
}

variable "database_disk_size" {
  description = "Database disk size in GB"
  type        = number
  default     = 20
}

variable "database_name" {
  description = "Name of the main database"
  type        = string
  default     = "ai_explorer"
}

variable "database_user" {
  description = "Database user name"
  type        = string
  default     = "ai_explorer_user"
}

variable "cloud_run_max_instances" {
  description = "Maximum number of Cloud Run instances"
  type        = number
  default     = 5
}

variable "cloud_run_memory" {
  description = "Memory allocation for Cloud Run services"
  type        = string
  default     = "1Gi"
}

variable "cloud_run_cpu" {
  description = "CPU allocation for Cloud Run services"
  type        = string
  default     = "1"
}

# Rate limiting configuration
variable "rate_limit_max_requests" {
  description = "Maximum requests per IP per window"
  type        = number
  default     = 5
}

variable "rate_limit_window_seconds" {
  description = "Rate limiting window in seconds"
  type        = number
  default     = 60
}

variable "global_rate_limit_max_requests" {
  description = "Maximum global requests per window"
  type        = number
  default     = 50
}

variable "global_rate_limit_window_seconds" {
  description = "Global rate limiting window in seconds"
  type        = number
  default     = 60
}

#Cost control configuration
variable "per_user_cost_limit" {
  description = "Per user cost limit in USD"
  type        = number
  default     = 2
}

variable "per_user_cost_period_seconds" {
  description = "Per user cost period in seconds"
  type        = number
  default     = 86400
}

variable "global_cost_limit" {
  description = "USD cost limit"
  type        = number
  default     = 200
}

variable "global_cost_period_seconds" {
  description = "Global cost period in secods"
  type        = number
  default     = 31536000
}

# Application configuration
variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"
  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], var.log_level)
    error_message = "Log level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL."
  }
}

variable "llm_provider" {
  description = "LLM provider to use"
  type        = string
  default     = "openai"
}

variable "llm_model" {
  description = "LLM model to use"
  type        = string
  default     = "gpt-4.1"
}

variable "embedding_model" {
  description = "Embedding model to use"
  type        = string
  default     = "text-embedding-3-small"
}

variable "llm_input_cost_per_token" {
  description = "LLM input cost per token in USD"
  type        = number
  default     = 0.0000004
}

variable "llm_output_cost_per_token" {
  description = "LLM output cost per token in USD"
  type        = number
  default     = 0.0000016
}

variable "collection_name" {
  description = "Vector store collection name"
  type        = string
  default     = "sdk_methods"
}

variable "langsmith_tracing" {
  description = "Enable LangSmith tracing"
  type        = bool
  default     = false
}

variable "langsmith_endpoint" {
  description = "LangSmith API endpoint"
  type        = string
  default     = "https://api.smith.langchain.com"
}

variable "allowed_origins" {
  description = "CORS allowed origins"
  type        = list(string)
  default     = ["dev.hederion.com", "hederion.com"]
}

# Redis configuration
variable "redis_memory_size_gb" {
  description = "Redis memory size in GB"
  type        = number
  default     = 1
}

variable "redis_tier" {
  description = "Redis tier (BASIC or STANDARD_HA)"
  type        = string
  default     = "BASIC"
  validation {
    condition     = contains(["BASIC", "STANDARD_HA"], var.redis_tier)
    error_message = "Redis tier must be either BASIC or STANDARD_HA."
  }
}

variable "llm_api_key" {
  description = "LLM API key"
  type        = string
  sensitive   = true
  nullable    = false
}

variable "langsmith_api_key" {
  description = "Langsmith API key"
  type        = string
  sensitive   = true
  nullable    = false
}

variable "saucerswap_api_key" {
  description = "Saucerswap API key"
  type        = string
  sensitive   = true
  nullable    = false
}

# Hgraph GraphQL configuration
variable "hgraph_api_key" {
  description = "Hgraph API key for GraphQL authentication"
  type        = string
  sensitive   = true
  nullable    = false
}

variable "hgraph_endpoint" {
  description = "Hgraph GraphQL endpoint URL"
  type        = string
  default     = "https://mainnet.hedera.api.hgraph.io/v1/graphql"
}


# Frontend configuration
variable "frontend_domain_name" {
  description = "Domain name for the frontend application (e.g., app.example.com)"
  type        = string
  default     = ""
}

variable "frontend_cors_origins" {
  description = "CORS allowed origins for frontend bucket"
  type        = list(string)
  default     = ["*"]
}
