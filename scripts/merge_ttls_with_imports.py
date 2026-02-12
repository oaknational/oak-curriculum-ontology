#!/usr/bin/env python3
"""
merge_ttls_with_imports.py

Merge TTL files into a single file, recursively resolving owl:imports.
Excludes any files inside directories named "versions".
"""

from pathlib import Path
from rdflib import Graph, URIRef
from urllib.parse import urlparse
import urllib.request
import ssl

# --------------------------
# Configuration
# --------------------------
OUTPUT_FILE = "/tmp/combined-data.ttl"

# Entry points: the root TTLs or directories of TTLs to merge
# Note: ontology and SHACL constraints are passed separately to pyshacl
ROOT_TTLS = [
    "data",
]

# OWL imports predicate
OWL_IMPORTS = URIRef("http://www.w3.org/2002/07/owl#imports")

# --------------------------
# Graph and state
# --------------------------
g = Graph()
seen_files = set()

# URI to file path mapping - all URIs are resolved dynamically in resolve_import_uri()
URI_MAPPINGS = {}

seen_uris = set()

# --------------------------
# Functions
# --------------------------
def resolve_import_uri(import_uri, repo_root):
    """
    Resolve an import URI to a fetchable location.
    Returns the URI/path to fetch, or None if it can't be resolved.
    """
    import re
    import_uri_str = str(import_uri)

    # Check if there's a direct mapping
    if import_uri_str in URI_MAPPINGS:
        return URI_MAPPINGS[import_uri_str]

    # Check if it's already a GitHub raw URL
    if "raw.githubusercontent.com" in import_uri_str:
        return import_uri_str

    # Handle core ontology
    # e.g., https://w3id.org/oak/curriculum/core/ -> ontology/oak-curriculum-ontology.ttl
    if "w3id.org/oak/curriculum/core" in import_uri_str:
        local_path = repo_root / "ontology" / "oak-curriculum-ontology.ttl"
        if local_path.exists():
            return local_path

    # Handle oak-ontology
    # e.g., https://w3id.org/oak/curriculum/oak-ontology -> ontology/oak-curriculum-ontology.ttl
    if "w3id.org/oak/curriculum/oak-ontology" in import_uri_str:
        local_path = repo_root / "ontology" / "oak-curriculum-ontology.ttl"
        if local_path.exists():
            return local_path

    # Handle /ontology (without oak- prefix)
    # e.g., https://w3id.org/oak/curriculum/ontology -> ontology/oak-curriculum-ontology.ttl
    if import_uri_str.rstrip("/").endswith("w3id.org/oak/curriculum/ontology"):
        local_path = repo_root / "ontology" / "oak-curriculum-ontology.ttl"
        if local_path.exists():
            return local_path

    # Handle oakcurriculum/programme-structure
    # e.g., https://w3id.org/oak/curriculum/oakcurriculum/programme-structure -> data/programme-structure.ttl
    if "w3id.org/oak/curriculum/oakcurriculum/programme-structure" in import_uri_str:
        local_path = repo_root / "data" / "programme-structure.ttl"
        if local_path.exists():
            return local_path

    # Handle oakcurriculum/threads
    # e.g., https://w3id.org/oak/curriculum/oakcurriculum/threads -> data/threads.ttl
    if "w3id.org/oak/curriculum/oakcurriculum/threads" in import_uri_str:
        local_path = repo_root / "data" / "threads.ttl"
        if local_path.exists():
            return local_path

    # Handle nationalcurriculum/temporal-structure or just nationalcurriculum/
    # e.g., https://w3id.org/oak/curriculum/nationalcurriculum/temporal-structure -> data/temporal-structure.ttl
    if "w3id.org/oak/curriculum/nationalcurriculum/temporal-structure" in import_uri_str:
        local_path = repo_root / "data" / "temporal-structure.ttl"
        if local_path.exists():
            return local_path

    if import_uri_str.rstrip("/").endswith("w3id.org/oak/curriculum/nationalcurriculum"):
        local_path = repo_root / "data" / "temporal-structure.ttl"
        if local_path.exists():
            return local_path

    # Handle nationalcurriculum/{subject}-programme-structure
    # e.g., https://w3id.org/oak/curriculum/nationalcurriculum/biology-programme-structure
    #       -> data/subjects/biology/biology-programme-structure.ttl
    match = re.search(r"w3id\.org/oak/curriculum/nationalcurriculum/(\w+)-programme-structure", import_uri_str)
    if match:
        subject = match.group(1)
        local_path = repo_root / "data" / "subjects" / subject / f"{subject}-programme-structure.ttl"
        if local_path.exists():
            return local_path

    # Handle nationalcurriculum/{subject}-knowledge-taxonomy
    # e.g., https://w3id.org/oak/curriculum/nationalcurriculum/biology-knowledge-taxonomy
    #       -> data/subjects/biology/biology-knowledge-taxonomy.ttl
    match = re.search(r"w3id\.org/oak/curriculum/nationalcurriculum/(\w+)-knowledge-taxonomy", import_uri_str)
    if match:
        subject = match.group(1)
        local_path = repo_root / "data" / "subjects" / subject / f"{subject}-knowledge-taxonomy.ttl"
        if local_path.exists():
            return local_path

    # Handle oak-data files
    # e.g., https://w3id.org/oak/curriculum/oak-data/programme-structure -> data/programme-structure.ttl
    if "w3id.org/oak/curriculum/oak-data/" in import_uri_str:
        # Extract the filename part after oak-data/
        filename = import_uri_str.split("oak-data/")[-1].rstrip("/")
        local_path = repo_root / "data" / f"{filename}.ttl"
        if local_path.exists():
            return local_path

    # Check if it's a local file path
    import_path = Path(import_uri_str)
    if import_path.exists():
        return import_path

    return None


