#!/usr/bin/env python3
"""
Generate SQL relational schema (DDL) from the Oak Curriculum Ontology.

Introspects the ontology TTL file to derive tables, columns, foreign keys, and
junction tables for both PostgreSQL and SQLite dialects. Re-run this script
whenever the ontology changes to keep the schema files up to date.

Uses OWLready2 for ontology introspection and rdflib to handle Turtle parsing
(OWLready2 only supports RDF/XML and NTriples natively).

Usage:
    python scripts/generate_sql_schema.py --dialect postgres -o distributions/oak-curriculum-schema-postgres.sql
    python scripts/generate_sql_schema.py --dialect sqlite -o distributions/oak-curriculum-schema-sqlite.sql
"""

import argparse
import os
import re
import sys
import tempfile

try:
    from owlready2 import get_ontology, Thing, Or
except ImportError:
    sys.exit("owlready2 is required: pip install owlready2")

try:
    import rdflib
except ImportError:
    sys.exit("rdflib is required: pip install rdflib")


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ONTOLOGY = os.path.join(
    SCRIPT_DIR, "..", "ontology", "oak-curriculum-ontology.ttl"
)

CURRIC_NS = "https://w3id.org/uk/oak/curriculum/ontology/"
SKOS_NS = "http://www.w3.org/2004/02/skos/core#"

# XSD datatype to SQL type mapping (dialect-neutral; boolean overridden per dialect below)
XSD_SQL_MAP = {
    "nonNegativeInteger": "INTEGER",
    "positiveInteger": "INTEGER",
    "integer": "INTEGER",
    "int": "INTEGER",
    "string": "TEXT",
    "langString": "TEXT",
    "anyURI": "TEXT",
    "boolean": "BOOLEAN",   # overridden to INTEGER for sqlite in generate_ddl
    "bool": "BOOLEAN",      # OWLready2 maps xsd:boolean to Python bool; overridden for sqlite
    "dateTime": "TIMESTAMP",
    "date": "DATE",
    "float": "REAL",
    "double": "DOUBLE PRECISION",
    "decimal": "NUMERIC",
}

# SKOS knowledge taxonomy: child table -> parent table (via skos:broader)
SKOS_BROADER_MAP = {
    "strand": "discipline",
    "sub_strand": "strand",
    "content_descriptor": "sub_strand",
}

# "has" properties where FK belongs on the child (range) table (domain is parent)
INVERSE_FK_PROPS = {
    "hasUnitVariantInclusion",   # Programme -> UnitVariantInclusion
    "hasLessonInclusion",        # UnitVariant -> LessonInclusion
    "hasKeyLearningPoint",       # Lesson -> KeyLearningPoint
    "hasPupilLessonOutcome",     # Lesson -> PupilLessonOutcome
}

# Many-to-many properties: junction tables
M2M_PROPS = {
    "coversStrand",           # Subject -> Strand
    "coversContent",          # Progression -> ContentDescriptor
    "includesThread",         # Unit -> Thread
    "includesContent",        # Unit -> ContentDescriptor
    "hasUnitVariantOption",   # UnitVariantChoice -> UnitVariant
    "hasKeyword",             # Lesson -> Keyword
    "hasMisconception",       # Lesson -> Misconception
}

# Junction table name overrides: (src, tgt) -> table_name
# Used when the auto-generated name {src}_{tgt} doesn't match convention.
JUNCTION_TABLE_NAMES = {
    ("unit_variant_choice", "unit_variant"): "unit_variant_choice_option",
    ("progression", "content_descriptor"): "progression_content_descriptor",
    ("unit", "content_descriptor"): "unit_content_descriptor",
    ("unit", "thread"): "unit_thread",
    ("lesson", "keyword"): "lesson_keyword",
    ("lesson", "misconception"): "lesson_misconception",
    ("subject", "strand"): "subject_strand",
}

