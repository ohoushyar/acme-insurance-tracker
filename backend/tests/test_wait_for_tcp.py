import importlib.util
from pathlib import Path


def _wait_for_tcp():
    path = Path(__file__).resolve().parents[1] / "scripts" / "wait_for_tcp.py"
    spec = importlib.util.spec_from_file_location("wait_for_tcp", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.wait_for_tcp


def test_wait_for_tcp_rejects_invalid_inputs() -> None:
    wait_for_tcp = _wait_for_tcp()
    assert wait_for_tcp("", 5432, 5) is False
    assert wait_for_tcp("127.0.0.1", 0, 5) is False
    assert wait_for_tcp("127.0.0.1", 5432, 0) is False