def parse_with_imports(file_path_or_uri, repo_root):
    """
    Parse a TTL file and recursively parse any owl:imports.
    Excludes files in directories called 'versions'.
    """
    # Handle local file paths
    if isinstance(file_path_or_uri, Path):
        file_path = file_path_or_uri.resolve()
        if file_path in seen_files:
            return
        if "versions" in file_path.parts:
            print(f"⏭ Skipping versioned file: {file_path}")
            return
        if not file_path.exists():
            print(f"⚠️ File does not exist: {file_path}")
            return

        print(f"📄 Parsing: {file_path}")
        g.parse(str(file_path), format="turtle")
        seen_files.add(file_path)

    # Handle remote URIs    
    else:
        import_uri_str = str(file_path_or_uri)
        if import_uri_str in seen_uris:
            return
        seen_uris.add(import_uri_str)

        resolved = resolve_import_uri(file_path_or_uri, repo_root)
        if resolved is None:
            print(f"⚠️ Warning: Cannot resolve import URI: {import_uri_str}")
            return

        # If resolved to a local file, check if already parsed
        if isinstance(resolved, Path):
            resolved_path = resolved.resolve()
            if resolved_path in seen_files:
                return
            print(f"🌐 Fetching: {import_uri_str}")
            print(f"   → from: {resolved}")
            seen_files.add(resolved_path)
            try:
                g.parse(str(resolved_path), format="turtle")
            except Exception as e:
                print(f"❌ Error parsing {resolved_path}: {e}")
            return

        # Remote URL - fetch and parse
        print(f"🌐 Fetching: {import_uri_str}")
        print(f"   → from: {resolved}")

        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(resolved, context=ssl_context) as response:
                g.parse(data=response.read(), format="turtle")
        except Exception as e:
            print(f"❌ Error parsing {resolved}: {e}")
            return

    # Recursively parse owl:imports
    for o in g.objects(None, OWL_IMPORTS):
        import_uri_str = str(o)

        # Skip if already processed
        if import_uri_str in seen_uris:
            continue

        # Try to resolve as a local file first
        import_path = Path(import_uri_str)
        if import_path.is_absolute() and import_path.exists():
            parse_with_imports(import_path, repo_root)
        elif not import_path.is_absolute():
            # Try relative to current file (if we have one)
            if isinstance(file_path_or_uri, Path):
                rel_path = file_path_or_uri.parent / import_path
                if rel_path.exists():
                    parse_with_imports(rel_path, repo_root)
                    continue

        # Otherwise treat as a URI that needs resolution
        parse_with_imports(o, repo_root)

# --------------------------
# Main merge
# --------------------------
# Get repo root (assuming script is in scripts/ directory)
repo_root = Path(__file__).parent.parent

for f in ROOT_TTLS:
    p = repo_root / f
    if p.is_dir():
        for ttl_file in sorted(p.rglob("*.ttl")):
            parse_with_imports(ttl_file, repo_root)
    elif p.is_file():
        parse_with_imports(p, repo_root)
    else:
        print(f"⚠️ Root path not found: {f}")

# Serialize merged graph
g.serialize(destination=OUTPUT_FILE, format="turtle")
print(f"\n✅ Merged {len(seen_files)} files (excluding 'versions') into {OUTPUT_FILE}")
