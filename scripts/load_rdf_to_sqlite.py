#!/usr/bin/env python3
"""
load_rdf_to_sqlite.py

Parse the Oak Curriculum ontology and data TTL files, then create and populate
a SQLite database using oak-curriculum-schema-sqlite.sql.

Usage:
    uv run scripts/load_rdf_to_sqlite.py

The database and schema paths are fixed to <repo>/distributions/ and are
deliberately not exposed on the command line. This prevents a caller from
redirecting the database connection, executing an arbitrary schema file, or
triggering the destructive unlink against an arbitrary filesystem location.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path

from rdf_loader import SQLiteAdapter, load_data, parse_ttl_files, print_counts

log = logging.getLogger(__name__)


def _ensure_within(path: Path, allowed_dir: Path) -> Path:
    """Resolve *path* and confirm it is contained within *allowed_dir*.

    Raises ValueError if the resolved path escapes the allowed directory, so
    the connection and the destructive unlink can only ever touch files under
    the distributions directory.
    """
    resolved = path.resolve()
    allowed = allowed_dir.resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError(f"Refusing to use path outside {allowed}: {resolved}")
    return resolved


def create_database(
    db_path: Path, schema_path: Path, allowed_dir: Path
) -> sqlite3.Connection:
    """Create a fresh SQLite database from the schema DDL.

    Both *db_path* and *schema_path* must live inside *allowed_dir*.
    """
    db_path = _ensure_within(db_path, allowed_dir)
    schema_path = _ensure_within(schema_path, allowed_dir)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema_path.read_text(encoding="utf-8"))  # NOSONAR
    return conn


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    repo_root = Path(__file__).resolve().parent.parent
    dist_dir = repo_root / "distributions"
    schema_path = dist_dir / "oak-curriculum-schema-sqlite.sql"
    db_path = dist_dir / "oak-curriculum.sqlite"

    if not schema_path.exists():
        sys.exit(f"Schema file not found: {schema_path}")

    log.info("Schema:  %s", schema_path)
    log.info("Output:  %s", db_path)

    g = parse_ttl_files(repo_root)
    conn = create_database(db_path, schema_path, dist_dir)
    adapter = SQLiteAdapter()
    try:
        cur = conn.cursor()
        load_data(g, cur, adapter)
        conn.commit()
        print_counts(cur, adapter)
    finally:
        conn.close()

    log.info("Done. Database written to %s", db_path)


if __name__ == "__main__":
    main()
