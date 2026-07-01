#!/usr/bin/env python3
"""
load_rdf_to_postgres.py

Parse the Oak Curriculum ontology and data TTL files, then create and populate
a PostgreSQL database using oak-curriculum-schema-postgres.sql.

Usage:
    uv run scripts/load_rdf_to_postgres.py

Connection details come only from the PG* environment variables below. A DSN
cannot be supplied on the command line, and the schema path is fixed to
<repo>/distributions/. This prevents a caller from redirecting the database
connection or executing an arbitrary schema file as DDL.

Environment variables:
    PGHOST      (default: localhost)
    PGPORT      (default: 5432)
    PGDATABASE  (default: oak_curriculum)
    PGUSER      (default: postgres)
    PGPASSWORD  (default: empty)

Each run drops and recreates all tables, so re-runs are idempotent.
"""

from __future__ import annotations

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


def connect_db() -> "psycopg2.extensions.connection":
    """Connect to PostgreSQL using the PG* environment variables."""
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ.get("PGDATABASE", "oak_curriculum"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )


def _ensure_within(path: Path, allowed_dir: Path) -> Path:
    """Resolve *path* and confirm it is contained within *allowed_dir*.

    Raises ValueError if the resolved path escapes the allowed directory, so
    the DDL that gets executed can only ever come from the distributions
    directory.
    """
    resolved = path.resolve()
    allowed = allowed_dir.resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError(f"Refusing to use path outside {allowed}: {resolved}")
    return resolved


def create_schema(
    conn: "psycopg2.extensions.connection", schema_path: Path, allowed_dir: Path
) -> None:
    """Drop existing tables and recreate from the schema DDL.

    *schema_path* must live inside *allowed_dir*.

    The DDL contains inline REFERENCES which can fail if tables are created
    out of FK-dependency order. We strip inline REFERENCES, create all tables
    first, then add FK constraints via ALTER TABLE.
    """
    schema_path = _ensure_within(schema_path, allowed_dir)
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

    # Matches: colname INTEGER [NOT NULL] REFERENCES table(col) [ON DELETE action]
    # group 1 = column name, 2 = optional NOT NULL, 3/4 = referenced table/column.
    # Each \s+ is bounded by a non-space token so there is no ambiguous
    # whitespace matching (and therefore no super-linear backtracking).
    fk_pattern = re.compile(
        r"(\w+)\s+INTEGER\s+(NOT\s+NULL\s+)?REFERENCES\s+(\w+)\((\w+)\)"
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
            # Rebuild the column definition without the inline REFERENCES
            # clause, reusing the groups fk_pattern already captured. This
            # avoids a second, backtracking-prone regex pass per column.
            kept = f"{m.group(1)} INTEGER" + (" NOT NULL" if m.group(2) else "")
            clean_stmt = clean_stmt.replace(matched_text, kept)
            alter_stmts.append(
                f"ALTER TABLE {table_name}"
                f" ADD FOREIGN KEY ({m.group(1)})"
                f" REFERENCES {m.group(3)}({m.group(4)}) ON DELETE RESTRICT;"
            )

        cur.execute(clean_stmt)

    for alter in alter_stmts:
        cur.execute(alter)

    conn.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    repo_root = Path(__file__).resolve().parent.parent
    dist_dir = repo_root / "distributions"
    schema_path = dist_dir / "oak-curriculum-schema-postgres.sql"

    if not schema_path.exists():
        sys.exit(f"Schema file not found: {schema_path}")

    log.info("Schema:  %s", schema_path)
    log.info("Connection: PG* environment variables")

    g = parse_ttl_files(repo_root)
    conn = connect_db()
    adapter = PostgresAdapter()
    try:
        create_schema(conn, schema_path, dist_dir)
        cur = conn.cursor()
        load_data(g, cur, adapter)
        conn.commit()
        print_counts(cur, adapter)
    finally:
        conn.close()

    log.info("Done.")


if __name__ == "__main__":
    main()
