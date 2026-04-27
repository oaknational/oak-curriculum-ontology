#!/usr/bin/env python3
"""
Generate SQL relational schema (DDL) from the Oak Curriculum Ontology.

Introspects the ontology TTL file to derive tables, columns, foreign keys, and
junction tables for both PostgreSQL and SQLite dialects. Re-run this script
whenever the ontology changes to keep the schema files up to date.

Uses OWLready2 for ontology introspection and rdflib to handle Turtle parsing
(OWLready2 only supports RDF/XML and NTriples natively).

Usage:
    uv run scripts/generate_sql_schema.py --dialect postgres -o distributions/oak-curriculum-schema-postgres.sql
    uv run scripts/generate_sql_schema.py --dialect sqlite -o distributions/oak-curriculum-schema-sqlite.sql
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

try:
    from owlready2 import get_ontology, Thing, Or
except ImportError:
    sys.exit("owlready2 is required: pip install owlready2")

try:
    import rdflib
except ImportError:
    sys.exit("rdflib is required: pip install rdflib")

log = logging.getLogger(__name__)

DEFAULT_ONTOLOGY = (
    Path(__file__).resolve().parent.parent / "ontology" / "oak-curriculum-ontology.ttl"
)

CURRIC_NS = "https://w3id.org/uk/oak/curriculum/ontology/"
SKOS_NS = "http://www.w3.org/2004/02/skos/core#"

# XSD datatype -> SQL type (dialect-neutral base; boolean overridden per dialect)
_XSD_SQL_BASE: dict[str, str] = {
    "nonNegativeInteger": "INTEGER",
    "positiveInteger": "INTEGER",
    "integer": "INTEGER",
    "int": "INTEGER",
    "string": "TEXT",
    "langString": "TEXT",
    "anyURI": "TEXT",
    "boolean": "BOOLEAN",
    "bool": "BOOLEAN",
    "dateTime": "TIMESTAMP",
    "date": "DATE",
    "float": "REAL",
    "double": "DOUBLE PRECISION",
    "decimal": "NUMERIC",
}

# SKOS knowledge taxonomy: child table -> parent table (via skos:broader)
SKOS_BROADER_MAP: dict[str, str] = {
    "strand": "discipline",
    "sub_strand": "strand",
    "content_descriptor": "sub_strand",
}

# "has" properties where FK belongs on the child (range) table (domain is parent)
INVERSE_FK_PROPS: set[str] = {
    "hasUnitVariantInclusion",   # Programme -> UnitVariantInclusion
    "hasLessonInclusion",        # UnitVariant -> LessonInclusion
    "hasKeyLearningPoint",       # Lesson -> KeyLearningPoint
    "hasPupilLessonOutcome",     # Lesson -> PupilLessonOutcome
}

# Many-to-many properties: junction tables
M2M_PROPS: set[str] = {
    "coversStrand",           # Subject -> Strand
    "coversContent",          # Progression -> ContentDescriptor
    "includesThread",         # Unit -> Thread
    "includesContent",        # Unit -> ContentDescriptor
    "hasUnitVariantOption",   # UnitVariantChoice -> UnitVariant
    "hasKeyword",             # Lesson -> Keyword
    "hasMisconception",       # Lesson -> Misconception
}

# Junction table name overrides: (src, tgt) -> table_name
JUNCTION_TABLE_NAMES: dict[tuple[str, str], str] = {
    ("unit_variant_choice", "unit_variant"): "unit_variant_choice_option",
    ("progression", "content_descriptor"): "progression_content_descriptor",
    ("unit", "content_descriptor"): "unit_content_descriptor",
    ("unit", "thread"): "unit_thread",
    ("lesson", "keyword"): "lesson_keyword",
    ("lesson", "misconception"): "lesson_misconception",
    ("subject", "strand"): "subject_strand",
}

# Properties where FK belongs on the domain table
DIRECT_FK_PROPS: set[str] = {
    "isKeyStageOf",               # KeyStage -> Phase (required)
    "isYearGroupOf",              # YearGroup -> KeyStage (required)
    "coversKeyStage",             # Scheme -> KeyStage (required)
    "coversDiscipline",           # SubjectGroup -> Discipline (required)
    "isSubjectOf",                # Subject -> SubjectGroup (required)
    "isSchemeOf",                 # Scheme -> Subject (required)
    "isProgressionOf",            # Progression -> Scheme (required)
    "isProgrammeOf",              # Programme -> Scheme (required)
    "coversYearGroup",            # Programme -> YearGroup (required per SHACL)
    "hasExamBoard",               # Programme -> ExamBoard (nullable)
    "hasTier",                    # Programme -> Tier (nullable)
    "isUnitOf",                   # Unit -> Scheme (required)
    "isUnitVariantOf",            # UnitVariant -> Unit (required)
    "includesUnitVariant",        # UnitVariantInclusion -> UnitVariant (nullable)
    "includesLesson",             # LessonInclusion -> Lesson (required)
    "includesUnitVariantChoice",  # UnitVariantInclusion -> UnitVariantChoice (nullable)
}

# FK columns that are optional (nullable) — keyed by (table, column)
NULLABLE_FK_COLS: set[tuple[str, str]] = {
    ("programme", "exam_board_id"),
    ("programme", "tier_id"),
    ("unit_variant_inclusion", "unit_variant_id"),
    ("unit_variant_inclusion", "unit_variant_choice_id"),
}

# Data properties that are required (NOT NULL) per SHACL sh:minCount 1
NOT_NULL_DATA_PROPS: set[str] = {
    "display_order",
    "sequence_position",
    "why_this_why_now",
    "unit_prior_knowledge_requirements",
    "statement",
    "correction",
    "is_national_curriculum",
    "is_required",
    "is_examined",
}

# Column name overrides: OWL local name -> SQL column name
COL_RENAMES: dict[str, str] = {
    "id": "oak_id",  # curric:id (Oak natural key) conflicts with SQL surrogate PK
}

# Per-table NOT NULL overrides not covered by NOT_NULL_DATA_PROPS
NOT_NULL_SPECIFIC_COLS: set[tuple[str, str]] = {
    ("lesson", "oak_id"),  # curric:id is required for Lesson (SHACL minCount 1)
}

# Domain override: props where OWL rdfs:domain auto-detection fails.
# Maps prop local-name -> list of tables that should receive the column.
DOMAIN_OVERRIDE: dict[str, list[str]] = {
    "displayOrder": ["strand", "sub_strand", "content_descriptor"],
    "id": ["unit", "unit_variant", "lesson"],
    "sequencePosition": ["unit_variant_inclusion", "lesson_inclusion"],
}

# Tables that include a description column
DESCRIPTION_TABLES: set[str] = {
    "phase",          # NOT NULL
    "exam_board",     # nullable
    "tier",           # nullable
    "thread",         # nullable
    "keyword",        # nullable
    "key_stage",      # NOT NULL
    "year_group",     # NOT NULL
    "scheme",         # nullable
    "strand",         # NOT NULL per SHACL
    "sub_strand",     # nullable
    "unit",           # nullable
}

# Subset of DESCRIPTION_TABLES where description is NOT NULL
NOT_NULL_DESCRIPTION_TABLES: set[str] = {"strand", "phase", "key_stage", "year_group"}

# Classes to exclude from SQL output (abstract superclasses, not data tables)
SKIP_CLASSES: set[str] = {
    "Inclusion",  # abstract superclass of UnitVariantInclusion and LessonInclusion
}

# Inverse/redundant object properties to skip entirely (we use one direction only)
SKIP_PROPS: set[str] = {
    "hasKeyStage",
    "hasYearGroup",
    "isCoveredByScheme",
    "isCoveredBySubjectGroup",
    "hasSubject",
    "hasScheme",
    "hasProgression",
    "hasProgramme",
    "isCoveredByProgramme",
    "isExamBoardOf",
    "isTierOf",
    "hasUnit",
    "hasUnitVariant",
    "isCoveredBySubject",
    "isIncludedByProgression",
    "isThreadOf",
    "isContentOf",
    "isKeywordOf",
    "isMisconceptionOf",
    "isKeyLearningPointOf",
    "isPupilLessonOutcomeOf",
    "aims",  # rdf:List -> subject_aim table (handled separately)
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Column:
    """A single DDL column definition."""

    name: str
    definition: str  # Everything after the column name: type, constraints

    def render(self) -> str:
        return f"{self.name} {self.definition}"


@dataclass
class JunctionTable:
    """A many-to-many junction table."""

    name: str
    col_a: str
    ref_a: str
    col_b: str
    ref_b: str


# Constants that reference Column must come after the class definition.

_TEXT_NOT_NULL = "TEXT NOT NULL"

# Tables where the standard "name TEXT NOT NULL" column is not appropriate.
NO_STANDARD_NAME_TABLES: dict[str, list[Column]] = {
    "misconception": [
        Column("statement", _TEXT_NOT_NULL),
        Column("correction", _TEXT_NOT_NULL),
    ],
    "unit_variant_inclusion": [],  # no name column; only data/FK columns
    "lesson_inclusion": [],        # no name column; only data/FK columns
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def camel_to_snake(name: str) -> str:
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s).lower()


def local_name(iri: str) -> str:
    return iri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def is_curric(entity) -> bool:
    return hasattr(entity, "iri") and entity.iri.startswith(CURRIC_NS)


def domain_classes(prop) -> list:
    """Get domain classes, resolving owl:unionOf."""
    result = []
    for d in prop.domain:
        if isinstance(d, Or):
            result.extend(c for c in d.Classes if is_curric(c))
        elif isinstance(d, type) and issubclass(d, Thing) and is_curric(d):
            result.append(d)
    return result


def range_classes(prop) -> list:
    return [
        r for r in prop.range
        if isinstance(r, type) and issubclass(r, Thing) and is_curric(r)
    ]


def _build_xsd_map(dialect: str) -> dict[str, str]:
    """Return a dialect-specific copy of the XSD->SQL type map.

    A copy is returned rather than mutating the module-level constant, so
    calling generate_ddl for different dialects in the same process is safe.
    """
    m = dict(_XSD_SQL_BASE)
    if dialect == "sqlite":
        m["boolean"] = "INTEGER"
        m["bool"] = "INTEGER"
    return m


def _sql_type_for(range_items, xsd_map: dict[str, str]) -> str:
    for r in range_items:
        if hasattr(r, "iri"):
            return xsd_map.get(local_name(r.iri), "TEXT")
        name = getattr(r, "__name__", str(r))
        if name in xsd_map:
            return xsd_map[name]
    return "TEXT"


# ---------------------------------------------------------------------------
# Ontology loading (Turtle -> NTriples -> OWLready2)
# ---------------------------------------------------------------------------

def load_ontology(ttl_path: Path):
    """Parse Turtle via rdflib and load into OWLready2 via a temp NTriples file.

    OWLready2 supports RDF/XML and NTriples but not Turtle directly.
    owl:imports triples are stripped so OWLready2 does not fetch external URLs.
    """
    g = rdflib.Graph()
    g.parse(str(ttl_path), format="turtle")

    owl_imports = rdflib.URIRef("http://www.w3.org/2002/07/owl#imports")
    g.remove((None, owl_imports, None))

    with tempfile.NamedTemporaryFile(suffix=".nt", delete=False) as tmp:
        nt_path = Path(tmp.name)
    try:
        g.serialize(destination=str(nt_path), format="nt", encoding="utf-8")
        onto = get_ontology(f"file://{nt_path}").load()
    finally:
        nt_path.unlink(missing_ok=True)

    return onto


# ---------------------------------------------------------------------------
# DDL generation — private helpers
# ---------------------------------------------------------------------------

def _init_table_columns(classes, pk: str) -> dict[str, list[Column]]:
    """Build the initial column list for each curriculum class table."""
    table_columns: dict[str, list[Column]] = {}
    for cls in classes:
        table = camel_to_snake(local_name(cls.iri))
        cols: list[Column] = [
            Column("id", pk),
            Column("uri", "TEXT NOT NULL UNIQUE"),
        ]
        if table in NO_STANDARD_NAME_TABLES:
            cols.extend(NO_STANDARD_NAME_TABLES[table])
        else:
            cols.append(Column("name", _TEXT_NOT_NULL))
        if table in DESCRIPTION_TABLES:
            not_null = " NOT NULL" if table in NOT_NULL_DESCRIPTION_TABLES else ""
            cols.append(Column("description", f"TEXT{not_null}"))
        table_columns[table] = cols
    return table_columns


def _not_null_suffix(col_name: str, table: str) -> str:
    """Return ' NOT NULL' if the column is required by SHACL, else ''."""
    if col_name in NOT_NULL_DATA_PROPS or (table, col_name) in NOT_NULL_SPECIFIC_COLS:
        return " NOT NULL"
    return ""


def _get_target_tables(prop, prop_name: str) -> list[str]:
    """Collect domain tables for a data property, including subclass tables."""
    dom = domain_classes(prop)
    tables = [camel_to_snake(local_name(cls.iri)) for cls in dom]
    for cls in dom:
        for sub in cls.subclasses():
            sub_table = camel_to_snake(local_name(sub.iri))
            if sub_table not in tables:
                tables.append(sub_table)
    if not tables and prop_name in DOMAIN_OVERRIDE:
        return DOMAIN_OVERRIDE[prop_name]
    return tables


def _add_data_property_columns(
    onto,
    table_columns: dict[str, list[Column]],
    xsd_map: dict[str, str],
) -> None:
    """Append data-property columns to the appropriate tables."""
    for prop in onto.data_properties():
        if not is_curric(prop):
            continue
        prop_name = local_name(prop.iri)
        if prop_name in SKIP_PROPS:
            continue

        col_name = COL_RENAMES.get(camel_to_snake(prop_name), camel_to_snake(prop_name))
        sql_t = _sql_type_for(prop.range, xsd_map)

        for table in _get_target_tables(prop, prop_name):
            if table not in table_columns:
                continue
            existing = {c.name for c in table_columns[table]}
            if col_name in existing:
                continue
            not_null = _not_null_suffix(col_name, table)
            table_columns[table].append(Column(col_name, f"{sql_t}{not_null}"))


def _handle_inverse_fk(
    dom: list,
    rng: list,
    table_columns: dict[str, list[Column]],
) -> None:
    """Add FK on the child (range) table for inverse-direction properties."""
    for rng_cls in rng:
        child_table = camel_to_snake(local_name(rng_cls.iri))
        if child_table not in table_columns:
            continue
        for dom_cls in dom:
            parent_table = camel_to_snake(local_name(dom_cls.iri))
            fk_col = f"{parent_table}_id"
            if fk_col not in {c.name for c in table_columns[child_table]}:
                table_columns[child_table].append(Column(
                    fk_col,
                    f"INTEGER NOT NULL REFERENCES {parent_table}(id) ON DELETE RESTRICT",
                ))


def _handle_m2m(
    dom: list,
    rng: list,
    junction_tables: list[JunctionTable],
) -> None:
    """Collect junction table definitions for many-to-many properties."""
    for dom_cls in dom:
        src = camel_to_snake(local_name(dom_cls.iri))
        for rng_cls in rng:
            tgt = camel_to_snake(local_name(rng_cls.iri))
            jt_name = JUNCTION_TABLE_NAMES.get((src, tgt), f"{src}_{tgt}")
            junction_tables.append(JunctionTable(
                name=jt_name,
                col_a=f"{src}_id",
                ref_a=src,
                col_b=f"{tgt}_id",
                ref_b=tgt,
            ))


def _handle_direct_fk(
    dom: list,
    rng: list,
    table_columns: dict[str, list[Column]],
) -> None:
    """Add FK on the domain table for direct-direction properties."""
    for dom_cls in dom:
        table = camel_to_snake(local_name(dom_cls.iri))
        if table not in table_columns:
            continue
        for rng_cls in rng:
            ref_table = camel_to_snake(local_name(rng_cls.iri))
            fk_col = f"{ref_table}_id"
            if fk_col not in {c.name for c in table_columns[table]}:
                nullable = (table, fk_col) in NULLABLE_FK_COLS
                not_null = "" if nullable else "NOT NULL "
                table_columns[table].append(Column(
                    fk_col,
                    f"INTEGER {not_null}REFERENCES {ref_table}(id) ON DELETE RESTRICT",
                ))


def _add_object_property_relations(
    onto,
    table_columns: dict[str, list[Column]],
) -> list[JunctionTable]:
    """Add FK columns and collect junction tables from object properties."""
    junction_tables: list[JunctionTable] = []

    for prop in onto.object_properties():
        if not is_curric(prop):
            continue
        prop_name = local_name(prop.iri)
        if prop_name in SKIP_PROPS:
            continue

        dom = domain_classes(prop)
        rng = range_classes(prop)
        if not dom or not rng:
            continue

        if prop_name in INVERSE_FK_PROPS:
            _handle_inverse_fk(dom, rng, table_columns)
        elif prop_name in M2M_PROPS:
            _handle_m2m(dom, rng, junction_tables)
        elif prop_name in DIRECT_FK_PROPS:
            _handle_direct_fk(dom, rng, table_columns)

    return junction_tables


def _add_skos_fk_columns(table_columns: dict[str, list[Column]]) -> None:
    """Add SKOS broader-hierarchy FK columns (all required)."""
    for child_table, parent_table in SKOS_BROADER_MAP.items():
        if child_table not in table_columns:
            continue
        fk_col = f"{parent_table}_id"
        existing = {c.name for c in table_columns[child_table]}
        if fk_col not in existing:
            table_columns[child_table].append(Column(
                fk_col,
                f"INTEGER NOT NULL REFERENCES {parent_table}(id) ON DELETE RESTRICT",
            ))


def _render_ddl(
    table_columns: dict[str, list[Column]],
    junction_tables: list[JunctionTable],
    pk: str,
    dialect: str,
) -> str:
    """Render the full DDL string from collected tables and junction tables."""
    lines = [
        "-- SQL schema generated from Oak Curriculum Ontology",
        f"-- Dialect: {dialect}",
        "",
    ]

    for table, cols in table_columns.items():
        formatted = ",\n  ".join(c.render() for c in cols)
        lines.append(f"CREATE TABLE {table} (\n  {formatted}\n);\n")

    for jt in junction_tables:
        lines.append(
            f"CREATE TABLE {jt.name} (\n"
            f"  {jt.col_a} INTEGER NOT NULL REFERENCES {jt.ref_a}(id) ON DELETE RESTRICT,\n"
            f"  {jt.col_b} INTEGER NOT NULL REFERENCES {jt.ref_b}(id) ON DELETE RESTRICT,\n"
            f"  PRIMARY KEY ({jt.col_a}, {jt.col_b})\n"
            f");\n"
        )

    # subject_aim: rdf:List in OWL -> normalised table
    lines.append(
        f"CREATE TABLE subject_aim (\n"
        f"  id {pk},\n"
        f"  subject_id INTEGER NOT NULL REFERENCES subject(id) ON DELETE RESTRICT,\n"
        f"  ordinal INTEGER NOT NULL,\n"
        f"  aim_text TEXT NOT NULL,\n"
        f"  UNIQUE (subject_id, ordinal)\n"
        f");\n"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_ddl(ontology_path: str | Path, dialect: str = "postgres") -> str:
    """Generate complete DDL for the given dialect from an ontology TTL file."""
    onto = load_ontology(Path(ontology_path))
    pk = "SERIAL PRIMARY KEY" if dialect == "postgres" else "INTEGER PRIMARY KEY AUTOINCREMENT"
    xsd_map = _build_xsd_map(dialect)

    classes = sorted(
        [c for c in onto.classes() if is_curric(c) and local_name(c.iri) not in SKIP_CLASSES],
        key=lambda c: c.iri,
    )

    table_columns = _init_table_columns(classes, pk)
    _add_data_property_columns(onto, table_columns, xsd_map)
    junction_tables = _add_object_property_relations(onto, table_columns)
    _add_skos_fk_columns(table_columns)

    return _render_ddl(table_columns, junction_tables, pk, dialect)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Generate SQL DDL from the Oak Curriculum Ontology"
    )
    parser.add_argument(
        "--ontology", type=Path, default=DEFAULT_ONTOLOGY,
        help="Path to ontology TTL file",
    )
    parser.add_argument(
        "--dialect", choices=["postgres", "sqlite"], default="postgres",
        help="SQL dialect (default: postgres)",
    )
    parser.add_argument(
        "-o", "--output", type=Path,
        help="Output file (default: stdout)",
    )
    args = parser.parse_args()

    ddl = generate_ddl(args.ontology, args.dialect)

    if args.output:
        args.output.write_text(ddl, encoding="utf-8")
        log.info("Schema written to %s", args.output)
    else:
        print(ddl)


if __name__ == "__main__":
    main()
