terraform {
  required_version = ">= 1.5.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.35"
    }
  }
}

variable "kube_context" {
  type        = string
  default     = ""
  description = "Kubeconfig context (Rancher Desktop, Docker Desktop, ...). Empty uses current-context."
}

provider "kubernetes" {
  config_path    = pathexpand("~/.kube/config")
  config_context = var.kube_context == "" ? null : var.kube_context
}

variable "openrouter_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

module "app" {
  source             = "../modules/local-app"
  openrouter_api_key = var.openrouter_api_key
}

output "url" {
  value = module.app.url
}
