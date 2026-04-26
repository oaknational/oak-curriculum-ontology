#!/usr/bin/env python3
"""
load_rdf_to_sqlite.py

Parse the Oak Curriculum ontology and data TTL files, then create and populate
a SQLite database using oak-curriculum-schema-sqlite.sql.

Usage:
    python scripts/load_rdf_to_sqlite.py
    python scripts/load_rdf_to_sqlite.py --db /path/to/output.sqlite
    python scripts/load_rdf_to_sqlite.py --schema distributions/oak-curriculum-schema-sqlite.sql
"""

import argparse
import sqlite3
import sys
from pathlib import Path

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


def create_database(db_path: Path, schema_path: Path) -> sqlite3.Connection:
    """Create SQLite database from schema DDL."""
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    ddl = schema_path.read_text()
    conn.executescript(ddl)
    return conn


def lit_str(g: Graph, subj: URIRef, pred: URIRef) -> str | None:
    """Get a single literal string value for a predicate, or None."""
    for obj in g.objects(subj, pred):
        if isinstance(obj, Literal):
            return str(obj)
    return None


def lit_int(g: Graph, subj: URIRef, pred: URIRef) -> int | None:
    """Get a single literal integer value for a predicate, or None."""
    for obj in g.objects(subj, pred):
        if isinstance(obj, Literal):
            try:
                return int(obj)
            except (ValueError, TypeError):
                return None
    return None


def lit_bool(g: Graph, subj: URIRef, pred: URIRef) -> int | None:
    """Get a boolean as 0/1 integer (SQLite has no BOOLEAN type), or None."""
    for obj in g.objects(subj, pred):
        if isinstance(obj, Literal):
            return 1 if bool(obj) else 0
    return None


def fk_uri(g: Graph, subj: URIRef, pred: URIRef) -> URIRef | None:
    """Get a single object URI for a predicate, or None."""
    for obj in g.objects(subj, pred):
        if isinstance(obj, URIRef):
            return obj
    return None


def resolve_fk(uri: URIRef | None, lookup: dict) -> int | None:
    """Resolve a URI to a row id via lookup dict."""
    if uri is None:
        return None
    return lookup.get(str(uri))


