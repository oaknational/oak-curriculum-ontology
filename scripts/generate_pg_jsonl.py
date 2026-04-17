#!/usr/bin/env python3
"""
generate_pg_jsonl.py — Property Graph JSONL distribution generator

Converts any OWL/RDF ontology+data graph (merged TTL) into two JSONL files
suitable for import into any property graph database.

  distributions/nodes.jsonl         — one JSON object per node
  distributions/relationships.jsonl — one JSON object per relationship

Ontology classes and data nodes are discovered dynamically from the graph —
no namespace constants need configuring. Any URIRef that has rdf:type
pointing to an owl:Class or rdfs:Class is treated as a data node. Any URI
that is referenced as a relationship endpoint but has no ontology type of
its own is included as an ExternalReference stub, preserving the edge
without requiring the full definition to be present.

See docs/property-graph-format.md for the full format specification.

Usage:
  python scripts/generate_pg_jsonl.py <input.ttl> <output_dir>
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

from rdflib import OWL, RDF, RDFS, XSD, BNode, Graph, Literal, URIRef
from rdflib.namespace import SKOS

# ---------------------------------------------------------------------------
# External vocabulary classes treated as proper data nodes
#
# Instances of these classes are fully-described data nodes in the graph but
# are typed using external vocabularies (e.g. SKOS) rather than the project's
# own owl:Class declarations. Seeding Pass 1 with them prevents their instances
# from being misclassified as ExternalReference stubs.
# ---------------------------------------------------------------------------

EXTERNAL_CLASSES: set[URIRef] = {
    SKOS.ConceptScheme,
}

# ---------------------------------------------------------------------------
# Predicates excluded from the relationships output
# ---------------------------------------------------------------------------

EXCLUDED_PREDICATES = {
    RDF.type,
    RDF.first,
    RDF.rest,
    RDFS.subClassOf,
    RDFS.subPropertyOf,
    RDFS.domain,
    RDFS.range,
    OWL.inverseOf,
    OWL.equivalentClass,
    OWL.onProperty,
    OWL.someValuesFrom,
    OWL.allValuesFrom,
    OWL.imports,
    OWL.versionIRI,
    OWL.priorVersion,
}

RDF_NIL = str(RDF.nil)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def local_name(uri: URIRef) -> str:
    """Return the local name of a URI (segment after last # or /)."""
    s = str(uri)
    for sep in ("#", "/"):
        idx = s.rfind(sep)
        if idx != -1 and idx < len(s) - 1:
            return s[idx + 1:]
    return s


def stub_namespace_label(uri: str) -> str:
    """Return the namespace segment of a stub URI (penultimate path segment).

    For https://w3id.org/uk/curriculum/nat-data-2014/year-group-1 → nat-data-2014
    """
    s = uri.rstrip("/#")
    # Drop the local name (last segment)
    for sep in ("#", "/"):
        idx = s.rfind(sep)
        if idx != -1:
            s = s[:idx]
            break
    # Return what is now the last segment (the namespace)
    for sep in ("#", "/"):
        idx = s.rfind(sep)
        if idx != -1:
            return s[idx + 1:]
    return s


def coerce_literal(lit: Literal):
    """Convert an RDF Literal to the appropriate Python scalar type."""
    dt = lit.datatype
    if dt == XSD.boolean:
        return lit.toPython()
    if dt in (XSD.integer, XSD.positiveInteger, XSD.nonNegativeInteger, XSD.int):
        try:
            return int(lit)
        except (ValueError, TypeError):
            return str(lit)
    if dt in (XSD.decimal, XSD.float, XSD.double):
        try:
            return float(lit)
        except (ValueError, TypeError):
            return str(lit)
    return str(lit)


# ---------------------------------------------------------------------------
# Core generation — private helpers (one per pass)
# ---------------------------------------------------------------------------

def _discover_ontology_entities(g: Graph) -> tuple[set[URIRef], set[str], set[str]]:
    """Pass 1: return (ontology_classes, ontology_file_uris, non_node_uris)."""
    ontology_classes: set[URIRef] = set(EXTERNAL_CLASSES)
    for s in g.subjects(RDF.type, OWL.Class):
        if isinstance(s, URIRef):
            ontology_classes.add(s)
    for s in g.subjects(RDF.type, RDFS.Class):
        if isinstance(s, URIRef):
            ontology_classes.add(s)

    ontology_files: set[str] = {
        str(s) for s in g.subjects(RDF.type, OWL.Ontology)
        if isinstance(s, URIRef)
    }
    non_node_uris: set[str] = ontology_files | {str(c) for c in ontology_classes}
    return ontology_classes, ontology_files, non_node_uris


def _collect_primary_nodes(
    g: Graph,
    ontology_classes: set[URIRef],
    ontology_files: set[str],
) -> dict[str, dict]:
    """Pass 2: return a node dict keyed by URI for every typed data instance."""
    nodes: dict[str, dict] = {}
    for subj, _, type_obj in g.triples((None, RDF.type, None)):
        if isinstance(subj, BNode) or not isinstance(type_obj, URIRef):
            continue
        if type_obj not in ontology_classes:
            continue
        s = str(subj)
        if s in ontology_files:
            continue
        if s not in nodes:
            nodes[s] = {"labels": set(), "raw_props": defaultdict(list), "stub": False}
        nodes[s]["labels"].add(local_name(type_obj))
    return nodes


def _collect_stub_nodes(
    g: Graph,
    nodes: dict[str, dict],
    non_node_uris: set[str],
) -> None:
    """Pass 3: add ExternalReference stubs for dangling relationship endpoints."""
    for subj, pred, obj in g:
        if isinstance(subj, BNode) or isinstance(obj, BNode):
            continue
        if not isinstance(obj, URIRef):
            continue
        if pred in EXCLUDED_PREDICATES:
            continue
        s_uri = str(subj)
        o_uri = str(obj)
        if s_uri not in nodes:
            continue
        if o_uri in nodes or o_uri in non_node_uris or o_uri == RDF_NIL:
            continue
        nodes[o_uri] = {"labels": set(), "raw_props": defaultdict(list), "stub": True}


def _populate_properties(g: Graph, nodes: dict[str, dict]) -> None:
    """Pass 4: attach literal properties to primary (non-stub) nodes."""
    for subj, pred, obj in g:
        if isinstance(subj, BNode):
            continue
        uri = str(subj)
        if uri not in nodes or nodes[uri]["stub"]:
            continue
        if pred == RDF.type or not isinstance(obj, Literal):
            continue
        # rdfs:label and skos:prefLabel → "name" to avoid collision with the                                                  
        # graph concept of "label" / "prefLabel" in property graph databases.                                                 
        prop_key = "name" if pred in (RDFS.label, SKOS.prefLabel) else local_name(pred)
        nodes[uri]["raw_props"][prop_key].append(coerce_literal(obj))


def _write_nodes(nodes: dict[str, dict], output_dir: Path) -> tuple[int, int]:
    """Pass 5: write nodes.jsonl; return (node_count, stub_count)."""
    node_count = 0
    stub_count = 0
    with open(output_dir / "nodes.jsonl", "w", encoding="utf-8") as f:
        for uri, data in nodes.items():
            if data["stub"]:
                labels = ["ExternalReference"]
                props: dict = {"namespace": stub_namespace_label(uri)}
                stub_count += 1
            else:
                labels = sorted(data["labels"])
                props = {
                    k: (v[0] if len(v) == 1 else v)
                    for k, v in data["raw_props"].items()
                }
            f.write(json.dumps({"id": uri, "labels": labels, "properties": props},
                               ensure_ascii=False) + "\n")
            node_count += 1
    return node_count, stub_count


def _write_relationships(g: Graph, nodes: dict[str, dict], output_dir: Path) -> int:
    """Pass 6: write relationships.jsonl; return relationship count."""
    rel_count = 0
    with open(output_dir / "relationships.jsonl", "w", encoding="utf-8") as f:
        for subj, pred, obj in g:
            if isinstance(subj, BNode) or isinstance(obj, BNode):
                continue
            if not isinstance(obj, URIRef):
                continue
            if pred in EXCLUDED_PREDICATES:
                continue
            s_uri = str(subj)
            o_uri = str(obj)
            if s_uri not in nodes or o_uri not in nodes:
                continue
            if o_uri == RDF_NIL:
                continue
            f.write(json.dumps({
                "type": local_name(pred),
                "startNodeId": s_uri,
                "endNodeId": o_uri,
                "properties": {},
            }, ensure_ascii=False) + "\n")
            rel_count += 1
    return rel_count


def generate(input_ttl: Path, output_dir: Path) -> dict:
    print(f"  Loading {input_ttl} ...")
    g = Graph()
    g.parse(str(input_ttl), format="turtle")
    print(f"  Graph contains {len(g):,} triples")

    ontology_classes, ontology_files, non_node_uris = _discover_ontology_entities(g)
    nodes = _collect_primary_nodes(g, ontology_classes, ontology_files)
    _collect_stub_nodes(g, nodes, non_node_uris)
    _populate_properties(g, nodes)

    output_dir.mkdir(parents=True, exist_ok=True)
    node_count, stub_count = _write_nodes(nodes, output_dir)
    rel_count = _write_relationships(g, nodes, output_dir)

    return {"nodes": node_count, "relationships": rel_count, "stubs": stub_count}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.ttl> <output_dir>", file=sys.stderr)
        sys.exit(1)

    input_ttl = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not input_ttl.exists():
        print(f"Error: {input_ttl} not found", file=sys.stderr)
        sys.exit(1)

    stats = generate(input_ttl, output_dir)
    print(f"    Created nodes.jsonl         ({stats['nodes']:,} nodes, "
          f"{stats['stubs']:,} external stubs)")
    print(f"    Created relationships.jsonl  ({stats['relationships']:,} relationships)")


if __name__ == "__main__":
    main()
