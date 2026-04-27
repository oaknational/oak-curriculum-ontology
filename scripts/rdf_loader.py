#!/usr/bin/env python3
"""
rdf_loader.py

Shared utilities for loading Oak Curriculum RDF data into relational databases.

Provides:
  - RDF graph helpers (parse_ttl_files, literal extractors, FK resolution)
  - DbAdapter ABC with SQLiteAdapter and PostgresAdapter implementations
  - load_data: full tier-ordered INSERT logic, parameterised via DbAdapter
  - print_counts: table row summary
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from rdflib import BNode, Graph, Namespace, RDF, RDFS, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import SKOS

log = logging.getLogger(__name__)

CURRIC = Namespace("https://w3id.org/uk/oak/curriculum/ontology/")
SCHEMA = Namespace("http://schema.org/")

_ONTOLOGY_DIR = "ontology"
_DATA_DIR = "data"


# ---------------------------------------------------------------------------
# RDF graph helpers
# ---------------------------------------------------------------------------

def parse_ttl_files(repo_root: Path) -> Graph:
    """Parse all .ttl files from ontology/ and data/ directories."""
    g = Graph()
    count = 0
    for dir_path in [repo_root / _ONTOLOGY_DIR, repo_root / _DATA_DIR]:
        if not dir_path.exists():
            continue
        for ttl_file in sorted(dir_path.rglob("*.ttl")):
            g.parse(ttl_file, format="turtle")
            count += 1
    log.info("Parsed %d TTL files (%d triples)", count, len(g))
    return g


def lit_str(g: Graph, subj: URIRef, pred: URIRef) -> str | None:
    """Return the first literal string value for a predicate, or None."""
    for obj in g.objects(subj, pred):
        if isinstance(obj, Literal):
            return str(obj)
    return None


def lit_int(g: Graph, subj: URIRef, pred: URIRef) -> int | None:
    """Return the first literal integer value for a predicate, or None."""
    for obj in g.objects(subj, pred):
        if isinstance(obj, Literal):
            try:
                return int(obj)
            except (ValueError, TypeError):
                return None
    return None


def lit_bool(g: Graph, subj: URIRef, pred: URIRef) -> bool | None:
    """Return the first literal boolean value for a predicate, or None.

    Both sqlite3 and psycopg2 accept Python bool for their respective column
    types (INTEGER and BOOLEAN), so no adapter-specific coercion is needed.
    """
    for obj in g.objects(subj, pred):
        if isinstance(obj, Literal):
            return bool(obj)
    return None


def fk_uri(g: Graph, subj: URIRef, pred: URIRef) -> URIRef | None:
    """Return the first object URI for a predicate, or None."""
    for obj in g.objects(subj, pred):
        if isinstance(obj, URIRef):
            return obj
    return None


def resolve_fk(uri: URIRef | None, lookup: dict[str, int]) -> int | None:
    """Resolve a URI to a surrogate row id via the URI->id lookup."""
    if uri is None:
        return None
    return lookup.get(str(uri))


# ---------------------------------------------------------------------------
# Database adapter
# ---------------------------------------------------------------------------

class DbAdapter(ABC):
    """Abstracts the SQL differences between SQLite and PostgreSQL."""

    @abstractmethod
    def bulk_insert(
        self, cur: Any, table: str, rows: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Bulk-insert rows (each must have a 'uri' key) and return {uri: id}."""

    @abstractmethod
    def bulk_insert_ignore(
        self,
        cur: Any,
        table: str,
        col_a: str,
        col_b: str,
        pairs: list[tuple[int, int]],
    ) -> None:
        """Bulk-insert junction table rows, skipping duplicates."""

    @abstractmethod
    def bulk_execute(
        self, cur: Any, table: str, cols: list[str], rows: list[tuple]
    ) -> None:
        """Bulk-INSERT rows without returning IDs (for tables without a URI key)."""

    @abstractmethod
    def table_names(self, cur: Any) -> list[str]:
        """Return all user table names (for print_counts)."""