def load_data(g: Graph, conn: sqlite3.Connection):
    """Load RDF instance data into SQLite tables in FK-dependency order."""
    cur = conn.cursor()
    lookup: dict[str, int] = {}

    def insert(table: str, uri: URIRef, values: dict) -> int:
        values["uri"] = str(uri)
        cols = ", ".join(values.keys())
        placeholders = ", ".join(["?"] * len(values))
        cur.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
            list(values.values()),
        )
        row_id = cur.lastrowid
        lookup[str(uri)] = row_id
        return row_id

    def instances(rdf_class: URIRef) -> list[URIRef]:
        return sorted(set(g.subjects(RDF.type, rdf_class)), key=str)

    # ------------------------------------------------------------------
    # Tier 1: no FK dependencies
    # ------------------------------------------------------------------

    # phase
    for uri in instances(CURRIC.Phase):
        insert("phase", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
            "lower_age_boundary": lit_int(g, uri, CURRIC.lowerAgeBoundary),
            "upper_age_boundary": lit_int(g, uri, CURRIC.upperAgeBoundary),
        })

    # discipline (skos:prefLabel / skos:definition)
    for uri in instances(CURRIC.Discipline):
        insert("discipline", uri, {
            "name": lit_str(g, uri, SKOS.prefLabel) or "",
            "description": lit_str(g, uri, SKOS.definition),
        })

    # exam_board
    for uri in instances(CURRIC.ExamBoard):
        insert("exam_board", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
            "website": lit_str(g, uri, CURRIC.website),
            "accreditation_body": lit_str(g, uri, CURRIC.accreditationBody),
        })

    # tier
    for uri in instances(CURRIC.Tier):
        insert("tier", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
        })

    # thread
    for uri in instances(CURRIC.Thread):
        insert("thread", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
        })

    # keyword (uses schema:name and schema:description)
    for uri in instances(CURRIC.Keyword):
        insert("keyword", uri, {
            "name": lit_str(g, uri, SCHEMA.name) or "",
            "description": lit_str(g, uri, SCHEMA.description),
        })

    # misconception
    for uri in instances(CURRIC.Misconception):
        insert("misconception", uri, {
            "statement": lit_str(g, uri, CURRIC.statement) or "",
            "correction": lit_str(g, uri, CURRIC.correction) or "",
        })

    # ------------------------------------------------------------------
    # Tier 2: depends on Tier 1
    # ------------------------------------------------------------------

    # key_stage (FK -> phase via curric:isKeyStageOf)
    for uri in instances(CURRIC.KeyStage):
        phase_uri = fk_uri(g, uri, CURRIC.isKeyStageOf)
        insert("key_stage", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
            "lower_age_boundary": lit_int(g, uri, CURRIC.lowerAgeBoundary),
            "upper_age_boundary": lit_int(g, uri, CURRIC.upperAgeBoundary),
            "phase_id": resolve_fk(phase_uri, lookup),
        })

    # strand (FK -> discipline via skos:broader)
    for uri in instances(CURRIC.Strand):
        broader_uri = fk_uri(g, uri, SKOS.broader)
        insert("strand", uri, {
            "name": lit_str(g, uri, SKOS.prefLabel) or "",
            "description": lit_str(g, uri, SKOS.definition),
            "display_order": lit_int(g, uri, CURRIC.displayOrder),
            "discipline_id": resolve_fk(broader_uri, lookup),
        })

    # subject_group (FK -> discipline via curric:coversDiscipline)
    for uri in instances(CURRIC.SubjectGroup):
        disc_uri = fk_uri(g, uri, CURRIC.coversDiscipline)
        insert("subject_group", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "discipline_id": resolve_fk(disc_uri, lookup),
        })

    # ------------------------------------------------------------------
    # Tier 3: depends on Tier 2
    # ------------------------------------------------------------------

    # year_group (FK -> key_stage via curric:isYearGroupOf)
    for uri in instances(CURRIC.YearGroup):
        ks_uri = fk_uri(g, uri, CURRIC.isYearGroupOf)
        insert("year_group", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
            "lower_age_boundary": lit_int(g, uri, CURRIC.lowerAgeBoundary),
            "upper_age_boundary": lit_int(g, uri, CURRIC.upperAgeBoundary),
            "key_stage_id": resolve_fk(ks_uri, lookup),
        })

    # sub_strand (FK -> strand via skos:broader)
    for uri in instances(CURRIC.SubStrand):
        broader_uri = fk_uri(g, uri, SKOS.broader)
        insert("sub_strand", uri, {
            "name": lit_str(g, uri, SKOS.prefLabel) or "",
            "description": lit_str(g, uri, SKOS.definition),
            "display_order": lit_int(g, uri, CURRIC.displayOrder),
            "strand_id": resolve_fk(broader_uri, lookup),
        })

    # subject (FK -> subject_group via curric:isSubjectOf)
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

    # content_descriptor (FK -> sub_strand via skos:broader)
    for uri in instances(CURRIC.ContentDescriptor):
        broader_uri = fk_uri(g, uri, SKOS.broader)
        insert("content_descriptor", uri, {
            "name": lit_str(g, uri, SKOS.prefLabel) or "",
            "supporting_guidance": lit_str(g, uri, CURRIC.supportingGuidance),
            "display_order": lit_int(g, uri, CURRIC.displayOrder),
            "sub_strand_id": resolve_fk(broader_uri, lookup),
        })

    # scheme (FK -> subject via curric:isSchemeOf, FK -> key_stage via curric:coversKeyStage)
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

    # progression (FK -> scheme via curric:isProgressionOf)
    for uri in instances(CURRIC.Progression):
        scheme_uri = fk_uri(g, uri, CURRIC.isProgressionOf)
        insert("progression", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
            "scheme_id": resolve_fk(scheme_uri, lookup),
        })

    # programme (FK -> scheme, year_group; optional exam_board, tier)
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

    # unit (FK -> scheme via curric:isUnitOf)
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

    # unit_variant_choice (grouping node; options are in unit_variant_choice_option)
    for uri in instances(CURRIC.UnitVariantChoice):
        insert("unit_variant_choice", uri, {
            "name": lit_str(g, uri, RDFS.label) or "",
        })

    # unit_variant (FK -> unit via curric:isUnitVariantOf)
    for uri in instances(CURRIC.UnitVariant):
        unit_uri = fk_uri(g, uri, CURRIC.isUnitVariantOf)
        insert("unit_variant", uri, {
            "oak_id": lit_int(g, uri, CURRIC.id),
            "name": lit_str(g, uri, RDFS.label) or "",
            "unit_id": resolve_fk(unit_uri, lookup),
        })

    # lesson (oak_id is required: curric:id minCount 1)
    for uri in instances(CURRIC.Lesson):
        insert("lesson", uri, {
            "oak_id": lit_int(g, uri, CURRIC.id) or 0,
            "name": lit_str(g, uri, RDFS.label) or "",
        })

    # ------------------------------------------------------------------
    # Tier 7: depends on Tier 6
    # ------------------------------------------------------------------

    # unit_variant_inclusion (FK -> programme; either unit_variant or unit_variant_choice)
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
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
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
            lookup[str(incl_uri)] = cur.lastrowid

    # lesson_inclusion (FK -> unit_variant; found via curric:hasLessonInclusion)
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
                "VALUES (?, ?, ?, ?)",
                (
                    str(incl_uri),
                    lit_int(g, incl_uri, CURRIC.sequencePosition),
                    uv_id,
                    resolve_fk(lesson_uri, lookup),
                ),
            )
            lookup[str(incl_uri)] = cur.lastrowid

    # key_learning_point (FK -> lesson via curric:hasKeyLearningPoint)
    for lesson_uri in instances(CURRIC.Lesson):
        lesson_id = lookup.get(str(lesson_uri))
        if lesson_id is None:
            continue
        for klp_uri in g.objects(lesson_uri, CURRIC.hasKeyLearningPoint):
            if not isinstance(klp_uri, URIRef):
                continue
            cur.execute(
                "INSERT INTO key_learning_point (uri, name, lesson_id) VALUES (?, ?, ?)",
                (
                    str(klp_uri),
                    lit_str(g, klp_uri, RDFS.label) or "",
                    lesson_id,
                ),
            )
            lookup[str(klp_uri)] = cur.lastrowid

    # pupil_lesson_outcome (FK -> lesson via curric:hasPupilLessonOutcome)
    for lesson_uri in instances(CURRIC.Lesson):
        lesson_id = lookup.get(str(lesson_uri))
        if lesson_id is None:
            continue
        for plo_uri in g.objects(lesson_uri, CURRIC.hasPupilLessonOutcome):
            if not isinstance(plo_uri, URIRef):
                continue
            cur.execute(
                "INSERT INTO pupil_lesson_outcome (uri, name, lesson_id) VALUES (?, ?, ?)",
                (
                    str(plo_uri),
                    lit_str(g, plo_uri, RDFS.label) or "",
                    lesson_id,
                ),
            )
            lookup[str(plo_uri)] = cur.lastrowid

    # ------------------------------------------------------------------
    # Junction tables
    # ------------------------------------------------------------------

    # subject_strand
    for subj_uri in instances(CURRIC.Subject):
        subj_id = lookup.get(str(subj_uri))
        if subj_id is None:
            continue
        for strand_uri in g.objects(subj_uri, CURRIC.coversStrand):
            strand_id = lookup.get(str(strand_uri))
            if strand_id is not None:
                cur.execute(
                    "INSERT OR IGNORE INTO subject_strand (subject_id, strand_id) VALUES (?, ?)",
                    (subj_id, strand_id),
                )

    # progression_content_descriptor
    for prog_uri in instances(CURRIC.Progression):
        prog_id = lookup.get(str(prog_uri))
        if prog_id is None:
            continue
        for cd_uri in g.objects(prog_uri, CURRIC.coversContent):
            cd_id = lookup.get(str(cd_uri))
            if cd_id is not None:
                cur.execute(
                    "INSERT OR IGNORE INTO progression_content_descriptor "
                    "(progression_id, content_descriptor_id) VALUES (?, ?)",
                    (prog_id, cd_id),
                )

    # unit_thread
    for unit_uri in instances(CURRIC.Unit):
        unit_id = lookup.get(str(unit_uri))
        if unit_id is None:
            continue
        for thread_uri in g.objects(unit_uri, CURRIC.includesThread):
            thread_id = lookup.get(str(thread_uri))
            if thread_id is not None:
                cur.execute(
                    "INSERT OR IGNORE INTO unit_thread (unit_id, thread_id) VALUES (?, ?)",
                    (unit_id, thread_id),
                )

    # unit_content_descriptor
    for unit_uri in instances(CURRIC.Unit):
        unit_id = lookup.get(str(unit_uri))
        if unit_id is None:
            continue
        for cd_uri in g.objects(unit_uri, CURRIC.includesContent):
            cd_id = lookup.get(str(cd_uri))
            if cd_id is not None:
                cur.execute(
                    "INSERT OR IGNORE INTO unit_content_descriptor "
                    "(unit_id, content_descriptor_id) VALUES (?, ?)",
                    (unit_id, cd_id),
                )

    # unit_variant_choice_option
    for uvc_uri in instances(CURRIC.UnitVariantChoice):
        uvc_id = lookup.get(str(uvc_uri))
        if uvc_id is None:
            continue
        for uv_uri in g.objects(uvc_uri, CURRIC.hasUnitVariantOption):
            uv_id = lookup.get(str(uv_uri))
            if uv_id is not None:
                cur.execute(
                    "INSERT OR IGNORE INTO unit_variant_choice_option "
                    "(unit_variant_choice_id, unit_variant_id) VALUES (?, ?)",
                    (uvc_id, uv_id),
                )

    # lesson_keyword
    for lesson_uri in instances(CURRIC.Lesson):
        lesson_id = lookup.get(str(lesson_uri))
        if lesson_id is None:
            continue
        for kw_uri in g.objects(lesson_uri, CURRIC.hasKeyword):
            kw_id = lookup.get(str(kw_uri))
            if kw_id is not None:
                cur.execute(
                    "INSERT OR IGNORE INTO lesson_keyword (lesson_id, keyword_id) VALUES (?, ?)",
                    (lesson_id, kw_id),
                )

    # lesson_misconception
    for lesson_uri in instances(CURRIC.Lesson):
        lesson_id = lookup.get(str(lesson_uri))
        if lesson_id is None:
            continue
        for mc_uri in g.objects(lesson_uri, CURRIC.hasMisconception):
            mc_id = lookup.get(str(mc_uri))
            if mc_id is not None:
                cur.execute(
                    "INSERT OR IGNORE INTO lesson_misconception "
                    "(lesson_id, misconception_id) VALUES (?, ?)",
                    (lesson_id, mc_id),
                )

    # ------------------------------------------------------------------
    # Subject aims (curric:aims -> rdf:List of literals)
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
                "INSERT INTO subject_aim (subject_id, ordinal, aim_text) VALUES (?, ?, ?)",
                (subj_id, ordinal, str(aim_literal)),
            )

    conn.commit()


def print_counts(conn: sqlite3.Connection):
    """Print row counts for all tables."""
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
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
        description="Load Oak Curriculum RDF data into SQLite"
    )
    parser.add_argument(
        "--schema", default=None,
        help="Path to SQLite schema SQL file (default: <repo>/distributions/oak-curriculum-schema-sqlite.sql)",
    )
    parser.add_argument(
        "--db", default=None,
        help="Output SQLite database path (default: <repo>/oak-curriculum.sqlite)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    schema_path = (
        Path(args.schema)
        if args.schema
        else repo_root / "distributions" / "oak-curriculum-schema-sqlite.sql"
    )
    db_path = Path(args.db) if args.db else repo_root / "distributions" / "oak-curriculum.sqlite"

    if not schema_path.exists():
        sys.exit(f"Schema file not found: {schema_path}")

    print(f"Schema:  {schema_path}")
    print(f"Output:  {db_path}")
    print()

    g = parse_ttl_files(repo_root)
    conn = create_database(db_path, schema_path)
    try:
        load_data(g, conn)
        print_counts(conn)
    finally:
        conn.close()

    print(f"\nDone. Database written to {db_path}")


if __name__ == "__main__":
    main()
