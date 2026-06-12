#!/usr/bin/env python3
"""
Check that README examples and stated counts match the published data.

Usage:
    uv run python scripts/check_readme_examples.py

This script guards against documentation drift by checking, in CI and locally:
1. Every ```turtle code block in README.md parses, uses only properties
   defined in the ontology, and references only entities present in the data.
2. Every ```sparql code block in README.md executes against the merged
   graph and returns at least one result.
3. Counts stated in README.md (classes, properties, shapes, subjects)
   match counts computed from the ontology and data files.
4. Instance counts stated in README.md (lessons, misconceptions, threads,
   etc.) match counts computed from the merged data graph.

Exits non-zero if any check fails.
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from rdflib import Graph, RDF, OWL, URIRef
from rdflib.term import Node

REPO_ROOT = Path(__file__).parent.parent
README = REPO_ROOT / "README.md"
ONTOLOGY_FILE = REPO_ROOT / "ontology" / "oak-curriculum-ontology.ttl"
CONSTRAINTS_FILE = REPO_ROOT / "ontology" / "oak-curriculum-constraints.ttl"
SUBJECTS_DIR = REPO_ROOT / "data" / "subjects"

CURRIC_NS = "https://w3id.org/uk/oak/curriculum/ontology/"
DATA_NAMESPACES = (
    "https://w3id.org/uk/oak/curriculum/nationalcurriculum/",
    "https://w3id.org/uk/oak/curriculum/oakcurriculum/",
)

# SHACL's namespace IRI is http:// by specification — an exact identifier,
# not a web link. "Upgrading" it to https breaks matching against the graph.
SH_NODE_SHAPE = URIRef("http://www.w3.org/ns/shacl#NodeShape")


def merge_data() -> Path:
    """Run the merge script to create the combined data graph.

    Writes to a unique temp file per invocation so concurrent runs
    cannot overwrite each other's output. The caller removes the file.
    """
    fd, name = tempfile.mkstemp(prefix="combined-data-", suffix=".ttl")
    os.close(fd)
    output = Path(name)
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "merge_ttls_with_imports.py"),
            "-q",
            "-o",
            str(output),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        output.unlink(missing_ok=True)
        print(f"Error merging TTL files: {result.stderr}")
        sys.exit(1)
    return output


def extract_code_blocks(markdown: str, language: str) -> list[tuple[int, str]]:
    """Return (start line number, block content) for each fenced block of a language."""
    blocks = []
    lines = markdown.splitlines()
    in_block = False
    start = 0
    current: list[str] = []
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not in_block and stripped == f"```{language}":
            in_block = True
            start = i
            current = []
        elif in_block and stripped == "```":
            in_block = False
            blocks.append((start, "\n".join(current)))
        elif in_block:
            current.append(line)
    return blocks


def _triple_errors(
    line_no: int, g: Graph, defined_terms: set[Node], data_nodes: set[Node]
) -> list[str]:
    """Errors for one parsed turtle block: unknown properties, missing entities."""
    errors = []
    for s, p, o in g:
        if str(p).startswith(CURRIC_NS) and p not in defined_terms:
            errors.append(
                f"README.md:{line_no} uses property {p} "
                "which is not defined in the ontology"
            )
        for node in (s, o):
            if (
                isinstance(node, URIRef)
                and str(node).startswith(DATA_NAMESPACES)
                and node not in data_nodes
            ):
                errors.append(
                    f"README.md:{line_no} references {node} "
                    "which does not exist in the data"
                )
    return errors


def check_turtle_blocks(markdown: str, ontology: Graph, data: Graph) -> list[str]:
    """Validate turtle examples: syntax, known properties, existing entities."""
    errors = []
    defined_terms = set(ontology.subjects())
    data_nodes = set(data.subjects()) | set(data.objects())

    for line_no, block in extract_code_blocks(markdown, "turtle"):
        g = Graph()
        try:
            g.parse(data=block, format="turtle")
        except Exception as e:
            errors.append(f"README.md:{line_no} turtle block does not parse: {e}")
            continue
        errors.extend(_triple_errors(line_no, g, defined_terms, data_nodes))
    return errors


def check_sparql_blocks(markdown: str, combined: Graph) -> list[str]:
    """Run SPARQL examples against the merged graph; require at least one result."""
    errors = []
    for line_no, block in extract_code_blocks(markdown, "sparql"):
        try:
            results = list(combined.query(block))
        except Exception as e:
            errors.append(f"README.md:{line_no} SPARQL block failed to execute: {e}")
            continue
        if not results:
            errors.append(
                f"README.md:{line_no} SPARQL block returned no results "
                "against the merged graph"
            )
    return errors


def check_counts(markdown: str, ontology: Graph, constraints: Graph) -> list[str]:
    """Compare counts stated in the README against counts computed from the data."""
    actual = {
        "classes": len(set(ontology.subjects(RDF.type, OWL.Class))),
        "properties": len(
            set(ontology.subjects(RDF.type, OWL.ObjectProperty))
            | set(ontology.subjects(RDF.type, OWL.DatatypeProperty))
        ),
        "shapes": len(set(constraints.subjects(RDF.type, SH_NODE_SHAPE))),
        "subjects": len([p for p in SUBJECTS_DIR.iterdir() if p.is_dir()]),
    }

    claim_patterns = {
        "classes": r"\b(\d+)\+?\s+(?:ontology\s+)?classes\b",
        "properties": r"\b(\d+)\+?\s+properties\b",
        "shapes": r"\b(\d+)\+?\s+(?:SHACL\s+)?(?:validation\s+)?shapes\b",
        "subjects": r"\b(\d+)\s+subject(?:s\b|\s+areas\b)",
    }

    errors = []
    lines = markdown.splitlines()
    for kind, pattern in claim_patterns.items():
        for line_no, line in enumerate(lines, start=1):
            for match in re.finditer(pattern, line, flags=re.IGNORECASE):
                claimed = int(match.group(1))
                if claimed != actual[kind]:
                    errors.append(
                        f"README.md:{line_no} claims {claimed} {kind}, "
                        f"but the actual count is {actual[kind]}"
                    )
    return errors


# README phrases that claim an instance count, mapped to the ontology class
# counted in the merged data graph. Claims match both prose ("11,207
# misconceptions") and table rows ("| Misconceptions | 11,207 |").
INSTANCE_CLAIMS = {
    "programmes": "Programme",
    "units": "Unit",
    "unit variants": "UnitVariant",
    "lessons": "Lesson",
    "threads": "Thread",
    "misconceptions": "Misconception",
    "prior knowledge requirements": "PriorKnowledgeRequirement",
    "key learning points": "KeyLearningPoint",
    "pupil lesson outcomes": "PupilLessonOutcome",
    "keywords": "Keyword",
    "lesson sequencing": "LessonInclusion",
}


def check_instance_counts(markdown: str, data: Graph) -> list[str]:
    """Compare instance counts stated in the README against the merged data."""
    errors = []
    lines = markdown.splitlines()
    for phrase, class_name in INSTANCE_CLAIMS.items():
        actual = len(set(data.subjects(RDF.type, URIRef(CURRIC_NS + class_name))))
        # Lookbehinds skip ordinals like "Year 7 programmes" / "Key Stage 4 units"
        prose = rf"(?<!year\s)(?<!stage\s)\b(\d[\d,]*)\s+{re.escape(phrase)}\b"
        table_row = rf"\|\s*{re.escape(phrase)}\b[^|]*\|\s*(\d[\d,]*)\s*\|"
        for line_no, line in enumerate(lines, start=1):
            for pattern in (prose, table_row):
                for match in re.finditer(pattern, line, flags=re.IGNORECASE):
                    claimed = int(match.group(1).replace(",", ""))
                    if claimed != actual:
                        errors.append(
                            f"README.md:{line_no} claims {match.group(1)} {phrase}, "
                            f"but the data contains {actual:,}"
                        )
    return errors


def main() -> int:
    markdown = README.read_text(encoding="utf-8")

    combined_path = merge_data()
    ontology = Graph()
    ontology.parse(ONTOLOGY_FILE, format="turtle")
    constraints = Graph()
    constraints.parse(CONSTRAINTS_FILE, format="turtle")
    combined = Graph()
    try:
        combined.parse(combined_path, format="turtle")
    finally:
        combined_path.unlink(missing_ok=True)
    # SPARQL examples should work against ontology + data together
    combined += ontology

    errors = (
        check_turtle_blocks(markdown, ontology, combined)
        + check_sparql_blocks(markdown, combined)
        + check_counts(markdown, ontology, constraints)
        + check_instance_counts(markdown, combined)
    )

    turtle_count = len(extract_code_blocks(markdown, "turtle"))
    sparql_count = len(extract_code_blocks(markdown, "sparql"))
    print(f"Checked {turtle_count} turtle blocks and {sparql_count} SPARQL blocks")

    if errors:
        print(f"\n{len(errors)} README check(s) failed:")
        for error in errors:
            print(f"  FAIL: {error}")
        return 1

    print("All README examples and counts match the data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
