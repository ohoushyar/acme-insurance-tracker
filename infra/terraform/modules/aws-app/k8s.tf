resource "kubernetes_namespace_v1" "app" {
  metadata {
    name   = local.namespace
    labels = local.labels
  }
}

resource "kubernetes_service_account_v1" "app" {
  metadata {
    name      = "insurance-tracker"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels    = local.labels
    annotations = {
      "eks.amazonaws.com/role-arn" = aws_iam_role.app.arn
    }
  }
}

resource "kubernetes_config_map_v1" "app" {
  metadata {
    name      = "insurance-tracker"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels    = local.labels
  }
  data = {
    SESSION_TTL_SECONDS   = "604800"
    SESSION_COOKIE_SECURE = "true"
    LOG_LEVEL             = "info"
    S3_ENDPOINT           = local.s3_endpoint
    S3_BUCKET             = aws_s3_bucket.docs.bucket
    S3_REGION             = var.aws_region
    OPENROUTER_MODEL      = var.openrouter_model
    REDIS_URL             = "redis://redis:6379/0"
    DRAMATIQ_REDIS_URL    = "redis://redis:6379/2"
    EMAIL_BACKEND         = var.ses_from_address != "" ? "ses" : ""
    EMAIL_FROM            = var.ses_from_address
    APP_PUBLIC_URL        = var.app_public_url
  }
}

resource "kubernetes_secret_v1" "app" {
  metadata {
    name      = "insurance-tracker"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels    = local.labels
  }
  data = {
    DATABASE_URL       = "postgresql+asyncpg://app:${random_password.app_db.result}@postgres:5432/insurance"
    ADMIN_DATABASE_URL = "postgresql+asyncpg://postgres:${random_password.postgres.result}@postgres:5432/insurance"
    POSTGRES_PASSWORD  = random_password.postgres.result
    APP_DB_PASSWORD    = random_password.app_db.result
    OPENROUTER_API_KEY = var.openrouter_api_key
  }
}

