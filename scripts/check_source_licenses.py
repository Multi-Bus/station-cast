"""Fail CI if ScanCode finds embedded license text in our own source files.

Reads the JSON reports produced by `scancode --license` (run once each
against src/, scripts/, and tests/) and checks whether any file has a
detected license. Our own code should carry no embedded license text at all,
so any detection means license-encumbered code may have been copied in and
needs manual review (this is a different concern from
scripts/check_licenses.py, which checks the licenses of *dependencies* we
install rather than the source files we wrote).
"""

import json
import sys
from pathlib import Path


def main(report_paths: list[Path]) -> int:
    detections: list[tuple[str, str]] = []

    for report_path in report_paths:
        with report_path.open(encoding="utf-8") as f:
            report = json.load(f)

        for entry in report["files"]:
            if entry.get("type") != "file":
                continue
            expression = entry.get("detected_license_expression")
            if expression:
                detections.append((entry["path"], expression))

    if detections:
        print("Embedded license text detected in source files:")
        for path, expression in detections:
            print(f"  - {path}: {expression}")
        return 1

    print("No embedded licenses detected in source files.")
    return 0


if __name__ == "__main__":
    sys.exit(main([Path(p) for p in sys.argv[1:]]))