# Properties where FK belongs on the domain table
DIRECT_FK_PROPS = {
    "isKeyStageOf",           # KeyStage -> Phase (required)
    "isYearGroupOf",          # YearGroup -> KeyStage (required)
    "coversKeyStage",         # Scheme -> KeyStage (required)
    "coversDiscipline",       # SubjectGroup -> Discipline (required)
    "isSubjectOf",            # Subject -> SubjectGroup (required)
    "isSchemeOf",             # Scheme -> Subject (required)
    "isProgressionOf",        # Progression -> Scheme (required)
    "isProgrammeOf",          # Programme -> Scheme (required)
    "coversYearGroup",        # Programme -> YearGroup (required per SHACL)
    "hasExamBoard",           # Programme -> ExamBoard (nullable)
    "hasTier",                # Programme -> Tier (nullable)
    "isUnitOf",               # Unit -> Scheme (required)
    "isUnitVariantOf",        # UnitVariant -> Unit (required)
    "includesUnitVariant",    # UnitVariantInclusion -> UnitVariant (nullable: either this or choice)
    "includesLesson",         # LessonInclusion -> Lesson (required)
    "includesUnitVariantChoice",  # UnitVariantInclusion -> UnitVariantChoice (nullable)
}

# FK columns that are optional (nullable) — keyed by (table, column)
NULLABLE_FK_COLS = {
    ("programme", "exam_board_id"),
    ("programme", "tier_id"),
    ("unit_variant_inclusion", "unit_variant_id"),
    ("unit_variant_inclusion", "unit_variant_choice_id"),
}