resource "kubernetes_config_map_v1" "postgres_init" {
  metadata {
    name      = "postgres-init"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels    = local.labels
  }
  data = {
    "01-app-role.sql" = <<-SQL
      DO $$$$
      BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app') THEN
          CREATE ROLE app LOGIN PASSWORD '${random_password.app_db.result}';
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

resource "kubernetes_service_v1" "postgres" {
  metadata {
    name      = "postgres"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels    = { app = "postgres" }
  }
  spec {
    selector = { app = "postgres" }
    port {
      port        = 5432
      target_port = 5432
    }
  }
}

resource "kubernetes_stateful_set_v1" "postgres" {
  metadata {
    name      = "postgres"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels    = { app = "postgres" }
  }
  spec {
    service_name = "postgres"
    replicas     = 1
    selector {
      match_labels = { app = "postgres" }
    }
    template {
      metadata {
        labels = { app = "postgres" }
      }
      spec {
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
            name       = "data"
            mount_path = "/var/lib/postgresql/data"
          }
          volume_mount {
            name       = "init"
            mount_path = "/docker-entrypoint-initdb.d"
          }
        }
        volume {
          name = "init"
          config_map {
            name         = kubernetes_config_map_v1.postgres_init.metadata[0].name
            default_mode = "0755"
          }
        }
      }
    }
    volume_claim_template {
      metadata {
        name = "data"
      }
      spec {
        access_modes       = ["ReadWriteOnce"]
        storage_class_name = "gp3"
        resources {
          requests = {
            storage = "10Gi"
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "redis" {
  metadata {
    name      = "redis"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels    = { app = "redis" }
  }
  spec {
    selector = { app = "redis" }
    port {
      port        = 6379
      target_port = 6379
    }
  }
}

resource "kubernetes_deployment_v1" "redis" {
  metadata {
    name      = "redis"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels    = { app = "redis" }
  }
  spec {
    replicas = 1
    selector {
      match_labels = { app = "redis" }
    }
    template {
      metadata {
        labels = { app = "redis" }
      }
      spec {
        container {
          name  = "redis"
          image = "redis:7"
          port {
            container_port = 6379
          }
        }
      }
    }
  }
}

resource "kubernetes_job_v1" "migrate" {
  metadata {
    name      = "migrate-${lower(replace(substr(var.image_tag, 0, 12), "/[^a-z0-9-]/", "x"))}"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels    = local.labels
  }
  spec {
    ttl_seconds_after_finished = 600
    backoff_limit              = 5
    template {
      metadata {
        labels = { app = "migrate" }
      }
      spec {
        restart_policy       = "OnFailure"
        service_account_name = kubernetes_service_account_v1.app.metadata[0].name
        container {
          name    = "migrate"
          image   = local.api_image
          command = ["/bin/sh", "-c"]
          args = [
            <<-CMD
              python /app/scripts/wait_for_tcp.py postgres 5432 120 &&
              python /app/scripts/wait_for_postgres.py 120 &&
              alembic upgrade head
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
      }
    }
  }
  wait_for_completion = true
  timeouts {
    create = "10m"
    update = "10m"
  }
  depends_on = [
    kubernetes_stateful_set_v1.postgres,
    kubernetes_deployment_v1.redis,
  ]
}

resource "kubernetes_service_v1" "api" {
  metadata {
    name      = "api"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels    = { app = "api" }
  }
  spec {
    selector = { app = "api" }
    port {
      port        = 8000
      target_port = 8000
    }
  }
}

resource "kubernetes_deployment_v1" "api" {
  metadata {
    name      = "api"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels    = { app = "api" }
  }
  spec {
    replicas = var.api_replicas
    selector {
      match_labels = { app = "api" }
    }
    template {
      metadata {
        labels = { app = "api" }
      }
      spec {
        service_account_name = kubernetes_service_account_v1.app.metadata[0].name
        container {
          name  = "api"
          image = local.api_image
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
          readiness_probe {
            http_get {
              path = "/docs"
              port = 8000
            }
            initial_delay_seconds = 10
            period_seconds        = 10
          }
        }
      }
    }
  }
  depends_on = [kubernetes_job_v1.migrate]
}

resource "kubernetes_deployment_v1" "worker" {
  metadata {
    name      = "worker"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels    = { app = "worker" }
  }
  spec {
    replicas = var.worker_replicas
    selector {
      match_labels = { app = "worker" }
    }
    template {
      metadata {
        labels = { app = "worker" }
      }
      spec {
        service_account_name = kubernetes_service_account_v1.app.metadata[0].name
        container {
          name    = "worker"
          image   = local.api_image
          command = ["dramatiq", "app.queue.actors", "--processes", "1", "--threads", "2"]
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
      }
    }
  }
  depends_on = [kubernetes_job_v1.migrate]
}

resource "kubernetes_ingress_v1" "api" {
  metadata {
    name      = "api"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels    = local.labels
    annotations = {
      "kubernetes.io/ingress.class"                = "alb"
      "alb.ingress.kubernetes.io/scheme"           = "internet-facing"
      "alb.ingress.kubernetes.io/target-type"      = "ip"
      "alb.ingress.kubernetes.io/listen-ports"     = "[{\"HTTP\":80}]"
      "alb.ingress.kubernetes.io/healthcheck-path" = "/docs"
      "alb.ingress.kubernetes.io/group.name"       = local.name_prefix
    }
  }
  spec {
    ingress_class_name = "alb"
    rule {
      http {
        path {
          path      = "/api"
          path_type = "Prefix"
          backend {
            service {
              name = kubernetes_service_v1.api.metadata[0].name
              port {
                number = 8000
              }
            }
          }
        }
        path {
          path      = "/docs"
          path_type = "Prefix"
          backend {
            service {
              name = kubernetes_service_v1.api.metadata[0].name
              port {
                number = 8000
              }
            }
          }
        }
        path {
          path      = "/openapi.json"
          path_type = "Prefix"
          backend {
            service {
              name = kubernetes_service_v1.api.metadata[0].name
              port {
                number = 8000
              }
            }
          }
        }
      }
    }
  }
  wait_for_load_balancer = true
  timeouts {
    create = "10m"
  }
  depends_on = [kubernetes_deployment_v1.api]
}
