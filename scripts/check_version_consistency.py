#!/usr/bin/env python3
"""
Check that every version string in the repository agrees.

Usage:
    python scripts/check_version_consistency.py [--tag vX.Y.Z]

Compares the version stated in:
- pyproject.toml (project.version)
- CITATION.cff (version and preferred-citation.version)
- ontology/oak-curriculum-ontology.ttl (owl:versionInfo and owl:versionIRI)
- README.md (version badge and roadmap heading)

All must be identical. With --tag (used in the release workflow), they must
also match the release tag. Exits non-zero on any mismatch, listing each
location and the version it states.
"""

import argparse
import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def collect_versions() -> dict[str, str | None]:
    """Return {location: version} for every place a version is stated."""
    versions: dict[str, str | None] = {}

    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        versions["pyproject.toml"] = tomllib.load(f)["project"]["version"]

    cff = (REPO_ROOT / "CITATION.cff").read_text(encoding="utf-8")
    cff_versions = re.findall(r"^\s*version:\s*(\S+)", cff, flags=re.MULTILINE)
    versions["CITATION.cff version"] = cff_versions[0] if cff_versions else None
    versions["CITATION.cff preferred-citation"] = (
        cff_versions[1] if len(cff_versions) > 1 else None
    )

    ttl = (REPO_ROOT / "ontology" / "oak-curriculum-ontology.ttl").read_text(
        encoding="utf-8"
    )
    info = re.search(r'owl:versionInfo\s+"([^"]+)"', ttl)
    versions["ontology owl:versionInfo"] = info.group(1) if info else None
    iri = re.search(r"owl:versionIRI\s+<[^>]*/([\d.]+)>", ttl)
    versions["ontology owl:versionIRI"] = iri.group(1) if iri else None

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    badge = re.search(r"badge/version-([\d.]+)-", readme)
    versions["README version badge"] = badge.group(1) if badge else None
    roadmap = re.search(r"^### v([\d.]+) \(Current", readme, flags=re.MULTILINE)
    versions["README roadmap heading"] = roadmap.group(1) if roadmap else None

    return versions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tag",
        help="Release tag (e.g. v0.1.3) that all version strings must match",
    )
    args = parser.parse_args()

    versions = collect_versions()
    expected = args.tag.lstrip("v") if args.tag else None

    errors = []
    for location, version in versions.items():
        if version is None:
            errors.append(f"{location}: version not found")
    stated = {v for v in versions.values() if v is not None}
    if len(stated) > 1:
        errors.append(f"versions disagree: {sorted(stated)}")
    if expected and stated != {expected}:
        errors.append(f"versions {sorted(stated)} do not match tag {args.tag}")

    for location, version in sorted(versions.items()):
        print(f"  {location}: {version}")

    if errors:
        print(f"\n{len(errors)} version check(s) failed:")
        for error in errors:
            print(f"  FAIL: {error}")
        return 1

    print(f"\nAll version strings agree: {stated.pop()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
