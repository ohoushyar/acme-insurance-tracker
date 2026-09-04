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


def test_local_pod_sets_ndots_one_so_external_names_skip_search() -> None:
    module = LOCAL_MODULE.read_text()

    assert re.search(
        r'dns_config\s*\{[^}]*option\s*\{[^}]*name\s*=\s*"ndots"[^}]*value\s*=\s*"1"',
        module,
        flags=re.DOTALL,
    ), "local pod must set ndots:1 so openrouter.ai is not resolved via search lan"
    assert "lan" not in re.findall(r"searches\s*=\s*\[(.*?)\]", module, flags=re.DOTALL)[
        0
    ]


def test_deploy_local_forwards_https_proxy() -> None:
    script = DEPLOY_LOCAL.read_text()
    assert "https_proxy" in script
    module = LOCAL_MODULE.read_text()
    assert "OPENSSL_CONF" in module
    assert "host_network" in module


def test_api_image_includes_openssl_seclevel_config() -> None:
    dockerfile = ROOT / "backend/Dockerfile"
    conf = ROOT / "backend/openssl-seclevel1.cnf"
    assert conf.is_file()
    assert "openssl-seclevel1.cnf" in dockerfile.read_text()
