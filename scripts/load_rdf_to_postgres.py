#!/usr/bin/env python3
"""
load_rdf_to_postgres.py

Parse the Oak Curriculum ontology and data TTL files, then create and populate
a PostgreSQL database using oak-curriculum-schema-postgres.sql.

Usage:
    python scripts/load_rdf_to_postgres.py
    python scripts/load_rdf_to_postgres.py --dsn "postgresql://user:pass@localhost:5432/oak_curriculum"
    python scripts/load_rdf_to_postgres.py --schema distributions/oak-curriculum-schema-postgres.sql

Environment variables (used when --dsn is not provided):
    PGHOST      (default: localhost)
    PGPORT      (default: 5432)
    PGDATABASE  (default: oak_curriculum)
    PGUSER      (default: postgres)
    PGPASSWORD  (default: empty)

Each run drops and recreates all tables, so re-runs are idempotent.
"""

import argparse
import os
import re
import sys
from pathlib import Path

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 is required: pip install psycopg2-binary")

from rdflib import BNode, Graph, Namespace, RDF, RDFS, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import SKOS, XSD

CURRIC = Namespace("https://w3id.org/uk/oak/curriculum/ontology/")
SCHEMA = Namespace("http://schema.org/")

ONTOLOGY_DIR = "ontology"
DATA_DIR = "data"


def parse_ttl_files(repo_root: Path) -> Graph:
    """Parse all .ttl files from ontology/ and data/ directories."""
    g = Graph()
    count = 0
    for dir_path in [repo_root / ONTOLOGY_DIR, repo_root / DATA_DIR]:
        if not dir_path.exists():
            continue
        for ttl_file in sorted(dir_path.rglob("*.ttl")):
            g.parse(str(ttl_file), format="turtle")
            count += 1
    print(f"Parsed {count} TTL files ({len(g)} triples)")
    return g


def connect_db(dsn: str | None) -> "psycopg2.extensions.connection":
    """Connect to PostgreSQL using DSN or environment variables."""
    if dsn:
        return psycopg2.connect(dsn)
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ.get("PGDATABASE", "oak_curriculum"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )


def create_schema(conn: "psycopg2.extensions.connection", schema_path: Path):
    """Drop existing tables and recreate from schema DDL.

    The DDL has inline REFERENCES which can fail if tables are created out of
    FK-dependency order. We strip inline REFERENCES, create tables first, then
    add FK constraints via ALTER TABLE.
    """
    ddl = schema_path.read_text()
    cur = conn.cursor()

    # Drop all existing tables
    cur.execute("""
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
    """)
    existing = [row[0] for row in cur.fetchall()]
    if existing:
        cur.execute(f"DROP TABLE IF EXISTS {', '.join(existing)} CASCADE")

    # Parse out individual CREATE TABLE statements
    stmts = re.findall(
        r"(CREATE\s+TABLE\s+\w+\s*\(.*?\)\s*;)",
        ddl,
        re.DOTALL | re.IGNORECASE,
    )

    # Regex to match inline FK: colname [NOT NULL] REFERENCES table(id) [ON DELETE RESTRICT]
    fk_pattern = re.compile(
        r"(\w+)\s+INTEGER\s*(?:NOT\s+NULL\s*)?REFERENCES\s+(\w+)\((\w+)\)(?:\s+ON\s+DELETE\s+\w+)?",
        re.IGNORECASE,
    )

    table_pattern = re.compile(r"CREATE\s+TABLE\s+(\w+)", re.IGNORECASE)
    alter_stmts = []

    for stmt in stmts:
        table_match = table_pattern.search(stmt)
        if not table_match:
            continue
        table_name = table_match.group(1)

        clean_stmt = stmt
        for m in fk_pattern.finditer(stmt):
            matched_text = m.group(0)
            replacement = re.sub(
                r"\s*REFERENCES\s+\w+\(\w+\)(?:\s+ON\s+DELETE\s+\w+)?",
                "",
                matched_text,
            )
            clean_stmt = clean_stmt.replace(matched_text, replacement)
            ref_table = m.group(2)
            ref_col = m.group(3)
            fk_col = m.group(1)
            alter_stmts.append(
                f"ALTER TABLE {table_name} ADD FOREIGN KEY ({fk_col}) "
                f"REFERENCES {ref_table}({ref_col}) ON DELETE RESTRICT;"
            )

        cur.execute(clean_stmt)

    for alter in alter_stmts:
        cur.execute(alter)

    conn.commit()