# Data properties that are required (NOT NULL) per SHACL sh:minCount 1
NOT_NULL_DATA_PROPS = {
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
# Needed when the auto-derived name would clash or is misleading.
COL_RENAMES = {
    "id": "oak_id",  # curric:id (Oak natural key) conflicts with SQL surrogate PK
}

# Per-table NOT NULL overrides for columns not covered by NOT_NULL_DATA_PROPS
NOT_NULL_SPECIFIC_COLS: set[tuple[str, str]] = {
    ("lesson", "oak_id"),  # curric:id is required for Lesson (SHACL minCount 1)
}

# Domain override: props where OWL rdfs:domain is not a curric class (e.g. skos:Concept,
# owl:Thing, or a skipped abstract class), so auto-detection fails.
# Maps prop local-name -> list of tables that should receive the column.
DOMAIN_OVERRIDE: dict[str, list[str]] = {
    "displayOrder": ["strand", "sub_strand", "content_descriptor"],
    "id": ["unit", "unit_variant", "lesson"],   # curric:id -> oak_id via COL_RENAMES
    "sequencePosition": ["unit_variant_inclusion", "lesson_inclusion"],
}

# Tables that include a description column (maps to rdfs:comment or skos:definition)
DESCRIPTION_TABLES = {
    "phase",             # NOT NULL (aligned to national curriculum schema)
    "exam_board",        # nullable
    "tier",              # nullable
    "thread",            # nullable
    "keyword",           # schema:description (nullable)
    "key_stage",         # NOT NULL (aligned to national curriculum schema)
    "year_group",        # NOT NULL (aligned to national curriculum schema)
    "scheme",            # nullable
    "strand",            # skos:definition (NOT NULL per SHACL)
    "sub_strand",        # nullable (aligned to national curriculum schema)
    "unit",              # nullable
}

# Subset of DESCRIPTION_TABLES where description is required (NOT NULL) per SHACL
NOT_NULL_DESCRIPTION_TABLES = {"strand", "phase", "key_stage", "year_group"}

# Tables where the standard "name TEXT NOT NULL" column is not appropriate.
# Provide replacement initial column definitions (after id and uri).
NO_STANDARD_NAME_TABLES = {
    "misconception": [
        "statement TEXT NOT NULL",
        "correction TEXT NOT NULL",
    ],
    "unit_variant_inclusion": [],   # no name column; only data/FK columns
    "lesson_inclusion": [],         # no name column; only data/FK columns
}

# Classes to exclude from SQL output (abstract superclasses, not data tables)
SKIP_CLASSES = {
    "Inclusion",  # abstract superclass of UnitVariantInclusion and LessonInclusion
}

# Inverse/redundant object properties to skip entirely (we use one direction only)
SKIP_PROPS = {
    # Inverses of DIRECT_FK_PROPS
    "hasKeyStage",            # inverse of isKeyStageOf
    "hasYearGroup",           # inverse of isYearGroupOf
    "isCoveredByScheme",      # inverse of coversKeyStage
    "isCoveredBySubjectGroup",  # inverse of coversDiscipline
    "hasSubject",             # inverse of isSubjectOf
    "hasScheme",              # inverse of isSchemeOf
    "hasProgression",         # inverse of isProgressionOf
    "hasProgramme",           # inverse of isProgrammeOf
    "isCoveredByProgramme",   # inverse of coversYearGroup
    "isExamBoardOf",          # inverse of hasExamBoard
    "isTierOf",               # inverse of hasTier
    "hasUnit",                # inverse of isUnitOf
    "hasUnitVariant",         # inverse of isUnitVariantOf
    # Inverses of M2M_PROPS
    "isCoveredBySubject",     # inverse of coversStrand
    "isIncludedByProgression",  # inverse of coversContent
    "isThreadOf",             # inverse of includesThread
    "isContentOf",            # inverse of includesContent
    "isKeywordOf",            # inverse of hasKeyword
    "isMisconceptionOf",      # inverse of hasMisconception
    # Inverses of INVERSE_FK_PROPS
    "isKeyLearningPointOf",   # inverse of hasKeyLearningPoint
    "isPupilLessonOutcomeOf", # inverse of hasPupilLessonOutcome
    # Handled separately
    "aims",                   # rdf:List -> subject_aim table
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


def is_skos_concept(cls) -> bool:
    for anc in cls.ancestors():
        if hasattr(anc, "iri") and anc.iri == f"{SKOS_NS}Concept":
            return True
    return False


def domain_classes(prop):
    """Get domain classes, resolving owl:unionOf."""
    result = []
    for d in prop.domain:
        if isinstance(d, Or):
            result.extend(c for c in d.Classes if is_curric(c))
        elif isinstance(d, type) and issubclass(d, Thing) and is_curric(d):
            result.append(d)
    return result


def range_classes(prop):
    result = []
    for r in prop.range:
        if isinstance(r, type) and issubclass(r, Thing) and is_curric(r):
            result.append(r)
    return result


def sql_type_for(range_items) -> str:
    for r in range_items:
        if hasattr(r, "iri"):
            return XSD_SQL_MAP.get(local_name(r.iri), "TEXT")
        name = getattr(r, "__name__", str(r))
        if name in XSD_SQL_MAP:
            return XSD_SQL_MAP[name]
    return "TEXT"


def is_nullable_fk(table: str, col: str) -> bool:
    return (table, col) in NULLABLE_FK_COLS


# ---------------------------------------------------------------------------
# Load ontology (Turtle -> NTriples -> OWLready2)
# ---------------------------------------------------------------------------

def load_ontology(ttl_path: str):
    """
    OWLready2 supports RDF/XML and NTriples but not Turtle.
    We use rdflib to parse the Turtle file and serialise to NTriples,
    then load the NTriples into OWLready2.
    """
    g = rdflib.Graph()
    g.parse(ttl_path, format="turtle")

    # Strip owl:imports so OWLready2 doesn't try to fetch external ontologies
    owl_imports = rdflib.URIRef("http://www.w3.org/2002/07/owl#imports")
    for triple in list(g.triples((None, owl_imports, None))):
        g.remove(triple)

    fd, nt_path = tempfile.mkstemp(suffix=".nt")
    try:
        os.close(fd)
        g.serialize(destination=nt_path, format="nt", encoding="utf-8")
        onto = get_ontology(f"file://{nt_path}").load()
    finally:
        os.unlink(nt_path)

    return onto


# ---------------------------------------------------------------------------
# DDL generation
# ---------------------------------------------------------------------------

def generate_ddl(ontology_path: str, dialect: str = "postgres") -> str:
    onto = load_ontology(ontology_path)

    pk = (
        "SERIAL PRIMARY KEY"
        if dialect == "postgres"
        else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )

    # SQLite has no native BOOLEAN type; use INTEGER instead
    if dialect == "sqlite":
        XSD_SQL_MAP["boolean"] = "INTEGER"
        XSD_SQL_MAP["bool"] = "INTEGER"
    else:
        XSD_SQL_MAP["boolean"] = "BOOLEAN"
        XSD_SQL_MAP["bool"] = "BOOLEAN"

    # Collect curriculum classes, sorted for deterministic output
    classes = sorted(
        [c for c in onto.classes() if is_curric(c) and local_name(c.iri) not in SKIP_CLASSES],
        key=lambda c: c.iri,
    )

    # Initialise per-table column lists
    table_columns: dict[str, list[str]] = {}
    for cls in classes:
        table = camel_to_snake(local_name(cls.iri))
        cols = [f"id {pk}", "uri TEXT NOT NULL UNIQUE"]
        if table in NO_STANDARD_NAME_TABLES:
            cols.extend(NO_STANDARD_NAME_TABLES[table])
        else:
            cols.append("name TEXT NOT NULL")
        if table in DESCRIPTION_TABLES:
            not_null = " NOT NULL" if table in NOT_NULL_DESCRIPTION_TABLES else ""
            cols.append(f"description TEXT{not_null}")
        table_columns[table] = cols

    # --- Datatype properties -> columns ---
    for prop in onto.data_properties():
        if not is_curric(prop):
            continue
        prop_name = local_name(prop.iri)
        if prop_name in SKIP_PROPS:
            continue
        col = camel_to_snake(prop_name)
        col = COL_RENAMES.get(col, col)
        sql_t = sql_type_for(prop.range)

        target_tables = [
            camel_to_snake(local_name(cls.iri))
            for cls in domain_classes(prop)
        ]
        # Add subclasses of any abstract parent classes found
        for cls in domain_classes(prop):
            for sub in cls.subclasses():
                sub_table = camel_to_snake(local_name(sub.iri))
                if sub_table not in target_tables:
                    target_tables.append(sub_table)
        # Fall back to explicit domain override when OWL detection yields nothing
        if not target_tables and prop_name in DOMAIN_OVERRIDE:
            target_tables = DOMAIN_OVERRIDE[prop_name]

        for table in target_tables:
            if table not in table_columns:
                continue
            existing = {c.split()[0] for c in table_columns[table]}
            if col in existing:
                continue
            specific_not_null = (table, col) in NOT_NULL_SPECIFIC_COLS
            not_null = " NOT NULL" if (col in NOT_NULL_DATA_PROPS or specific_not_null) else ""
            table_columns[table].append(f"{col} {sql_t}{not_null}")

    # --- Object properties -> FKs and junction tables ---
    junction_tables: list[tuple[str, str, str, str, str]] = []

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
            # "has" properties: FK on the *child* (range) table
            for rng_cls in rng:
                child_table = camel_to_snake(local_name(rng_cls.iri))
                for dom_cls in dom:
                    parent_table = camel_to_snake(local_name(dom_cls.iri))
                    fk_col = f"{parent_table}_id"
                    if child_table in table_columns:
                        existing = {c.split()[0] for c in table_columns[child_table]}
                        if fk_col not in existing:
                            table_columns[child_table].append(
                                f"{fk_col} INTEGER NOT NULL REFERENCES {parent_table}(id) ON DELETE RESTRICT"
                            )

        elif prop_name in M2M_PROPS:
            # Many-to-many -> junction table
            for dom_cls in dom:
                src = camel_to_snake(local_name(dom_cls.iri))
                for rng_cls in rng:
                    tgt = camel_to_snake(local_name(rng_cls.iri))
                    jt_name = JUNCTION_TABLE_NAMES.get((src, tgt), f"{src}_{tgt}")
                    junction_tables.append(
                        (jt_name, f"{src}_id", src, f"{tgt}_id", tgt)
                    )

        elif prop_name in DIRECT_FK_PROPS:
            # FK belongs on the domain table
            for dom_cls in dom:
                table = camel_to_snake(local_name(dom_cls.iri))
                for rng_cls in rng:
                    ref_table = camel_to_snake(local_name(rng_cls.iri))
                    fk_col = f"{ref_table}_id"
                    if table in table_columns:
                        existing = {c.split()[0] for c in table_columns[table]}
                        if fk_col not in existing:
                            nullable = is_nullable_fk(table, fk_col)
                            not_null = "" if nullable else "NOT NULL "
                            table_columns[table].append(
                                f"{fk_col} INTEGER {not_null}REFERENCES {ref_table}(id) ON DELETE RESTRICT"
                            )

    # --- SKOS broader hierarchy FKs — all required ---
    for child_table, parent_table in SKOS_BROADER_MAP.items():
        if child_table in table_columns:
            fk_col = f"{parent_table}_id"
            existing = {c.split()[0] for c in table_columns[child_table]}
            if fk_col not in existing:
                table_columns[child_table].append(
                    f"{fk_col} INTEGER NOT NULL REFERENCES {parent_table}(id) ON DELETE RESTRICT"
                )

    # -----------------------------------------------------------------------
    # Emit DDL
    # -----------------------------------------------------------------------
    output = [
        "-- SQL schema generated from Oak Curriculum Ontology",
        f"-- Dialect: {dialect}",
        "",
    ]

    for table, cols in table_columns.items():
        formatted = ",\n  ".join(cols)
        output.append(f"CREATE TABLE {table} (\n  {formatted}\n);\n")

    for jt_name, col_a, ref_a, col_b, ref_b in junction_tables:
        output.append(
            f"CREATE TABLE {jt_name} (\n"
            f"  {col_a} INTEGER NOT NULL REFERENCES {ref_a}(id) ON DELETE RESTRICT,\n"
            f"  {col_b} INTEGER NOT NULL REFERENCES {ref_b}(id) ON DELETE RESTRICT,\n"
            f"  PRIMARY KEY ({col_a}, {col_b})\n"
            f");\n"
        )

    # Subject aims (rdf:List in OWL -> normalised table)
    output.append(
        f"CREATE TABLE subject_aim (\n"
        f"  id {pk},\n"
        f"  subject_id INTEGER NOT NULL REFERENCES subject(id) ON DELETE RESTRICT,\n"
        f"  ordinal INTEGER NOT NULL,\n"
        f"  aim_text TEXT NOT NULL,\n"
        f"  UNIQUE (subject_id, ordinal)\n"
        f");\n"
    )

    return "\n".join(output)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate SQL DDL from the Oak Curriculum Ontology"
    )
    parser.add_argument(
        "--ontology", default=DEFAULT_ONTOLOGY,
        help="Path to ontology TTL file",
    )
    parser.add_argument(
        "--dialect", choices=["postgres", "sqlite"], default="postgres",
        help="SQL dialect (default: postgres)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file (default: stdout)",
    )
    args = parser.parse_args()

    ddl = generate_ddl(args.ontology, args.dialect)

    if args.output:
        with open(args.output, "w") as f:
            f.write(ddl)
        print(f"Schema written to {args.output}", file=sys.stderr)
    else:
        print(ddl)


if __name__ == "__main__":
    main()
