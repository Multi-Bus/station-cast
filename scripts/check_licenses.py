"""Fail CI if any dependency uses a license forbidden by docs/LICENSE_POLICY.md.

Reads the CSV report produced by `fosslight_dependency` and checks the
License column against the project's forbidden-license keywords. A blank
License field is reported as a warning (fosslight cannot always resolve a
license from PyPI metadata) but does not fail the build — those packages
must be checked manually before being treated as cleared.
"""

import csv
import sys
from pathlib import Path

FORBIDDEN_KEYWORDS = [
    "sspl",
    "rsal",
    "elastic license",
    "busl",
    "business source license",
    "cc-by-nc",
    "non-commercial",
    "noncommercial",
    "gpl",  # also catches LGPL / AGPL
]


def main(csv_path: Path) -> int:
    violations: list[tuple[str, str]] = []
    unknown: list[str] = []

    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            name = row.get("OSS Name", "").strip()
            license_field = row.get("License", "").strip()

            if not license_field:
                unknown.append(name)
                continue

            lowered = license_field.lower()
            if any(keyword in lowered for keyword in FORBIDDEN_KEYWORDS):
                violations.append((name, license_field))

    if unknown:
        names = ", ".join(unknown)
        print(f"::warning::License unknown for {len(unknown)} package(s), verify manually: {names}")

    if violations:
        print("Forbidden license(s) detected (see docs/LICENSE_POLICY.md):")
        for name, license_field in violations:
            print(f"  - {name}: {license_field}")
        return 1

    print(f"License check passed. {len(unknown)} package(s) need manual verification.")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
