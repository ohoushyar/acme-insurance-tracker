# Deployment

## AWS (staging / production)

Shared EKS cluster; per-env namespace, S3 buckets (SPA + PDFs), and
CloudFront. API and worker run at `replicas=2`. Postgres and Redis stay
in-cluster (1 replica).

```bash
make deploy ENV=staging
make deploy ENV=production

# *** DEMO ONLY ***
make destroy-aws ENV=staging
make destroy-aws ENV=production CONFIRM=yes
# optional: also tear down the shared EKS/VPC after both envs are gone
make destroy-aws ENV=staging DESTROY_CLUSTER=yes
```

Copy `infra/terraform/aws/platform/terraform.tfvars.example` and
`infra/terraform/aws/app/staging.tfvars.example` (or `production`) to
`*.tfvars` if you need non-default region or cluster name. Pass
`OPENROUTER_API_KEY` via `.env` or the environment.

Existing YAML under `k8s/` is a reference only; Terraform owns applied
resources.

## Local Kubernetes

One pod runs API, Dramatiq, Postgres, Redis, MinIO, and nginx on the
cluster `kubectl` currently points at (Rancher Desktop).

```bash
# Kubernetes enabled in Rancher Desktop, then:
kubectl cluster-info
make deploy-local
kubectl port-forward svc/insurance-tracker 8080:80
# http://localhost:8080
make destroy-local
```

`destroy-local` removes the workload only; it does not quit Rancher
Desktop. Requires `kubectl`, Terraform, and Docker (or the Rancher
Desktop docker/nerdctl CLI). If the cluster uses containerd, `nerdctl`
must be on `PATH` (Rancher Desktop: `~/.rd/bin/nerdctl`). If ConfigMaps
or Secrets were left in the cluster from a previous apply (Terraform
state missing), `make deploy-local` imports them instead of failing
with "already exists". `make destroy-local` also deletes leftover
objects labeled `app=insurance-tracker`.