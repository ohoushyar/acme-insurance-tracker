terraform {
  required_version = ">= 1.5.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.35"
    }
  }
}

variable "namespace" {
  type    = string
  default = "default"
}

variable "api_image" {
  type    = string
  default = "insurance-tracker-api:latest"
}

variable "frontend_image" {
  type    = string
  default = "insurance-tracker-frontend:latest"
}

variable "postgres_password" {
  type      = string
  default   = "postgres"
  sensitive = true
}

variable "app_db_password" {
  type      = string
  default   = "app"
  sensitive = true
}

variable "s3_access_key" {
  type      = string
  default   = "minioadmin"
  sensitive = true
}

variable "s3_secret_key" {
  type      = string
  default   = "minioadmin"
  sensitive = true
}

variable "openrouter_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "openrouter_model" {
  type    = string
  default = "openai/gpt-4o-mini"
}

locals {
  labels = {
    app = "insurance-tracker"
  }
  database_url       = "postgresql+asyncpg://app:${var.app_db_password}@127.0.0.1:5432/insurance"
  admin_database_url = "postgresql+asyncpg://postgres:${var.postgres_password}@127.0.0.1:5432/insurance"
}

resource "kubernetes_config_map_v1" "postgres_init" {
  metadata {
    name      = "postgres-init"
    namespace = var.namespace
    labels    = local.labels
  }
  data = {
    "01-app-role.sql" = <<-SQL
      DO $$$$
      BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app') THEN
          CREATE ROLE app LOGIN PASSWORD '${var.app_db_password}';
        END IF;
      END
      $$$$;
      GRANT CONNECT ON DATABASE insurance TO app;
      GRANT USAGE, CREATE ON SCHEMA public TO app;
      ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app;
      ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app;
    SQL
  }
}

resource "kubernetes_config_map_v1" "app" {
  metadata {
    name      = "insurance-tracker"
    namespace = var.namespace
    labels    = local.labels
  }
  data = {
    SESSION_TTL_SECONDS   = "604800"
    SESSION_COOKIE_SECURE = "false"
    LOG_LEVEL             = "info"
    S3_ENDPOINT           = "http://127.0.0.1:9000"
    S3_BUCKET             = "insurance-docs"
    S3_REGION             = "us-east-1"
    OPENROUTER_MODEL      = var.openrouter_model
    DATABASE_URL          = local.database_url
    ADMIN_DATABASE_URL    = local.admin_database_url
    REDIS_URL             = "redis://127.0.0.1:6379/0"
    DRAMATIQ_REDIS_URL    = "redis://127.0.0.1:6379/2"
  }
}

resource "kubernetes_secret_v1" "app" {
  metadata {
    name      = "insurance-tracker"
    namespace = var.namespace
    labels    = local.labels
  }
  data = {
    POSTGRES_PASSWORD  = var.postgres_password
    APP_DB_PASSWORD    = var.app_db_password
    S3_ACCESS_KEY      = var.s3_access_key
    S3_SECRET_KEY      = var.s3_secret_key
    OPENROUTER_API_KEY = var.openrouter_api_key
  }
}

