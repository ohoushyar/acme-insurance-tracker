terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.35"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

variable "environment" {
  type = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "cluster_name" {
  type = string
}

variable "oidc_provider_arn" {
  type = string
}

variable "oidc_issuer" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "image_tag" {
  type = string
}

variable "ecr_repository_url" {
  type = string
}

variable "openrouter_api_key" {
  type      = string
  sensitive = true
}

variable "openrouter_model" {
  type    = string
  default = "openai/gpt-4o-mini"
}

variable "api_replicas" {
  type    = number
  default = 2
}

variable "worker_replicas" {
  type    = number
  default = 2
}

variable "ses_from_address" {
  type    = string
  default = ""
}

variable "ses_hosted_zone_id" {
  type    = string
  default = ""
}

variable "app_public_url" {
  type    = string
  default = ""
}

data "aws_caller_identity" "current" {}

locals {
  namespace   = var.environment
  name_prefix = "insurance-tracker-${var.environment}"
  api_image   = "${var.ecr_repository_url}:${var.image_tag}"
  docs_bucket = "${local.name_prefix}-docs-${data.aws_caller_identity.current.account_id}"
  web_bucket  = "${local.name_prefix}-web-${data.aws_caller_identity.current.account_id}"
  s3_endpoint = "https://s3.${var.aws_region}.amazonaws.com"
  labels = {
    app         = "insurance-tracker"
    environment = var.environment
  }
}

resource "random_password" "postgres" {
  length  = 24
  special = false
}

resource "random_password" "app_db" {
  length  = 24
  special = false
}
