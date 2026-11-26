"""Write the API's OpenAPI spec to docs/openapi.json (make openapi). A test keeps it in sync."""

import json
import sys
from pathlib import Path

from papertrail.api.app import create_app
from papertrail.config import Settings


def spec() -> str:
    app = create_app(Settings(_env_file=None, store_backend="memory", upload_dir="/tmp/pt-up"))
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/openapi.json")
    out.write_text(spec(), encoding="utf-8")
    print(f"Wrote {out}")
