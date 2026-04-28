#!/usr/bin/env python3
"""
load_rdf_to_sqlite.py

Parse the Oak Curriculum ontology and data TTL files, then create and populate
a SQLite database using oak-curriculum-schema-sqlite.sql.

Usage:
    uv run scripts/load_rdf_to_sqlite.py
    uv run scripts/load_rdf_to_sqlite.py --db /path/to/output.sqlite
    uv run scripts/load_rdf_to_sqlite.py --schema distributions/oak-curriculum-schema-sqlite.sql
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

from rdf_loader import SQLiteAdapter, load_data, parse_ttl_files, print_counts

log = logging.getLogger(__name__)


def create_database(db_path: Path, schema_path: Path) -> sqlite3.Connection:
    """Create a fresh SQLite database from the schema DDL."""
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema_path.read_text(encoding="utf-8"))  # NOSONAR
    return conn


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Load Oak Curriculum RDF data into SQLite"
    )
    parser.add_argument(
        "--schema", type=Path, default=None,
        help="Path to SQLite schema SQL file"
        " (default: <repo>/distributions/oak-curriculum-schema-sqlite.sql)",
    )
    parser.add_argument(
        "--db", type=Path, default=None,
        help="Output SQLite database path"
        " (default: <repo>/distributions/oak-curriculum.sqlite)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    schema_path = (
        args.schema
        if args.schema
        else repo_root / "distributions" / "oak-curriculum-schema-sqlite.sql"
    )
    db_path = (
        args.db
        if args.db
        else repo_root / "distributions" / "oak-curriculum.sqlite"
    )

    if not schema_path.exists():
        sys.exit(f"Schema file not found: {schema_path}")

    log.info("Schema:  %s", schema_path)
    log.info("Output:  %s", db_path)

    g = parse_ttl_files(repo_root)
    conn = create_database(db_path, schema_path)
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
