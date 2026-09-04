# Deployment: local Kubernetes + AWS EKS

This plan covers **cluster deploy and teardown** for the insurance
tracker. Product features are unchanged. Compose (`make serve`) stays
the inner-loop path.

## Decisions (surfaced, not silent)

| Topic | Choice | Why |
|---|---|---|
| Orchestration | Terraform | Requested. Makefile bootstraps images/AWS auth and runs apply/destroy. |
| Local cluster | Current kubecontext (Rancher Desktop) | One multi-container pod on the cluster `kubectl` already talks to. |
| AWS compute | One EKS cluster, namespaces `staging` and `production` | Cheaper than two clusters; isolation is namespace + buckets. |
| AWS app HA | API `replicas=2`, worker `replicas=2` | Availability for stateless app pods. |
| AWS data plane | In-cluster Postgres + Redis, 1 replica each | Confirmed; no RDS/ElastiCache in this step. |
| SPA hosting | S3 + CloudFront | Same-origin front door so the session cookie still works. |
| PDF storage | MinIO in local k8s; real S3 in AWS | Existing `S3_*` settings; IRSA in AWS (no static keys). |
| Migrations | Kubernetes Job (AWS); wait+alembic in the local API container | Two API replicas must not race `alembic upgrade`. |
| Teardown | `make destroy-local` / `make destroy-aws` | Idempotent cleanup; production requires `CONFIRM=yes`. |

## Public front door

The SPA calls relative `/api/v1/...` with `credentials: "include"`.
CloudFront is the HTTPS host: `/` → frontend bucket, `/api/*` → ALB →
API pods. Local is HTTP via `kubectl port-forward`
(`SESSION_COOKIE_SECURE=false`).

```
Browser → CloudFront
            /        → S3 frontend bucket
            /api/*   → ALB → EKS API (x2)
API/worker → Postgres, Redis, S3 docs bucket
```

## Layout

```
infra/terraform/
  modules/
    local-app/        # local all-in-one Deployment + ClusterIP Service
    aws-platform/     # VPC, EKS, ECR, IRSA for ALB/EBS, ALB controller
    aws-app/          # per-env S3 x2, CloudFront, namespace, workloads
  local/              # current kubecontext (Rancher Desktop)
  aws/
    platform/         # shared cluster state
    app/              # workspaces staging|production
```

**New Terraform dependencies:** AWS provider, kubernetes provider, helm
provider, `terraform-aws-modules/vpc/aws`, `terraform-aws-modules/eks/aws`,
`terraform-aws-modules/iam/aws` (IRSA). State files and `*.tfvars`
(except `*.example`) are gitignored. State is local files in this step.

Existing `k8s/*.yaml` stay as a reference; Terraform owns applied
resources.

## Local Kubernetes

`make deploy-local` uses the **current kubectl context** (Rancher
Desktop: `rancher-desktop`). It does not create a cluster.

1. Confirm `kubectl cluster-info` works (start Rancher Desktop first).
2. Build API image; frontend image with `API_UPSTREAM=127.0.0.1:8000`.
3. Load images into the cluster runtime (docker image store, or
   `nerdctl -n k8s.io` for containerd / Rancher Desktop).
4. Import any leftover ConfigMaps/Secrets/Deployment/Service already in
   the cluster (lost local Terraform state), then `terraform apply` in
   `infra/terraform/local`.
5. `kubectl port-forward svc/insurance-tracker 8080:80`.

Containers share localhost (Postgres 5432, Redis 6379, MinIO 9000,
API 8000, nginx 80). The API waits for a SQL connection, ensures the
`app` role, then runs `alembic upgrade head` and uvicorn. Secrets
default to Compose-like values; `OPENROUTER_API_KEY` comes from `.env`.

`make destroy-local`: terraform destroy of the workload only, then
`kubectl delete -l app=insurance-tracker` for objects that were not in
state. It does **not** shut down Rancher Desktop. Idempotent if already
gone. Does not touch Compose volumes.

If the worker log stops at `extraction_llm_invoke` and OpenRouter's
dashboard shows no request, the pod never completed HTTPS to
`openrouter.ai`. Two local causes:

1. CoreDNS `ndots:5` plus Rancher Desktop's search domain `lan`:
   `openrouter.ai` is looked up as `openrouter.ai.lan` and the LAN
   gateway answers `192.168.1.1`. The local pod sets
   `dnsConfig.options ndots:1` and omits the `lan` search domain.
2. TLS intercept / missing proxy. Local deploy uses `hostNetwork`,
   sets `OPENSSL_CONF` (TLS 1.2, security level 1) so httpx timeouts
   still fire, and forwards `HTTPS_PROXY` / `HTTP_PROXY` from the
   host. A probe logs `openrouter_probe_ok` or
   `openrouter_probe_failed` with the exception type before the LLM
   call.

`NO_PROXY` defaults to `127.0.0.1,localhost,::1` so MinIO is not sent
through a corporate proxy. After `make deploy-local`, look for the
probe line before `extraction_llm_invoke`. Dramatiq's actor time
limit is 3 minutes and `TimeLimitExceeded` marks the document failed
without retrying.

Local k8s and Compose set `OPENROUTER_TLS_SECLEVEL=1` so OpenSSL 3 still
verifies `openrouter.ai` but accepts TLS-intercept leaf certs with
1024-bit RSA (`EE certificate key too weak`). AWS leaves the default
(`2`). Certificate verification stays on; this is not `verify=False`.

## AWS (staging / production)

`make deploy ENV=staging` (or `production`):

1. Apply **platform** (VPC, EKS, ECR, EBS CSI, AWS Load Balancer
   Controller). Shared; idempotent.
2. Build/push API image to ECR (`IMAGE_TAG` = git sha). Worker uses
   the same image, different command.
3. Apply **app** for `$ENV` (namespace, secrets, Postgres, Redis, migrate
   Job, API x2, worker x2, Ingress/ALB, S3 buckets, CloudFront).
4. `npm run build` and `aws s3 sync` the SPA; CloudFront invalidation.

`make destroy-aws ENV=staging` (aliases: `destroy-staging`,
`destroy-production`):

1. Fail if `ENV` unset. `ENV=production` also requires `CONFIRM=yes`.
2. Empty that env’s S3 buckets so Terraform can delete them.
3. Destroy **app** (namespace, ALB, PVCs, env CloudFront, env buckets).
4. Does **not** destroy shared EKS/VPC unless
   `DESTROY_CLUSTER=yes` and the other env’s state is empty.

## App change: S3 factory

Empty `S3_ENDPOINT` still selects `InMemoryDocumentStore` (tests).
AWS sets `S3_ENDPOINT=https://s3.<region>.amazonaws.com`, omits access
keys (IRSA / default credential chain), and uses virtual-hosted
addressing. MinIO keeps path-style + static keys.

## Makefile

```
make deploy-local
make destroy-local
make deploy ENV=staging|production
make destroy-aws ENV=staging|production
make destroy-staging
make destroy-production
```

`deploy` / `destroy-aws` fail fast without `ENV`. All are `.PHONY`.
