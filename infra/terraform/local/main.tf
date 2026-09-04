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

variable "https_proxy" {
  type    = string
  default = ""
}

variable "http_proxy" {
  type    = string
  default = ""
}

variable "no_proxy" {
  type    = string
  default = "127.0.0.1,localhost,::1"
}

module "app" {
  source             = "../modules/local-app"
  openrouter_api_key = var.openrouter_api_key
  https_proxy        = var.https_proxy
  http_proxy         = var.http_proxy
  no_proxy           = var.no_proxy
}

output "url" {
  value = module.app.url
}
