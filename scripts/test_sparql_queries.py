#!/usr/bin/env python3
"""
Test SPARQL queries against the merged curriculum data.

Usage:
    uv run python scripts/test_sparql_queries.py

This script:
1. Merges all TTL files using the existing merge script
2. Runs example SPARQL queries
3. Reports results to verify queries work correctly
"""

from rdflib import Graph
import subprocess
import sys
from pathlib import Path


def merge_data():
    """Run the merge script to create combined data."""
    repo_root = Path(__file__).parent.parent
    result = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "merge_ttls_with_imports.py"), "-q"],
        capture_output=True,
        text=True,
        cwd=repo_root
    )
    if result.returncode != 0:
        print(f"Error merging TTL files: {result.stderr}")
        sys.exit(1)


def load_graph():
    """Load the merged data into an RDF graph."""
    g = Graph()
    g.parse("/tmp/combined-data.ttl", format="turtle")
    return g


QUERIES = {
    "Find all Year 7 programmes": """
        PREFIX curric: <https://w3id.org/uk/oak/curriculum/ontology/>
        PREFIX natcurric: <https://w3id.org/uk/oak/curriculum/nationalcurriculum/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?programme ?label WHERE {
          ?programme a curric:Programme ;
                     curric:coversYearGroup natcurric:year-group-7 ;
                     rdfs:label ?label .
        }
        ORDER BY ?label
    """,

    "Find Mathematics content descriptors": """
        PREFIX curric: <https://w3id.org/uk/oak/curriculum/ontology/>
        PREFIX natcurric: <https://w3id.org/uk/oak/curriculum/nationalcurriculum/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT ?descriptor ?label WHERE {
          natcurric:discipline-mathematics skos:narrower+ ?descriptor .
          ?descriptor a curric:ContentDescriptor ;
                      skos:prefLabel ?label .
        }
        ORDER BY ?label
    """,

    "List units in sequence for a programme": """
        PREFIX curric: <https://w3id.org/uk/oak/curriculum/ontology/>
        PREFIX oakcurric: <https://w3id.org/uk/oak/curriculum/oakcurriculum/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?position ?unitVariant ?label WHERE {
          oakcurric:programme-mathematics-year-group-7
            curric:hasUnitVariantInclusion ?inclusion .
          ?inclusion curric:sequencePosition ?position ;
                     curric:includesUnitVariant ?unitVariant .
          ?unitVariant rdfs:label ?label .
        }
        ORDER BY ?position
    """,

    "Find programmes by subject": """
        PREFIX curric: <https://w3id.org/uk/oak/curriculum/ontology/>
        PREFIX natcurric: <https://w3id.org/uk/oak/curriculum/nationalcurriculum/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?subject ?subjectLabel ?programme ?programmeLabel WHERE {
          ?programme a curric:Programme ;
                     rdfs:label ?programmeLabel ;
                     curric:isProgrammeOf ?scheme .
          ?scheme curric:isSchemeOf ?subject .
          ?subject rdfs:label ?subjectLabel .
        }
        ORDER BY ?subjectLabel ?programmeLabel
    """,

    "Find all Key Stage 3 Science content": """
        PREFIX curric: <https://w3id.org/uk/oak/curriculum/ontology/>
        PREFIX natcurric: <https://w3id.org/uk/oak/curriculum/nationalcurriculum/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT DISTINCT ?content ?label WHERE {
          natcurric:discipline-science skos:narrower+ ?content .
          ?content skos:prefLabel ?label .
        }
        ORDER BY ?label
    """,
}


def run_query(graph, name, query, limit=10):
    """Run a SPARQL query and print results."""
    print(f"\n{'='*60}")
    print(f"Query: {name}")
    print('='*60)

    try:
        results = graph.query(query)
        count = 0
        for row in results:
            if count < limit:
                print("  " + " | ".join(str(v) for v in row))
            count += 1

        if count == 0:
            print("  (no results)")
        elif count > limit:
            print(f"  ... and {count - limit} more")

        print(f"\nTotal results: {count}")
        return count > 0

    except Exception as e:
        print(f"ERROR: {e}")
        return False


def main():
    """Main entry point."""
    print("Merging TTL files...")
    merge_data()

    print("Loading merged data...")
    graph = load_graph()
    print(f"Loaded {len(graph)} triples")

    all_passed = True
    for name, query in QUERIES.items():
        if not run_query(graph, name, query):
            all_passed = False

    print("\n" + "="*60)
    if all_passed:
        print("SUCCESS: All queries returned results.")
    else:
        print("FAILURE: Some queries returned no results!")
        sys.exit(1)


if __name__ == "__main__":
    main()
