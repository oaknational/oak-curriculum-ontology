#!/bin/bash
# Local validation script that matches CI/CD exactly
set -eo pipefail

echo "========================================================================"
echo "LOCAL VALIDATION (matches CI/CD)"
echo "========================================================================"
echo ""

# Pre-flight checks
if [[ ! -f "scripts/merge_ttls_with_imports.py" ]]; then
    echo "❌ Error: scripts/merge_ttls_with_imports.py not found"
    exit 1
fi

if [[ ! -f "ontology/oak-curriculum-constraints.ttl" ]]; then
    echo "❌ Error: ontology/oak-curriculum-constraints.ttl not found"
    exit 1
fi

if [[ ! -f "ontology/oak-curriculum-ontology.ttl" ]]; then
    echo "❌ Error: ontology/oak-curriculum-ontology.ttl not found"
    exit 1
fi

echo "Step 1: Merge TTL files and resolve imports..."
if command -v uv &> /dev/null; then
    uv run python3 scripts/merge_ttls_with_imports.py
else
    python3 scripts/merge_ttls_with_imports.py
fi

# Verify merge output exists
if [[ ! -f "/tmp/combined-data.ttl" ]]; then
    echo "❌ Error: Merge script did not produce /tmp/combined-data.ttl"
    exit 1
fi

echo ""
echo "Step 2: Check Turtle syntax..."

# Run syntax check using rdflib
SYNTAX_CHECK_SCRIPT='
from rdflib import Graph
try:
    g = Graph()
    g.parse("/tmp/combined-data.ttl", format="turtle")
    print("✅ Merged Turtle syntax is valid")
except Exception as e:
    print(f"❌ Turtle syntax error: {e}")
    exit(1)
'

if command -v uv &> /dev/null; then
    uv run python3 -c "$SYNTAX_CHECK_SCRIPT"
else
    python3 -c "$SYNTAX_CHECK_SCRIPT"
fi

echo ""
echo "Step 3: Run SHACL validation..."

# Run pyshacl - prefer uv, then venv, then system
if command -v uv &> /dev/null; then
    uv run pyshacl \
        --shacl ontology/oak-curriculum-constraints.ttl \
        --ont-graph ontology/oak-curriculum-ontology.ttl \
        --inference rdfs \
        --abort \
        --format human \
        /tmp/combined-data.ttl
elif [[ -f ".venv/bin/pyshacl" ]]; then
    .venv/bin/pyshacl \
        --shacl ontology/oak-curriculum-constraints.ttl \
        --ont-graph ontology/oak-curriculum-ontology.ttl \
        --inference rdfs \
        --abort \
        --format human \
        /tmp/combined-data.ttl
elif command -v pyshacl &> /dev/null; then
    pyshacl \
        --shacl ontology/oak-curriculum-constraints.ttl \
        --ont-graph ontology/oak-curriculum-ontology.ttl \
        --inference rdfs \
        --abort \
        --format human \
        /tmp/combined-data.ttl
else
    echo "❌ Error: pyshacl not found"
    echo ""
    echo "Install it with:"
    echo "  uv add pyshacl"
    echo ""
    echo "Or without uv:"
    echo "  pip install pyshacl"
    exit 1
fi

echo ""
echo "========================================================================"
echo "✅ All validation passed!"
echo "========================================================================"
