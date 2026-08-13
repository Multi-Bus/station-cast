"""Freeze the API's OpenAPI spec to docs/openapi.json (S2, issue #14).

Run after any change to api/main.py or api/schemas.py to re-freeze the
contract. CI checks the committed file matches this script's output so a
schema change can't land without updating the frozen spec.
"""

import json
import sys
from pathlib import Path

from stationcast.api.main import app

OUT_PATH = Path("docs/openapi.json")


def main() -> int:
    spec = json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    OUT_PATH.write_text(spec, encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