resource "kubernetes_deployment_v1" "stack" {
  metadata {
    name      = "insurance-tracker"
    namespace = var.namespace
    labels    = local.labels
  }
  spec {
    replicas = 1
    selector {
      match_labels = local.labels
    }
    strategy {
      type = "Recreate"
    }
    template {
      metadata {
        labels = local.labels
      }
      spec {
        restart_policy = "Always"

        volume {
          name = "postgres-data"
          empty_dir {}
        }
        volume {
          name = "minio-data"
          empty_dir {}
        }
        volume {
          name = "postgres-init"
          config_map {
            name         = kubernetes_config_map_v1.postgres_init.metadata[0].name
            default_mode = "0755"
          }
        }

        container {
          name  = "postgres"
          image = "postgres:16"
          port {
            container_port = 5432
          }
          env {
            name  = "POSTGRES_USER"
            value = "postgres"
          }
          env {
            name  = "PGDATA"
            value = "/var/lib/postgresql/data/pgdata"
          }
          env {
            name  = "POSTGRES_DB"
            value = "insurance"
          }
          env {
            name = "POSTGRES_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.app.metadata[0].name
                key  = "POSTGRES_PASSWORD"
              }
            }
          }
          env {
            name = "APP_DB_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.app.metadata[0].name
                key  = "APP_DB_PASSWORD"
              }
            }
          }
          volume_mount {
            name       = "postgres-data"
            mount_path = "/var/lib/postgresql/data"
          }
          volume_mount {
            name       = "postgres-init"
            mount_path = "/docker-entrypoint-initdb.d"
          }
        }

        container {
          name  = "redis"
          image = "redis:7"
          port {
            container_port = 6379
          }
        }

        container {
          name  = "minio"
          image = "minio/minio:latest"
          args  = ["server", "/data", "--console-address", ":9001"]
          port {
            container_port = 9000
          }
          port {
            container_port = 9001
          }
          env {
            name = "MINIO_ROOT_USER"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.app.metadata[0].name
                key  = "S3_ACCESS_KEY"
              }
            }
          }
          env {
            name = "MINIO_ROOT_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.app.metadata[0].name
                key  = "S3_SECRET_KEY"
              }
            }
          }
          volume_mount {
            name       = "minio-data"
            mount_path = "/data"
          }
        }

        container {
          name    = "minio-init"
          image   = "minio/mc:latest"
          command = ["/bin/sh", "-c"]
          args = [
            <<-CMD
              until mc alias set local http://127.0.0.1:9000 "$$S3_ACCESS_KEY" "$$S3_SECRET_KEY"; do
                sleep 1
              done
              mc mb --ignore-existing local/insurance-docs
              sleep infinity
            CMD
          ]
          env {
            name = "S3_ACCESS_KEY"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.app.metadata[0].name
                key  = "S3_ACCESS_KEY"
              }
            }
          }
          env {
            name = "S3_SECRET_KEY"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.app.metadata[0].name
                key  = "S3_SECRET_KEY"
              }
            }
          }
        }

        container {
          name              = "api"
          image             = var.api_image
          image_pull_policy = "IfNotPresent"
          command           = ["/bin/sh", "-c"]
          args = [
            <<-CMD
              python /app/scripts/wait_for_tcp.py 127.0.0.1 5432 90 &&
              python /app/scripts/wait_for_postgres.py 90 &&
              python /app/scripts/wait_for_tcp.py 127.0.0.1 6379 90 &&
              python /app/scripts/wait_for_tcp.py 127.0.0.1 9000 90 &&
              alembic upgrade head &&
              uvicorn app.main:app --host 0.0.0.0 --port 8000
            CMD
          ]
          port {
            container_port = 8000
          }
          env_from {
            config_map_ref {
              name = kubernetes_config_map_v1.app.metadata[0].name
            }
          }
          env_from {
            secret_ref {
              name = kubernetes_secret_v1.app.metadata[0].name
            }
          }
        }

        container {
          name              = "worker"
          image             = var.api_image
          image_pull_policy = "IfNotPresent"
          command           = ["/bin/sh", "-c"]
          args = [
            <<-CMD
              python /app/scripts/wait_for_tcp.py 127.0.0.1 5432 90 &&
              python /app/scripts/wait_for_postgres.py 90 &&
              python /app/scripts/wait_for_tcp.py 127.0.0.1 6379 90 &&
              python /app/scripts/wait_for_tcp.py 127.0.0.1 9000 90 &&
              dramatiq app.queue.actors --processes 1 --threads 2
            CMD
          ]
          env_from {
            config_map_ref {
              name = kubernetes_config_map_v1.app.metadata[0].name
            }
          }
          env_from {
            secret_ref {
              name = kubernetes_secret_v1.app.metadata[0].name
            }
          }
        }

        container {
          name              = "frontend"
          image             = var.frontend_image
          image_pull_policy = "IfNotPresent"
          port {
            container_port = 80
          }
        }
      }
    }
  }
  timeouts {
    create = "10m"
    update = "10m"
  }
}

resource "kubernetes_service_v1" "frontend" {
  metadata {
    name      = "insurance-tracker"
    namespace = var.namespace
    labels    = local.labels
  }
  spec {
    type     = "ClusterIP"
    selector = local.labels
    port {
      name        = "http"
      port        = 80
      target_port = 80
    }
  }
  wait_for_load_balancer = false
}

output "url" {
  value = "kubectl port-forward svc/insurance-tracker 8080:80  # then http://localhost:8080"
}
