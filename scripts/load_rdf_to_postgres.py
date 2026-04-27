#!/usr/bin/env python3
"""
load_rdf_to_postgres.py

Parse the Oak Curriculum ontology and data TTL files, then create and populate
a PostgreSQL database using oak-curriculum-schema-postgres.sql.

Usage:
    uv run scripts/load_rdf_to_postgres.py
    uv run scripts/load_rdf_to_postgres.py --dsn "postgresql://user:pass@localhost:5432/oak_curriculum"
    uv run scripts/load_rdf_to_postgres.py --schema distributions/oak-curriculum-schema-postgres.sql

Environment variables (used when --dsn is not provided):
    PGHOST      (default: localhost)
    PGPORT      (default: 5432)
    PGDATABASE  (default: oak_curriculum)
    PGUSER      (default: postgres)
    PGPASSWORD  (default: empty)

Each run drops and recreates all tables, so re-runs are idempotent.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from pathlib import Path

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 is required: pip install psycopg2-binary")

from rdf_loader import PostgresAdapter, load_data, parse_ttl_files, print_counts

log = logging.getLogger(__name__)


def connect_db(dsn: str | None) -> "psycopg2.extensions.connection":
    """Connect to PostgreSQL using a DSN or PG* environment variables."""
    if dsn:
        return psycopg2.connect(dsn)
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ.get("PGDATABASE", "oak_curriculum"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )


def create_schema(
    conn: "psycopg2.extensions.connection", schema_path: Path
) -> None:
    """Drop existing tables and recreate from the schema DDL.

    The DDL contains inline REFERENCES which can fail if tables are created
    out of FK-dependency order. We strip inline REFERENCES, create all tables
    first, then add FK constraints via ALTER TABLE.
    """
    ddl = schema_path.read_text(encoding="utf-8")
    cur = conn.cursor()

    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    existing = [row[0] for row in cur.fetchall()]
    if existing:
        cur.execute(f"DROP TABLE IF EXISTS {', '.join(existing)} CASCADE")

    stmts = re.findall(
        r"(CREATE\s+TABLE\s+\w+\s*\(.*?\)\s*;)",
        ddl,
        re.DOTALL | re.IGNORECASE,
    )

    # Matches: colname [NOT NULL] REFERENCES table(col) [ON DELETE action]
    fk_pattern = re.compile(
        r"(\w+)\s+INTEGER\s*(?:NOT\s+NULL\s*)?REFERENCES\s+(\w+)\((\w+)\)"
        r"(?:\s+ON\s+DELETE\s+\w+)?",
        re.IGNORECASE,
    )
    table_pattern = re.compile(r"CREATE\s+TABLE\s+(\w+)", re.IGNORECASE)
    alter_stmts: list[str] = []

    for stmt in stmts:
        table_match = table_pattern.search(stmt)
        if not table_match:
            continue
        table_name = table_match.group(1)

        clean_stmt = stmt
        for m in fk_pattern.finditer(stmt):
            matched_text = m.group(0)
            stripped = re.sub(
                r"\s*REFERENCES\s+\w+\(\w+\)(?:\s+ON\s+DELETE\s+\w+)?",
                "",
                matched_text,
            )
            clean_stmt = clean_stmt.replace(matched_text, stripped)
            alter_stmts.append(
                f"ALTER TABLE {table_name}"
                f" ADD FOREIGN KEY ({m.group(1)})"
                f" REFERENCES {m.group(2)}({m.group(3)}) ON DELETE RESTRICT;"
            )

        cur.execute(clean_stmt)

    for alter in alter_stmts:
        cur.execute(alter)

    conn.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Load Oak Curriculum RDF data into PostgreSQL"
    )
    parser.add_argument(
        "--schema", type=Path, default=None,
        help="Path to PostgreSQL schema SQL file"
        " (default: <repo>/distributions/oak-curriculum-schema-postgres.sql)",
    )
    parser.add_argument(
        "--dsn", default=None,
        help="PostgreSQL connection string (default: use PG* environment variables)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    schema_path = (
        args.schema
        if args.schema
        else repo_root / "distributions" / "oak-curriculum-schema-postgres.sql"
    )

    if not schema_path.exists():
        sys.exit(f"Schema file not found: {schema_path}")

    log.info("Schema:  %s", schema_path)
    log.info("DSN:     %s", args.dsn or "(from PG* environment variables)")

    g = parse_ttl_files(repo_root)
    conn = connect_db(args.dsn)
    adapter = PostgresAdapter()
    try:
        create_schema(conn, schema_path)
        cur = conn.cursor()
        load_data(g, cur, adapter)
        conn.commit()
        print_counts(cur, adapter)
    finally:
        conn.close()

    log.info("Done.")


if __name__ == "__main__":
    main()
