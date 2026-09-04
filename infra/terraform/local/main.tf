terraform {
  required_version = ">= 1.5.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.35"
    }
  }
}

provider "kubernetes" {
  config_path    = pathexpand("~/.kube/config")
  config_context = "k3d-insurance-tracker"
}

variable "openrouter_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

module "app" {
  source             = "../modules/k3d-app"
  openrouter_api_key = var.openrouter_api_key
}

output "url" {
  value = module.app.url
}
