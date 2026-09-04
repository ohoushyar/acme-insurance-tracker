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

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type = string
}

variable "image_tag" {
  type = string
}

variable "openrouter_api_key" {
  type      = string
  sensitive = true
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

provider "aws" {
  region = var.aws_region
}

data "terraform_remote_state" "platform" {
  backend = "local"
  config = {
    path = "${path.module}/../platform/terraform.tfstate"
  }
}

data "aws_eks_cluster_auth" "this" {
  name = data.terraform_remote_state.platform.outputs.cluster_name
}

provider "kubernetes" {
  host                   = data.terraform_remote_state.platform.outputs.cluster_endpoint
  cluster_ca_certificate = base64decode(data.terraform_remote_state.platform.outputs.cluster_certificate_authority_data)
  token                  = data.aws_eks_cluster_auth.this.token
}

module "app" {
  source             = "../../modules/aws-app"
  environment        = var.environment
  cluster_name       = data.terraform_remote_state.platform.outputs.cluster_name
  oidc_provider_arn  = data.terraform_remote_state.platform.outputs.oidc_provider_arn
  oidc_issuer        = data.terraform_remote_state.platform.outputs.oidc_issuer
  aws_region         = data.terraform_remote_state.platform.outputs.aws_region
  image_tag          = var.image_tag
  ecr_repository_url = data.terraform_remote_state.platform.outputs.ecr_repository_url
  openrouter_api_key = var.openrouter_api_key
  ses_from_address   = var.ses_from_address
  ses_hosted_zone_id = var.ses_hosted_zone_id
  app_public_url     = var.app_public_url
}

output "frontend_bucket" {
  value = module.app.frontend_bucket
}

output "docs_bucket" {
  value = module.app.docs_bucket
}

output "cloudfront_distribution_id" {
  value = module.app.cloudfront_distribution_id
}

output "cloudfront_url" {
  value = module.app.cloudfront_url
}

output "namespace" {
  value = module.app.namespace
}

output "ses_dkim_tokens" {
  value = module.app.ses_dkim_tokens
}
