#!/usr/bin/env python3
"""
validate_pg_jsonl.py — Validate property graph JSONL distribution files.

Checks that nodes.jsonl and relationships.jsonl are well-formed and contain
the required fields. Exits 1 if any errors are found.

Usage:
  python scripts/validate_pg_jsonl.py <output_dir>
"""

import json
import sys
from pathlib import Path


def validate_file(
    path: Path, required_fields: list[str]
) -> tuple[int, int, list[str]]:
    errors: list[str] = []
    count = 0
    stub_count = 0

    with open(path, encoding="utf-8") as f:
        for line_num, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as e:
                errors.append(f"Line {line_num}: invalid JSON — {e}")
                continue
            for field in required_fields:
                if field not in obj:
                    errors.append(f"Line {line_num}: missing required field '{field}'")
            if obj.get("labels") == ["ExternalReference"]:
                stub_count += 1
            count += 1

    return count, stub_count, errors


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <output_dir>", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(sys.argv[1])
    all_ok = True

    checks = [
        (output_dir / "nodes.jsonl",        ["id", "labels", "properties"]),
        (output_dir / "relationships.jsonl", ["type", "startNodeId", "endNodeId", "properties"]),
    ]

    for path, fields in checks:
        if not path.exists():
            print(f"  ERROR: {path} not found", file=sys.stderr)
            all_ok = False
            continue

        count, stub_count, errors = validate_file(path, fields)
        if errors:
            print(f"  INVALID {path.name}: {len(errors)} error(s)")
            for e in errors[:10]:
                print(f"    {e}")
            all_ok = False
        else:
            extra = f", {stub_count:,} external stubs" if stub_count else ""
            print(f"  Valid {path.name} ({count:,} records{extra})")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
