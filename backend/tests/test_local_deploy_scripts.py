import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL_MODULE = ROOT / "infra/terraform/modules/local-app/main.tf"
DEPLOY_LOCAL = ROOT / "infra/scripts/deploy-local.sh"
DESTROY_LOCAL = ROOT / "infra/scripts/destroy-local.sh"


def test_deploy_local_adopts_every_local_k8s_resource() -> None:
    module = LOCAL_MODULE.read_text()
    script = DEPLOY_LOCAL.read_text()
    resources = re.findall(
        r'^resource "(kubernetes_[^"]+)" "([^"]+)"',
        module,
        flags=re.MULTILINE,
    )
    assert resources
    for kind, name in resources:
        address = f"module.app.{kind}.{name}"
        assert address in script, f"{address} must be imported when it already exists"


def test_destroy_local_deletes_labeled_cluster_leftovers() -> None:
    script = DESTROY_LOCAL.read_text()
    assert "app=insurance-tracker" in script
    assert "kubectl" in script