def lit_str(g: Graph, subj: URIRef, pred: URIRef) -> str | None:
    for obj in g.objects(subj, pred):
        if isinstance(obj, Literal):
            return str(obj)
    return None


def lit_int(g: Graph, subj: URIRef, pred: URIRef) -> int | None:
    for obj in g.objects(subj, pred):
        if isinstance(obj, Literal):
            try:
                return int(obj)
            except (ValueError, TypeError):
                return None
    return None


def lit_bool(g: Graph, subj: URIRef, pred: URIRef) -> bool | None:
    for obj in g.objects(subj, pred):
        if isinstance(obj, Literal):
            return bool(obj)
    return None


def fk_uri(g: Graph, subj: URIRef, pred: URIRef) -> URIRef | None:
    for obj in g.objects(subj, pred):
        if isinstance(obj, URIRef):
            return obj
    return None


def resolve_fk(uri: URIRef | None, lookup: dict) -> int | None:
    if uri is None:
        return None
    return lookup.get(str(uri))


def load_data(g: Graph, conn: "psycopg2.extensions.connection"):
    """Load RDF instance data into PostgreSQL tables in FK-dependency order."""
    cur = conn.cursor()
    lookup: dict[str, int] = {}

    def insert(table: str, uri: URIRef, values: dict) -> int:
        values["uri"] = str(uri)
        cols = ", ".join(values.keys())
        placeholders = ", ".join(["%s"] * len(values))
        cur.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING id",
            list(values.values()),
        )
        row_id = cur.fetchone()[0]
        lookup[str(uri)] = row_id
        return row_id

    def instances(rdf_class: URIRef) -> list[URIRef]:
        return sorted(set(g.subjects(RDF.type, rdf_class)), key=str)

    # ------------------------------------------------------------------
    # Tier 1: no FK dependencies
    # ------------------------------------------------------------------

    for uri in instances(CURRIC.Phase):
        insert("phase", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
            "lower_age_boundary": lit_int(g, uri, CURRIC.lowerAgeBoundary),
            "upper_age_boundary": lit_int(g, uri, CURRIC.upperAgeBoundary),
        })

    for uri in instances(CURRIC.Discipline):
        insert("discipline", uri, {
            "name": lit_str(g, uri, SKOS.prefLabel) or "",
            "description": lit_str(g, uri, SKOS.definition),
        })

    for uri in instances(CURRIC.ExamBoard):
        insert("exam_board", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
            "website": lit_str(g, uri, CURRIC.website),
            "accreditation_body": lit_str(g, uri, CURRIC.accreditationBody),
        })

    for uri in instances(CURRIC.Tier):
        insert("tier", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
        })

    for uri in instances(CURRIC.Thread):
        insert("thread", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
        })

    for uri in instances(CURRIC.Keyword):
        insert("keyword", uri, {
            "name": lit_str(g, uri, SCHEMA.name) or "",
            "description": lit_str(g, uri, SCHEMA.description),
        })

    for uri in instances(CURRIC.Misconception):
        insert("misconception", uri, {
            "statement": lit_str(g, uri, CURRIC.statement) or "",
            "correction": lit_str(g, uri, CURRIC.correction) or "",
        })

    # ------------------------------------------------------------------
    # Tier 2: depends on Tier 1
    # ------------------------------------------------------------------

    for uri in instances(CURRIC.KeyStage):
        phase_uri = fk_uri(g, uri, CURRIC.isKeyStageOf)
        insert("key_stage", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
            "lower_age_boundary": lit_int(g, uri, CURRIC.lowerAgeBoundary),
            "upper_age_boundary": lit_int(g, uri, CURRIC.upperAgeBoundary),
            "phase_id": resolve_fk(phase_uri, lookup),
        })

    for uri in instances(CURRIC.Strand):
        broader_uri = fk_uri(g, uri, SKOS.broader)
        insert("strand", uri, {
            "name": lit_str(g, uri, SKOS.prefLabel) or "",
            "description": lit_str(g, uri, SKOS.definition),
            "display_order": lit_int(g, uri, CURRIC.displayOrder),
            "discipline_id": resolve_fk(broader_uri, lookup),
        })

    for uri in instances(CURRIC.SubjectGroup):
        disc_uri = fk_uri(g, uri, CURRIC.coversDiscipline)
        insert("subject_group", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "discipline_id": resolve_fk(disc_uri, lookup),
        })

    # ------------------------------------------------------------------
    # Tier 3: depends on Tier 2
    # ------------------------------------------------------------------

    for uri in instances(CURRIC.YearGroup):
        ks_uri = fk_uri(g, uri, CURRIC.isYearGroupOf)
        insert("year_group", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
            "lower_age_boundary": lit_int(g, uri, CURRIC.lowerAgeBoundary),
            "upper_age_boundary": lit_int(g, uri, CURRIC.upperAgeBoundary),
            "key_stage_id": resolve_fk(ks_uri, lookup),
        })

    for uri in instances(CURRIC.SubStrand):
        broader_uri = fk_uri(g, uri, SKOS.broader)
        insert("sub_strand", uri, {
            "name": lit_str(g, uri, SKOS.prefLabel) or "",
            "description": lit_str(g, uri, SKOS.definition),
            "display_order": lit_int(g, uri, CURRIC.displayOrder),
            "strand_id": resolve_fk(broader_uri, lookup),
        })

    for uri in instances(CURRIC.Subject):
        sg_uri = fk_uri(g, uri, CURRIC.isSubjectOf)
        insert("subject", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "rationale": lit_str(g, uri, CURRIC.rationale),
            "school_curriculum": lit_str(g, uri, CURRIC.schoolCurriculum),
            "subject_group_id": resolve_fk(sg_uri, lookup),
        })

    # ------------------------------------------------------------------
    # Tier 4: depends on Tier 3
    # ------------------------------------------------------------------

    for uri in instances(CURRIC.ContentDescriptor):
        broader_uri = fk_uri(g, uri, SKOS.broader)
        insert("content_descriptor", uri, {
            "name": lit_str(g, uri, SKOS.prefLabel) or "",
            "supporting_guidance": lit_str(g, uri, CURRIC.supportingGuidance),
            "display_order": lit_int(g, uri, CURRIC.displayOrder),
            "sub_strand_id": resolve_fk(broader_uri, lookup),
        })

    for uri in instances(CURRIC.Scheme):
        subj_uri = fk_uri(g, uri, CURRIC.isSchemeOf)
        ks_uri = fk_uri(g, uri, CURRIC.coversKeyStage)
        insert("scheme", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
            "subject_id": resolve_fk(subj_uri, lookup),
            "key_stage_id": resolve_fk(ks_uri, lookup),
        })

    # ------------------------------------------------------------------
    # Tier 5: depends on Tier 4
    # ------------------------------------------------------------------

    for uri in instances(CURRIC.Progression):
        scheme_uri = fk_uri(g, uri, CURRIC.isProgressionOf)
        insert("progression", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "scheme_id": resolve_fk(scheme_uri, lookup),
        })

    for uri in instances(CURRIC.Programme):
        scheme_uri = fk_uri(g, uri, CURRIC.isProgrammeOf)
        yg_uri = fk_uri(g, uri, CURRIC.coversYearGroup)
        eb_uri = fk_uri(g, uri, CURRIC.hasExamBoard)
        tier_uri = fk_uri(g, uri, CURRIC.hasTier)
        insert("programme", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "is_national_curriculum": lit_bool(g, uri, CURRIC.isNationalCurriculum),
            "is_required": lit_bool(g, uri, CURRIC.isRequired),
            "is_examined": lit_bool(g, uri, CURRIC.isExamined),
            "exam_type": lit_str(g, uri, CURRIC.examType),
            "scheme_id": resolve_fk(scheme_uri, lookup),
            "year_group_id": resolve_fk(yg_uri, lookup),
            "exam_board_id": resolve_fk(eb_uri, lookup),
            "tier_id": resolve_fk(tier_uri, lookup),
        })

    for uri in instances(CURRIC.Unit):
        scheme_uri = fk_uri(g, uri, CURRIC.isUnitOf)
        insert("unit", uri, {
            "oak_id": lit_int(g, uri, CURRIC.id),
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
            "why_this_why_now": lit_str(g, uri, CURRIC.whyThisWhyNow) or "",
            "unit_prior_knowledge_requirements": lit_str(g, uri, CURRIC.unitPriorKnowledgeRequirements) or "",
            "scheme_id": resolve_fk(scheme_uri, lookup),
        })

    # ------------------------------------------------------------------
    # Tier 6: depends on Tier 5
    # ------------------------------------------------------------------

    for uri in instances(CURRIC.UnitVariantChoice):
        insert("unit_variant_choice", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
        })

    for uri in instances(CURRIC.UnitVariant):
        unit_uri = fk_uri(g, uri, CURRIC.isUnitVariantOf)
        insert("unit_variant", uri, {
            "oak_id": lit_int(g, uri, CURRIC.id),
            "name": lit_str(g, uri, RDFS.label) or "",
            "unit_id": resolve_fk(unit_uri, lookup),
        })

    for uri in instances(CURRIC.Lesson):
        insert("lesson", uri, {
            "oak_id": lit_int(g, uri, CURRIC.id) or 0,
            "name": lit_str(g, uri, RDFS.label) or "",
        })

    # ------------------------------------------------------------------
    # Tier 7: depends on Tier 6
    # ------------------------------------------------------------------

    # unit_variant_inclusion (found via hasUnitVariantInclusion on Programme)
    for prog_uri in instances(CURRIC.Programme):
        prog_id = lookup.get(str(prog_uri))
        if prog_id is None:
            continue
        for incl_uri in g.objects(prog_uri, CURRIC.hasUnitVariantInclusion):
            if not isinstance(incl_uri, URIRef):
                continue
            uv_uri = fk_uri(g, incl_uri, CURRIC.includesUnitVariant)
            uvc_uri = fk_uri(g, incl_uri, CURRIC.includesUnitVariantChoice)
            cur.execute(
                "INSERT INTO unit_variant_inclusion "
                "(uri, sequence_position, min_choices, max_choices, "
                "programme_id, unit_variant_id, unit_variant_choice_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (
                    str(incl_uri),
                    lit_int(g, incl_uri, CURRIC.sequencePosition),
                    lit_int(g, incl_uri, CURRIC.minChoices),
                    lit_int(g, incl_uri, CURRIC.maxChoices),
                    prog_id,
                    resolve_fk(uv_uri, lookup),
                    resolve_fk(uvc_uri, lookup),
                ),
            )
            lookup[str(incl_uri)] = cur.fetchone()[0]

    # lesson_inclusion (found via hasLessonInclusion on UnitVariant)
    for uv_uri in instances(CURRIC.UnitVariant):
        uv_id = lookup.get(str(uv_uri))
        if uv_id is None:
            continue
        for incl_uri in g.objects(uv_uri, CURRIC.hasLessonInclusion):
            if not isinstance(incl_uri, URIRef):
                continue
            lesson_uri = fk_uri(g, incl_uri, CURRIC.includesLesson)
            cur.execute(
                "INSERT INTO lesson_inclusion "
                "(uri, sequence_position, unit_variant_id, lesson_id) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (
                    str(incl_uri),
                    lit_int(g, incl_uri, CURRIC.sequencePosition),
                    uv_id,
                    resolve_fk(lesson_uri, lookup),
                ),
            )
            lookup[str(incl_uri)] = cur.fetchone()[0]

    # key_learning_point
    for lesson_uri in instances(CURRIC.Lesson):
        lesson_id = lookup.get(str(lesson_uri))
        if lesson_id is None:
            continue
        for klp_uri in g.objects(lesson_uri, CURRIC.hasKeyLearningPoint):
            if not isinstance(klp_uri, URIRef):
                continue
            cur.execute(
                "INSERT INTO key_learning_point (uri, name, lesson_id) VALUES (%s, %s, %s) RETURNING id",
                (str(klp_uri), lit_str(g, klp_uri, RDFS.label) or "", lesson_id),
            )
            lookup[str(klp_uri)] = cur.fetchone()[0]

    # pupil_lesson_outcome
    for lesson_uri in instances(CURRIC.Lesson):
        lesson_id = lookup.get(str(lesson_uri))
        if lesson_id is None:
            continue
        for plo_uri in g.objects(lesson_uri, CURRIC.hasPupilLessonOutcome):
            if not isinstance(plo_uri, URIRef):
                continue
            cur.execute(
                "INSERT INTO pupil_lesson_outcome (uri, name, lesson_id) VALUES (%s, %s, %s) RETURNING id",
                (str(plo_uri), lit_str(g, plo_uri, RDFS.label) or "", lesson_id),
            )
            lookup[str(plo_uri)] = cur.fetchone()[0]

    # ------------------------------------------------------------------
    # Junction tables
    # ------------------------------------------------------------------

    for subj_uri in instances(CURRIC.Subject):
        subj_id = lookup.get(str(subj_uri))
        if subj_id is None:
            continue
        for strand_uri in g.objects(subj_uri, CURRIC.coversStrand):
            strand_id = lookup.get(str(strand_uri))
            if strand_id is not None:
                cur.execute(
                    "INSERT INTO subject_strand (subject_id, strand_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (subj_id, strand_id),
                )

    for prog_uri in instances(CURRIC.Progression):
        prog_id = lookup.get(str(prog_uri))
        if prog_id is None:
            continue
        for cd_uri in g.objects(prog_uri, CURRIC.coversContent):
            cd_id = lookup.get(str(cd_uri))
            if cd_id is not None:
                cur.execute(
                    "INSERT INTO progression_content_descriptor "
                    "(progression_id, content_descriptor_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (prog_id, cd_id),
                )

    for unit_uri in instances(CURRIC.Unit):
        unit_id = lookup.get(str(unit_uri))
        if unit_id is None:
            continue
        for thread_uri in g.objects(unit_uri, CURRIC.includesThread):
            thread_id = lookup.get(str(thread_uri))
            if thread_id is not None:
                cur.execute(
                    "INSERT INTO unit_thread (unit_id, thread_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (unit_id, thread_id),
                )
        for cd_uri in g.objects(unit_uri, CURRIC.includesContent):
            cd_id = lookup.get(str(cd_uri))
            if cd_id is not None:
                cur.execute(
                    "INSERT INTO unit_content_descriptor "
                    "(unit_id, content_descriptor_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (unit_id, cd_id),
                )

    for uvc_uri in instances(CURRIC.UnitVariantChoice):
        uvc_id = lookup.get(str(uvc_uri))
        if uvc_id is None:
            continue
        for uv_uri in g.objects(uvc_uri, CURRIC.hasUnitVariantOption):
            uv_id = lookup.get(str(uv_uri))
            if uv_id is not None:
                cur.execute(
                    "INSERT INTO unit_variant_choice_option "
                    "(unit_variant_choice_id, unit_variant_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (uvc_id, uv_id),
                )

    for lesson_uri in instances(CURRIC.Lesson):
        lesson_id = lookup.get(str(lesson_uri))
        if lesson_id is None:
            continue
        for kw_uri in g.objects(lesson_uri, CURRIC.hasKeyword):
            kw_id = lookup.get(str(kw_uri))
            if kw_id is not None:
                cur.execute(
                    "INSERT INTO lesson_keyword (lesson_id, keyword_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (lesson_id, kw_id),
                )
        for mc_uri in g.objects(lesson_uri, CURRIC.hasMisconception):
            mc_id = lookup.get(str(mc_uri))
            if mc_id is not None:
                cur.execute(
                    "INSERT INTO lesson_misconception (lesson_id, misconception_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (lesson_id, mc_id),
                )

    # ------------------------------------------------------------------
    # Subject aims
    # ------------------------------------------------------------------

    for subj_uri in instances(CURRIC.Subject):
        subj_id = lookup.get(str(subj_uri))
        if subj_id is None:
            continue
        list_head = None
        for obj in g.objects(subj_uri, CURRIC.aims):
            if isinstance(obj, (URIRef, BNode)):
                list_head = obj
                break
        if list_head is None:
            continue
        aims = list(Collection(g, list_head))
        for ordinal, aim_literal in enumerate(aims, start=1):
            cur.execute(
                "INSERT INTO subject_aim (subject_id, ordinal, aim_text) VALUES (%s, %s, %s)",
                (subj_id, ordinal, str(aim_literal)),
            )

    conn.commit()