class SQLiteAdapter(DbAdapter):
    def bulk_insert(
        self, cur: Any, table: str, rows: list[dict[str, Any]]
    ) -> dict[str, int]:
        if not rows:
            return {}
        cols = list(rows[0].keys())
        phs = ", ".join(["?"] * len(cols))
        sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({phs})"
        result: dict[str, int] = {}
        for row in rows:
            cur.execute(sql, tuple(row[c] for c in cols))
            result[row["uri"]] = cur.lastrowid
        return result

    def bulk_insert_ignore(
        self,
        cur: Any,
        table: str,
        col_a: str,
        col_b: str,
        pairs: list[tuple[int, int]],
    ) -> None:
        if not pairs:
            return
        cur.executemany(
            f"INSERT OR IGNORE INTO {table} ({col_a}, {col_b}) VALUES (?, ?)",
            pairs,
        )

    def bulk_execute(
        self, cur: Any, table: str, cols: list[str], rows: list[tuple]
    ) -> None:
        if not rows:
            return
        phs = ", ".join(["?"] * len(cols))
        cur.executemany(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({phs})",
            rows,
        )

    def table_names(self, cur: Any) -> list[str]:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        return [row[0] for row in cur.fetchall()]


class PostgresAdapter(DbAdapter):
    def bulk_insert(
        self, cur: Any, table: str, rows: list[dict[str, Any]]
    ) -> dict[str, int]:
        if not rows:
            return {}
        from psycopg2.extras import execute_values
        cols = list(rows[0].keys())
        values = [tuple(r[c] for c in cols) for r in rows]
        rows = execute_values(
            cur,
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES %s RETURNING id, uri",
            values,
            fetch=True,
        )
        return {uri: row_id for row_id, uri in rows}

    def bulk_insert_ignore(
        self,
        cur: Any,
        table: str,
        col_a: str,
        col_b: str,
        pairs: list[tuple[int, int]],
    ) -> None:
        if not pairs:
            return
        from psycopg2.extras import execute_values
        execute_values(
            cur,
            f"INSERT INTO {table} ({col_a}, {col_b}) VALUES %s ON CONFLICT DO NOTHING",
            pairs,
        )

    def bulk_execute(
        self, cur: Any, table: str, cols: list[str], rows: list[tuple]
    ) -> None:
        if not rows:
            return
        from psycopg2.extras import execute_values
        execute_values(
            cur,
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES %s",
            rows,
        )

    def table_names(self, cur: Any) -> list[str]:
        cur.execute(
            "SELECT tablename FROM pg_tables"
            " WHERE schemaname = 'public' ORDER BY tablename"
        )
        return [row[0] for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Core data loading
# ---------------------------------------------------------------------------

def load_data(g: Graph, cur: Any, adapter: DbAdapter) -> dict[str, int]:
    """Load RDF instance data into relational tables in FK-dependency order.

    Args:
        g:       Fully parsed RDF graph (ontology + data).
        cur:     An open database cursor.
        adapter: DbAdapter instance matching the target database.

    Returns:
        A URI-string -> surrogate-id lookup dict (useful for callers that need
        to reference inserted rows).
    """
    lookup: dict[str, int] = {}

    def instances(rdf_class: URIRef) -> list[URIRef]:
        return sorted(set(g.subjects(RDF.type, rdf_class)), key=str)

    # ------------------------------------------------------------------
    # Tier 1: no FK dependencies
    # ------------------------------------------------------------------

    _batch = instances(CURRIC.Phase)
    log.info("  phase: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "phase", [
        {
            "uri": str(uri),
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
            "lower_age_boundary": lit_int(g, uri, CURRIC.lowerAgeBoundary),
            "upper_age_boundary": lit_int(g, uri, CURRIC.upperAgeBoundary),
        }
        for uri in _batch
    ]))

    _batch = instances(CURRIC.Discipline)
    log.info("  discipline: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "discipline", [
        {"uri": str(uri), "name": lit_str(g, uri, SKOS.prefLabel) or ""}
        for uri in _batch
    ]))

    _batch = instances(CURRIC.ExamBoard)
    log.info("  exam_board: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "exam_board", [
        {
            "uri": str(uri),
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
            "website": lit_str(g, uri, CURRIC.website),
            "accreditation_body": lit_str(g, uri, CURRIC.accreditationBody),
        }
        for uri in _batch
    ]))

    _batch = instances(CURRIC.Tier)
    log.info("  tier: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "tier", [
        {
            "uri": str(uri),
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
        }
        for uri in _batch
    ]))

    _batch = instances(CURRIC.Thread)
    log.info("  thread: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "thread", [
        {
            "uri": str(uri),
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
        }
        for uri in _batch
    ]))

    _batch = instances(CURRIC.Keyword)
    log.info("  keyword: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "keyword", [
        {
            "uri": str(uri),
            "name": lit_str(g, uri, SCHEMA.name) or "",
            "description": lit_str(g, uri, SCHEMA.description),
        }
        for uri in _batch
    ]))

    _batch = instances(CURRIC.Misconception)
    log.info("  misconception: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "misconception", [
        {
            "uri": str(uri),
            "statement": lit_str(g, uri, CURRIC.statement) or "",
            "correction": lit_str(g, uri, CURRIC.correction) or "",
        }
        for uri in _batch
    ]))

    # ------------------------------------------------------------------
    # Tier 2: depends on Tier 1
    # ------------------------------------------------------------------

    _batch = instances(CURRIC.KeyStage)
    log.info("  key_stage: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "key_stage", [
        {
            "uri": str(uri),
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
            "lower_age_boundary": lit_int(g, uri, CURRIC.lowerAgeBoundary),
            "upper_age_boundary": lit_int(g, uri, CURRIC.upperAgeBoundary),
            "phase_id": resolve_fk(fk_uri(g, uri, CURRIC.isKeyStageOf), lookup),
        }
        for uri in _batch
    ]))

    _batch = instances(CURRIC.Strand)
    log.info("  strand: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "strand", [
        {
            "uri": str(uri),
            "name": lit_str(g, uri, SKOS.prefLabel) or "",
            "description": lit_str(g, uri, SKOS.definition),
            "display_order": lit_int(g, uri, CURRIC.displayOrder),
            "discipline_id": resolve_fk(fk_uri(g, uri, SKOS.broader), lookup),
        }
        for uri in _batch
    ]))

    _batch = instances(CURRIC.SubjectGroup)
    log.info("  subject_group: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "subject_group", [
        {
            "uri": str(uri),
            "name": lit_str(g, uri, RDFS.label) or "",
            "discipline_id": resolve_fk(fk_uri(g, uri, CURRIC.coversDiscipline), lookup),
        }
        for uri in _batch
    ]))

    # ------------------------------------------------------------------
    # Tier 3: depends on Tier 2
    # ------------------------------------------------------------------

    _batch = instances(CURRIC.YearGroup)
    log.info("  year_group: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "year_group", [
        {
            "uri": str(uri),
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
            "lower_age_boundary": lit_int(g, uri, CURRIC.lowerAgeBoundary),
            "upper_age_boundary": lit_int(g, uri, CURRIC.upperAgeBoundary),
            "key_stage_id": resolve_fk(fk_uri(g, uri, CURRIC.isYearGroupOf), lookup),
        }
        for uri in _batch
    ]))

    _batch = instances(CURRIC.SubStrand)
    log.info("  sub_strand: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "sub_strand", [
        {
            "uri": str(uri),
            "name": lit_str(g, uri, SKOS.prefLabel) or "",
            "description": lit_str(g, uri, SKOS.definition),
            "display_order": lit_int(g, uri, CURRIC.displayOrder),
            "strand_id": resolve_fk(fk_uri(g, uri, SKOS.broader), lookup),
        }
        for uri in _batch
    ]))

    _batch = instances(CURRIC.Subject)
    log.info("  subject: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "subject", [
        {
            "uri": str(uri),
            "name": lit_str(g, uri, RDFS.label) or "",
            "rationale": lit_str(g, uri, CURRIC.rationale),
            "school_curriculum": lit_str(g, uri, CURRIC.schoolCurriculum),
            "subject_group_id": resolve_fk(fk_uri(g, uri, CURRIC.isSubjectOf), lookup),
        }
        for uri in _batch
    ]))

    # ------------------------------------------------------------------
    # Tier 4: depends on Tier 3
    # ------------------------------------------------------------------

    _batch = instances(CURRIC.ContentDescriptor)
    log.info("  content_descriptor: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "content_descriptor", [
        {
            "uri": str(uri),
            "name": lit_str(g, uri, SKOS.prefLabel) or "",
            "supporting_guidance": lit_str(g, uri, CURRIC.supportingGuidance),
            "display_order": lit_int(g, uri, CURRIC.displayOrder),
            "sub_strand_id": resolve_fk(fk_uri(g, uri, SKOS.broader), lookup),
        }
        for uri in _batch
    ]))

    _batch = instances(CURRIC.Scheme)
    log.info("  scheme: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "scheme", [
        {
            "uri": str(uri),
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
            "subject_id": resolve_fk(fk_uri(g, uri, CURRIC.isSchemeOf), lookup),
            "key_stage_id": resolve_fk(fk_uri(g, uri, CURRIC.coversKeyStage), lookup),
        }
        for uri in _batch
    ]))

    # ------------------------------------------------------------------
    # Tier 5: depends on Tier 4
    # ------------------------------------------------------------------

    _batch = instances(CURRIC.Progression)
    log.info("  progression: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "progression", [
        {
            "uri": str(uri),
            "name": lit_str(g, uri, RDFS.label) or "",
            "scheme_id": resolve_fk(fk_uri(g, uri, CURRIC.isProgressionOf), lookup),
        }
        for uri in _batch
    ]))

    _batch = instances(CURRIC.Programme)
    log.info("  programme: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "programme", [
        {
            "uri": str(uri),
            "name": lit_str(g, uri, RDFS.label) or "",
            "is_national_curriculum": lit_bool(g, uri, CURRIC.isNationalCurriculum),
            "is_required": lit_bool(g, uri, CURRIC.isRequired),
            "is_examined": lit_bool(g, uri, CURRIC.isExamined),
            "exam_type": lit_str(g, uri, CURRIC.examType),
            "scheme_id": resolve_fk(fk_uri(g, uri, CURRIC.isProgrammeOf), lookup),
            "year_group_id": resolve_fk(fk_uri(g, uri, CURRIC.coversYearGroup), lookup),
            "exam_board_id": resolve_fk(fk_uri(g, uri, CURRIC.hasExamBoard), lookup),
            "tier_id": resolve_fk(fk_uri(g, uri, CURRIC.hasTier), lookup),
        }
        for uri in _batch
    ]))

    _batch = instances(CURRIC.Unit)
    log.info("  unit: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "unit", [
        {
            "uri": str(uri),
            "oak_id": lit_int(g, uri, CURRIC.id),
            "name": lit_str(g, uri, RDFS.label) or "",
            "description": lit_str(g, uri, RDFS.comment),
            "why_this_why_now": lit_str(g, uri, CURRIC.whyThisWhyNow) or "",
            "unit_prior_knowledge_requirements": lit_str(
                g, uri, CURRIC.unitPriorKnowledgeRequirements
            ) or "",
            "scheme_id": resolve_fk(fk_uri(g, uri, CURRIC.isUnitOf), lookup),
        }
        for uri in _batch
    ]))

    # ------------------------------------------------------------------
    # Tier 6: depends on Tier 5
    # ------------------------------------------------------------------

    _batch = instances(CURRIC.UnitVariantChoice)
    log.info("  unit_variant_choice: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "unit_variant_choice", [
        {"uri": str(uri), "name": lit_str(g, uri, RDFS.label) or ""}
        for uri in _batch
    ]))

    _batch = instances(CURRIC.UnitVariant)
    log.info("  unit_variant: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "unit_variant", [
        {
            "uri": str(uri),
            "oak_id": lit_int(g, uri, CURRIC.id),
            "name": lit_str(g, uri, RDFS.label) or "",
            "unit_id": resolve_fk(fk_uri(g, uri, CURRIC.isUnitVariantOf), lookup),
        }
        for uri in _batch
    ]))

    _batch = instances(CURRIC.Lesson)
    log.info("  lesson: %d", len(_batch))
    lookup.update(adapter.bulk_insert(cur, "lesson", [
        {
            "uri": str(uri),
            "oak_id": lit_int(g, uri, CURRIC.id) or 0,
            "name": lit_str(g, uri, RDFS.label) or "",
        }
        for uri in _batch
    ]))

    # ------------------------------------------------------------------
    # Tier 7: depends on Tier 6
    # ------------------------------------------------------------------

    # unit_variant_inclusion (FK -> programme; either unit_variant or unit_variant_choice)
    _rows: list[dict[str, Any]] = []
    for prog_uri in instances(CURRIC.Programme):
        prog_id = lookup.get(str(prog_uri))
        if prog_id is None:
            continue
        for incl_uri in g.objects(prog_uri, CURRIC.hasUnitVariantInclusion):
            if not isinstance(incl_uri, URIRef):
                continue
            _rows.append({
                "uri": str(incl_uri),
                "sequence_position": lit_int(g, incl_uri, CURRIC.sequencePosition),
                "min_choices": lit_int(g, incl_uri, CURRIC.minChoices),
                "max_choices": lit_int(g, incl_uri, CURRIC.maxChoices),
                "programme_id": prog_id,
                "unit_variant_id": resolve_fk(
                    fk_uri(g, incl_uri, CURRIC.includesUnitVariant), lookup
                ),
                "unit_variant_choice_id": resolve_fk(
                    fk_uri(g, incl_uri, CURRIC.includesUnitVariantChoice), lookup
                ),
            })
    log.info("  unit_variant_inclusion: %d", len(_rows))
    lookup.update(adapter.bulk_insert(cur, "unit_variant_inclusion", _rows))

    # lesson_inclusion (FK -> unit_variant; found via hasLessonInclusion)
    _rows = []
    for uv_uri in instances(CURRIC.UnitVariant):
        uv_id = lookup.get(str(uv_uri))
        if uv_id is None:
            continue
        for incl_uri in g.objects(uv_uri, CURRIC.hasLessonInclusion):
            if not isinstance(incl_uri, URIRef):
                continue
            _rows.append({
                "uri": str(incl_uri),
                "sequence_position": lit_int(g, incl_uri, CURRIC.sequencePosition),
                "unit_variant_id": uv_id,
                "lesson_id": resolve_fk(fk_uri(g, incl_uri, CURRIC.includesLesson), lookup),
            })
    log.info("  lesson_inclusion: %d", len(_rows))
    lookup.update(adapter.bulk_insert(cur, "lesson_inclusion", _rows))

    # key_learning_point and pupil_lesson_outcome (nested under Lesson)
    _klp_rows: list[dict[str, Any]] = []
    _plo_rows: list[dict[str, Any]] = []
    for lesson_uri in instances(CURRIC.Lesson):
        lesson_id = lookup.get(str(lesson_uri))
        if lesson_id is None:
            continue
        for klp_uri in g.objects(lesson_uri, CURRIC.hasKeyLearningPoint):
            if not isinstance(klp_uri, URIRef):
                continue
            _klp_rows.append({
                "uri": str(klp_uri),
                "name": lit_str(g, klp_uri, RDFS.label) or "",
                "lesson_id": lesson_id,
            })
        for plo_uri in g.objects(lesson_uri, CURRIC.hasPupilLessonOutcome):
            if not isinstance(plo_uri, URIRef):
                continue
            _plo_rows.append({
                "uri": str(plo_uri),
                "name": lit_str(g, plo_uri, RDFS.label) or "",
                "lesson_id": lesson_id,
            })
    log.info("  key_learning_point: %d", len(_klp_rows))
    lookup.update(adapter.bulk_insert(cur, "key_learning_point", _klp_rows))
    log.info("  pupil_lesson_outcome: %d", len(_plo_rows))
    lookup.update(adapter.bulk_insert(cur, "pupil_lesson_outcome", _plo_rows))

    # ------------------------------------------------------------------
    # Junction tables
    # ------------------------------------------------------------------
    log.info("Junction tables")

    log.info("  subject_strand")
    _pairs: list[tuple[int, int]] = []
    for subj_uri in instances(CURRIC.Subject):
        subj_id = lookup.get(str(subj_uri))
        if subj_id is None:
            continue
        for strand_uri in g.objects(subj_uri, CURRIC.coversStrand):
            strand_id = lookup.get(str(strand_uri))
            if strand_id is not None:
                _pairs.append((subj_id, strand_id))
    adapter.bulk_insert_ignore(cur, "subject_strand", "subject_id", "strand_id", _pairs)

    log.info("  progression_content_descriptor")
    _pairs = []
    for prog_uri in instances(CURRIC.Progression):
        prog_id = lookup.get(str(prog_uri))
        if prog_id is None:
            continue
        for cd_uri in g.objects(prog_uri, CURRIC.coversContent):
            cd_id = lookup.get(str(cd_uri))
            if cd_id is not None:
                _pairs.append((prog_id, cd_id))
    adapter.bulk_insert_ignore(
        cur, "progression_content_descriptor",
        "progression_id", "content_descriptor_id", _pairs,
    )

    log.info("  unit_thread, unit_content_descriptor")
    _thread_pairs: list[tuple[int, int]] = []
    _cd_pairs: list[tuple[int, int]] = []
    for unit_uri in instances(CURRIC.Unit):
        unit_id = lookup.get(str(unit_uri))
        if unit_id is None:
            continue
        for thread_uri in g.objects(unit_uri, CURRIC.includesThread):
            thread_id = lookup.get(str(thread_uri))
            if thread_id is not None:
                _thread_pairs.append((unit_id, thread_id))
        for cd_uri in g.objects(unit_uri, CURRIC.includesContent):
            cd_id = lookup.get(str(cd_uri))
            if cd_id is not None:
                _cd_pairs.append((unit_id, cd_id))
    adapter.bulk_insert_ignore(cur, "unit_thread", "unit_id", "thread_id", _thread_pairs)
    adapter.bulk_insert_ignore(
        cur, "unit_content_descriptor",
        "unit_id", "content_descriptor_id", _cd_pairs,
    )

    log.info("  unit_variant_choice_option")
    _pairs = []
    for uvc_uri in instances(CURRIC.UnitVariantChoice):
        uvc_id = lookup.get(str(uvc_uri))
        if uvc_id is None:
            continue
        for uv_uri in g.objects(uvc_uri, CURRIC.hasUnitVariantOption):
            uv_id = lookup.get(str(uv_uri))
            if uv_id is not None:
                _pairs.append((uvc_id, uv_id))
    adapter.bulk_insert_ignore(
        cur, "unit_variant_choice_option",
        "unit_variant_choice_id", "unit_variant_id", _pairs,
    )

    log.info("  lesson_keyword, lesson_misconception")
    _kw_pairs: list[tuple[int, int]] = []
    _mc_pairs: list[tuple[int, int]] = []
    for lesson_uri in instances(CURRIC.Lesson):
        lesson_id = lookup.get(str(lesson_uri))
        if lesson_id is None:
            continue
        for kw_uri in g.objects(lesson_uri, CURRIC.hasKeyword):
            kw_id = lookup.get(str(kw_uri))
            if kw_id is not None:
                _kw_pairs.append((lesson_id, kw_id))
        for mc_uri in g.objects(lesson_uri, CURRIC.hasMisconception):
            mc_id = lookup.get(str(mc_uri))
            if mc_id is not None:
                _mc_pairs.append((lesson_id, mc_id))
    adapter.bulk_insert_ignore(cur, "lesson_keyword", "lesson_id", "keyword_id", _kw_pairs)
    adapter.bulk_insert_ignore(
        cur, "lesson_misconception",
        "lesson_id", "misconception_id", _mc_pairs,
    )

    # ------------------------------------------------------------------
    # Subject aims (curric:aims -> rdf:List of literals)
    # ------------------------------------------------------------------
    log.info("Subject aims")

    _aim_rows: list[tuple[int, int, str]] = []
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
        for ordinal, aim_literal in enumerate(Collection(g, list_head), start=1):
            _aim_rows.append((subj_id, ordinal, str(aim_literal)))
    adapter.bulk_execute(
        cur, "subject_aim", ["subject_id", "ordinal", "aim_text"], _aim_rows
    )

    log.info("Data load complete. %d URIs inserted.", len(lookup))
    return lookup


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_counts(cur: Any, adapter: DbAdapter) -> None:
    """Print a row-count summary for all user tables."""
    tables = adapter.table_names(cur)
    print("\nRow counts:")
    print("-" * 40)
    total = 0
    for table in tables:
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        count = cur.fetchone()[0]
        total += count
        print(f"  {table:40s} {count:>5}")
    print("-" * 40)
    print(f"  {'TOTAL':40s} {total:>5}")
