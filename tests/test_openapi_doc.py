import importlib.util
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_committed_openapi_spec_is_up_to_date():
    spec = importlib.util.spec_from_file_location(
        "export_openapi", ROOT / "scripts" / "export_openapi.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (ROOT / "docs" / "openapi.json").read_text() == module.spec(), "Run: make openapi"