def print_counts(conn: "psycopg2.extensions.connection"):
    """Print row counts for all tables."""
    cur = conn.cursor()
    cur.execute("""
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    """)
    tables = [row[0] for row in cur.fetchall()]
    print("\nRow counts:")
    print("-" * 40)
    total = 0
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        total += count
        print(f"  {table:40s} {count:>5}")
    print("-" * 40)
    print(f"  {'TOTAL':40s} {total:>5}")


def main():
    parser = argparse.ArgumentParser(
        description="Load Oak Curriculum RDF data into PostgreSQL"
    )
    parser.add_argument(
        "--schema", default=None,
        help="Path to PostgreSQL schema SQL file (default: <repo>/distributions/oak-curriculum-schema-postgres.sql)",
    )
    parser.add_argument(
        "--dsn", default=None,
        help="PostgreSQL connection string (default: use PG* environment variables)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    schema_path = (
        Path(args.schema)
        if args.schema
        else repo_root / "distributions" / "oak-curriculum-schema-postgres.sql"
    )

    if not schema_path.exists():
        sys.exit(f"Schema file not found: {schema_path}")

    print(f"Schema:  {schema_path}")
    print(f"DSN:     {args.dsn or '(from PG* environment variables)'}")
    print()

    g = parse_ttl_files(repo_root)
    conn = connect_db(args.dsn)
    try:
        create_schema(conn, schema_path)
        load_data(g, conn)
        print_counts(conn)
    finally:
        conn.close()

    print("\nDone.")


if __name__ == "__main__":
    main()
