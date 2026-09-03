import ast
from pathlib import Path

ROUTERS = Path(__file__).resolve().parents[1] / "app" / "routers"
ALLOWED_SQLALCHEMY = {"sqlalchemy.ext.asyncio"}
SESSION_MUTATIONS = {"execute", "add", "delete"}


def _sqlalchemy_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sqlalchemy" or alias.name.startswith("sqlalchemy."):
                    found.append(alias.name)
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and (node.module == "sqlalchemy" or node.module.startswith("sqlalchemy."))
        ):
            found.append(node.module)
    return found


def _session_mutations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in SESSION_MUTATIONS:
            continue
        if isinstance(node.func.value, ast.Name) and node.func.value.id == "session":
            found.append(f"session.{node.func.attr}")
    return found


def test_routers_do_not_import_sqlalchemy_query_apis() -> None:
    violations: list[str] = []
    for path in sorted(ROUTERS.glob("*.py")):
        for module in _sqlalchemy_imports(path):
            if module not in ALLOWED_SQLALCHEMY:
                violations.append(f"{path.name}: {module}")
        for call in _session_mutations(path):
            violations.append(f"{path.name}: {call}")
    assert violations == []
