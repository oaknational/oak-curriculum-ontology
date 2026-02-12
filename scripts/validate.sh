#!/bin/bash
# Local validation script that matches CI/CD exactly
set -e

echo "========================================================================"
echo "LOCAL VALIDATION (matches CI/CD)"
echo "========================================================================"
echo ""

echo "Step 1: Merge TTL files and resolve imports..."
if command -v uv &> /dev/null; then
    uv run python3 scripts/merge_ttls_with_imports.py
else
    python3 scripts/merge_ttls_with_imports.py
fi

echo ""
echo "Step 2: Run SHACL validation..."

# Try to find pyshacl - prefer uv, then venv, then system
if command -v uv &> /dev/null; then
    PYSHACL="uv run pyshacl"
elif [ -f ".venv/bin/pyshacl" ]; then
    PYSHACL=".venv/bin/pyshacl"
elif command -v pyshacl &> /dev/null; then
    PYSHACL="pyshacl"
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

$PYSHACL \
  --shacl ontology/oak-curriculum-constraints.ttl \
  --ont-graph ontology/oak-curriculum-ontology.ttl \
  --inference rdfs \
  --abort \
  --format human \
  /tmp/combined-data.ttl

echo ""
echo "========================================================================"
echo "✅ All validation passed!"
echo "========================================================================"
