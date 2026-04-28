#!/usr/bin/env python3
"""
generate_distribution_summary.py

Post-build: generates checksums, distribution-info.json, and the GitHub
Actions step summary for the oak-curriculum distribution directory.

Usage:
    uv run scripts/generate_distribution_summary.py \
        --triple-count 411186 \
        --commit-sha abc1234 \
        --ref refs/heads/main
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DIST_DIR = Path("distributions")
FILE_PREFIX = "oak-curriculum-full"

# (filename, display label, extension for RDF formats, MIME type)
DIST_FILES: list[tuple[str, str, str | None, str]] = [
    (f"{FILE_PREFIX}.ttl",                 "Turtle",                               ".ttl",    "text/turtle"),
    (f"{FILE_PREFIX}.jsonld",              "JSON-LD",                              ".jsonld", "application/ld+json"),
    (f"{FILE_PREFIX}.rdf",                 "RDF/XML",                              ".rdf",    "application/rdf+xml"),
    (f"{FILE_PREFIX}.nt",                  "N-Triples",                            ".nt",     "application/n-triples"),
    ("oak-curriculum.sqlite",              "SQLite",                               ".sqlite", "application/vnd.sqlite3"),
    ("nodes.jsonl",                        "Property Graph Nodes (JSONL)",         None,      "application/x-ndjson"),
    ("relationships.jsonl",                "Property Graph Relationships (JSONL)", None,      "application/x-ndjson"),
    ("oak-curriculum-schema-postgres.sql", "SQL Schema (PostgreSQL)",              None,      "application/sql"),
    ("oak-curriculum-schema-sqlite.sql",   "SQL Schema (SQLite)",                  None,      "application/sql"),
]


def _checksum(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _human_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "K", "M", "G"):
        if size < 1024:
            return f"{size:.0f}{unit}"
        size /= 1024
    return f"{size:.1f}T"


def generate_checksums() -> None:
    sha256_lines: list[str] = []
    md5_lines: list[str] = []
    for filename, *_ in DIST_FILES:
        p = DIST_DIR / filename
        if p.exists():
            sha256_lines.append(f"{_checksum(p, 'sha256')}  {filename}")
            md5_lines.append(f"{_checksum(p, 'md5')}  {filename}")
    (DIST_DIR / "checksums-sha256.txt").write_text("\n".join(sha256_lines) + "\n")
    (DIST_DIR / "checksums-md5.txt").write_text("\n".join(md5_lines) + "\n")
    print("Checksums generated:\n")
    print("\n".join(sha256_lines))


def generate_metadata(triple_count: int, commit_sha: str, ref: str) -> None:
    formats: list[dict[str, str]] = []
    for filename, label, ext, mime in DIST_FILES:
        entry: dict[str, str] = {"format": label, "mime_type": mime}
        if ext:
            entry["extension"] = ext
        else:
            entry["filename"] = filename
        formats.append(entry)

    metadata = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit_sha": commit_sha,
        "commit_short": commit_sha[:7],
        "ref": ref,
        "triple_count": triple_count,
        "formats": formats,
    }
    out = DIST_DIR / "distribution-info.json"
    out.write_text(json.dumps(metadata, indent=2) + "\n")
    print("\nDistribution metadata created:\n")
    print(out.read_text())


def generate_summary(triple_count: int) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        print("GITHUB_STEP_SUMMARY not set; skipping CI summary output")
        return

    rows = [
        f"| {label} | `{filename}` | {_human_size((DIST_DIR / filename).stat().st_size)} |"
        for filename, label, *_ in DIST_FILES
        if (DIST_DIR / filename).exists()
    ]
    total = sum(
        (DIST_DIR / fn).stat().st_size
        for fn, *_ in DIST_FILES
        if (DIST_DIR / fn).exists()
    )

    lines = [
        "### Generated RDF Distribution Files",
        "",
        f"**Triple Count:** {triple_count}",
        "",
        "| Format | File | Size |",
        "|--------|------|------|",
        *rows,
        "",
        f"**Total size:** {_human_size(total)}",
        "",
        "#### Additional Files",
        "- `checksums-sha256.txt` - SHA256 checksums for verification",
        "- `checksums-md5.txt` - MD5 checksums for compatibility",
        "- `distribution-info.json` - Metadata and build information",
        "",
    ]
    with open(summary_path, "a") as f:
        f.write("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate checksums, metadata and CI summary for oak-curriculum distributions"
    )
    parser.add_argument("--triple-count", type=int, default=0, help="Number of RDF triples")
    parser.add_argument("--commit-sha", default="unknown", help="Full git commit SHA")
    parser.add_argument("--ref", default="unknown", help="Git ref (branch or tag)")
    args = parser.parse_args()

    generate_checksums()
    generate_metadata(args.triple_count, args.commit_sha, args.ref)
    generate_summary(args.triple_count)


if __name__ == "__main__":
    main()
