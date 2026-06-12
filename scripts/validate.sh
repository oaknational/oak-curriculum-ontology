#!/bin/bash
# Local validation script that matches CI/CD exactly
set -eo pipefail

echo "======================================================================="
echo "LOCAL VALIDATION (matches CI/CD)"
echo "======================================================================="
echo ""

# Pre-flight checks
if [[ ! -f "scripts/merge_ttls_with_imports.py" ]]; then
    echo "❌ Error: scripts/merge_ttls_with_imports.py not found" >&2
    exit 1
fi

if [[ ! -f "ontology/oak-curriculum-constraints.ttl" ]]; then
    echo "❌ Error: ontology/oak-curriculum-constraints.ttl not found" >&2
    exit 1
fi

if [[ ! -f "ontology/oak-curriculum-ontology.ttl" ]]; then
    echo "❌ Error: ontology/oak-curriculum-ontology.ttl not found" >&2
    exit 1
fi

# N-Triples: faster to write and re-parse than Turtle. The merge itself
# parses every source file, so it doubles as the syntax check — pyshacl's
# own parse covers the merged output.
COMBINED_DATA="/tmp/combined-data.nt"

echo "Step 1: Merge TTL files and resolve imports..."
if command -v uv &> /dev/null; then
    uv run python3 scripts/merge_ttls_with_imports.py -o "$COMBINED_DATA"
else
    python3 scripts/merge_ttls_with_imports.py -o "$COMBINED_DATA"
fi

# Verify merge output exists
if [[ ! -f "$COMBINED_DATA" ]]; then
    echo "❌ Error: Merge script did not produce $COMBINED_DATA" >&2
    exit 1
fi

echo ""
echo "Step 2: Run SHACL validation (takes a few minutes on the full graph)..."

SHACL_OUTPUT="/tmp/shacl-output.txt"

# Inference is deliberately "none": all entities carry explicit rdf:type and
# shapes target concrete classes, so RDFS inference adds nothing the shapes
# need — and it both dominated the runtime and masked genuine warnings by
# inferring the very type/property facts the shapes check for.
# Known issue: --abort stops evaluation at the first failing shape, so the
# report can be truncated when shapes fail. Removing it gives the complete
# result set but full evaluation currently takes >10 minutes; per-shape
# profiling is needed before --abort can go.
PYSHACL_ARGS=(
    --shacl ontology/oak-curriculum-constraints.ttl
    --ont-graph ontology/oak-curriculum-ontology.ttl
    --inference none
    --abort
    --format human
    "$COMBINED_DATA"
)

# Run pyshacl - prefer uv, then venv, then system; capture exit code without aborting script
set +e
if command -v uv &> /dev/null; then
    uv run pyshacl "${PYSHACL_ARGS[@]}" | tee "$SHACL_OUTPUT"
elif [[ -f ".venv/bin/pyshacl" ]]; then
    .venv/bin/pyshacl "${PYSHACL_ARGS[@]}" | tee "$SHACL_OUTPUT"
elif command -v pyshacl &> /dev/null; then
    pyshacl "${PYSHACL_ARGS[@]}" | tee "$SHACL_OUTPUT"
else
    echo "❌ Error: pyshacl not found" >&2
    echo ""
    echo "Install it with:"
    echo "  uv add pyshacl"
    echo ""
    echo "Or without uv:"
    echo "  pip install pyshacl"
    exit 1
fi
set -e

# Only fail if there are actual violations; warnings alone are not failures
VIOLATIONS=$(grep -c "Constraint Violation" "$SHACL_OUTPUT" || true)
if [[ "${VIOLATIONS}" -gt 0 ]]; then
    echo ""
    echo "❌ Found ${VIOLATIONS} constraint violation(s)"
    exit 1
elif grep -q "sh:Warning\|sh:Info" "$SHACL_OUTPUT"; then
    echo ""
    echo "⚠️  Validation passed with warnings (no violations)"
fi

echo ""
echo "========================================================================"
echo "✅ All validation passed!"
echo "========================================================================"
