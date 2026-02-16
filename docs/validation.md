# SHACL Validation

This document explains how the Oak Curriculum Ontology validates its data quality using SHACL (Shapes Constraint Language) and how validation is automated through CI/CD.

## Overview

All curriculum data in this repository is validated against SHACL constraints to ensure:
- Data consistency and completeness
- Correct relationships between resources
- Compliance with curriculum structure rules
- Prevention of invalid or orphaned data

**Validation runs automatically** on every push and pull request via GitHub Actions.

## SHACL Constraints

SHACL constraints are defined in `ontology/oak-constraints.ttl`. These constraints specify rules that curriculum data must follow.

### Key Validation Rules

**Programme Constraints:**
- Every programme must have exactly one year group
- Every programme must belong to exactly one scheme (e.g., "English Key Stage 2")
- Every programme must have at least one unit variant inclusion
- Programmes must specify boolean flags: `isNationalCurriculum`, `isRequired`, `isExamined`
- Examined programmes must specify an exam type (e.g., "GCSE")
- Programmes with tiers must have exam boards

**Unit Constraints:**
- Every unit must belong to exactly one scheme
- Every unit must have at least one unit variant
- Every unit must include a "why this why now" pedagogical rationale

**Unit Variant Constraints:**
- Every unit variant must reference its parent unit
- Every unit variant must include at least one lesson
- Unit variants must not be orphaned (must be used in at least one programme)

**Sequencing Constraints:**
- Sequence positions within a programme must be unique
- Sequence positions within a unit variant must be unique
- Sequence positions must be positive integers

**Optionality Constraints:**
- Unit variant choices must have at least 2 options
- When using choices, `minChoices` and `maxChoices` must be specified
- `minChoices` cannot exceed `maxChoices` or the number of available options

See `ontology/oak-constraints.ttl` for the complete constraint definitions.

## How Validation Works

Validation occurs in three steps:

### 1. Merge TTL Files with OWL Imports Resolution

**Script:** `scripts/merge_ttls_with_imports.py`

This script:
1. Discovers all `.ttl` files in the repository (excluding `versions/` directories)
2. Parses each file and extracts its `owl:imports` declarations
3. Recursively resolves imports using a URI mapping system:
   - **External imports** (from dfe-curriculum-ontology) are fetched from GitHub
   - **Local imports** (from this repository) are resolved to local file paths
4. Combines all data into a single merged graph at `/tmp/combined-data.ttl`

**URI Resolution Mappings:**

The script maps w3id.org URIs to their actual locations:

```python
# External: DfE Curriculum Ontology (fetched from GitHub)
"https://w3id.org/uk/curriculum/core/"
  → "https://raw.githubusercontent.com/oaknational/dfe-curriculum-ontology/main/ontology/curriculum-ontology.ttl"

"https://w3id.org/uk/curriculum/england/science-programme-structure"
  → "https://raw.githubusercontent.com/oaknational/dfe-curriculum-ontology/main/data/national-curriculum-for-england/subjects/science/science-programme-structure.ttl"

# Local: Oak Curriculum Ontology (resolved to local files)
"https://w3id.org/uk/curriculum/oak-ontology"
  → "ontology/oak-ontology.ttl"

"https://w3id.org/uk/curriculum/oak-data/programme-structure"
  → "data/programme-structure.ttl"
```

This ensures that:
- Scheme definitions (like `eng:scheme-science-key-stage-3`) are loaded from the dfe-curriculum-ontology repo
- Only imports actually declared in files are fetched (no unnecessary overhead)
- Both repos remain organizationally separate while validation works correctly

### 2. Syntax Validation

**Tool:** rdflib

The merged graph is parsed to verify Turtle syntax is valid. This catches:
- Syntax errors
- Malformed URIs
- Invalid prefixes
- Structural issues

### 3. SHACL Validation

**Tool:** pyshacl

The merged data graph is validated against SHACL constraints with RDFS inference enabled:

```bash
pyshacl \
  --shacl ontology/oak-constraints.ttl \
  --ont-graph ontology/oak-ontology.ttl \
  --inference rdfs \
  --abort \
  --format human \
  /tmp/combined-data.ttl
```

**Parameters:**
- `--shacl`: The SHACL shapes file defining validation rules
- `--ont-graph`: The ontology file defining classes and properties
- `--inference rdfs`: Enable RDFS inference (e.g., class membership via `rdf:type`)
- `--abort`: Fail fast on first violation
- `--format human`: Output human-readable validation reports

If validation fails, the CI/CD pipeline stops and reports the violations.

## CI/CD Validation Pipeline

**File:** `.github/workflows/validate-ontology.yml`

The validation workflow runs on:
- Every push to `main` or `develop` branches
- Every pull request to `main`
- Manual workflow dispatch

### Workflow Steps

```yaml
1. Checkout repository
   ↓
2. Set up Python 3.11
   ↓
3. Install dependencies (rdflib, pyshacl)
   ↓
4. Merge TTLs and resolve owl:imports
   → Runs: scripts/merge_ttls_with_imports.py
   → Outputs: /tmp/combined-data.ttl
   ↓
5. Check Turtle syntax
   → Validates merged file parses correctly
   → Fails if syntax errors detected
   ↓
6. Run SHACL validation
   → Validates combined data against constraints
   → Uses RDFS inference
   → Outputs human-readable report
   → Fails if violations detected
```

**Success:** All checks pass → merge allowed

**Failure:** Validation errors reported → fix required before merge

## Running Validation Locally

### Using the Validation Script (Recommended)

Run the exact same validation as the CI/CD pipeline with a single command:

```bash
./scripts/validate.sh
```

This script:
- ✅ Merges all TTL files with auto-discovery
- ✅ Resolves external owl:imports from dfe-curriculum-ontology
- ✅ Runs SHACL validation with RDFS inference
- ✅ Matches CI/CD exactly
- ✅ Auto-detects pyshacl (checks virtual environment first, then system)

**Prerequisites:**

```bash
# Install pyshacl if not already installed
pip install pyshacl

# Or in a virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install pyshacl
```

### Manual Validation (Advanced)

If you need to run the validation steps manually:

```bash
# Step 1: Merge TTL files and resolve owl:imports
python3 scripts/merge_ttls_with_imports.py

# Step 2: Run SHACL validation
pyshacl \
  --shacl ontology/oak-constraints.ttl \
  --ont-graph ontology/oak-ontology.ttl \
  --inference rdfs \
  --abort \
  --format human \
  /tmp/combined-data.ttl
```

## Adding New Files

When adding new `.ttl` files to the repository, **no configuration changes are needed** in most cases.

### Automatic Discovery

The merge script automatically discovers all `.ttl` files in:
- `ontology/`
- `data/`
- All subdirectories (excluding `versions/`)

New files are automatically included in validation.

### When Configuration IS Needed

You only need to update `scripts/merge_ttls_with_imports.py` if:

#### 1. Adding New External owl:imports

If your new `.ttl` files import URIs from the dfe-curriculum-ontology repo that aren't already mapped, add them to `URI_MAPPINGS`:

```python
# Example: Adding English programme structure
"https://w3id.org/uk/curriculum/england/english-programme-structure":
    "https://raw.githubusercontent.com/oaknational/dfe-curriculum-ontology/main/data/national-curriculum-for-england/subjects/english/english-programme-structure.ttl",
```

**Currently mapped imports:**
- `https://w3id.org/uk/curriculum/core/` (curriculum ontology)
- `https://w3id.org/uk/curriculum/england/` (temporal structure)
- `https://w3id.org/uk/curriculum/england/science-programme-structure` (science programme structure)
- `https://w3id.org/uk/curriculum/england/science-knowledge-taxonomy` (science taxonomy)

#### 2. Adding New Local Namespaces

If you introduce new local namespaces (e.g., `oak-data/new-namespace`), add resolution logic in `resolve_import_uri()`:

```python
if "w3id.org/uk/curriculum/oak-data/new-namespace" in import_uri_str:
    local_path = repo_root / "data" / "new-namespace.ttl"
    if local_path.exists():
        return local_path
```

### What Doesn't Need Configuration

These changes work automatically:
- ✅ Adding new programmes in `data/programmes/`
- ✅ Adding new subjects in `data/programmes/<subject>/`
- ✅ Creating new data files in `data/`
- ✅ Updating existing files
- ✅ Adding new SHACL constraints in `ontology/oak-constraints.ttl`

## owl:imports Resolution

The merge script (`scripts/merge_ttls_with_imports.py`) automatically resolves `owl:imports` declarations by fetching imported resources.

### How It Works

When the script encounters an `owl:imports` declaration:

1. **Checks URI mappings** - Looks up the import URI in `URI_MAPPINGS` dictionary
2. **Resolves to source** - Maps w3id.org persistent URIs to:
   - Local file paths (for oak-curriculum-ontology resources)
   - GitHub raw URLs (for dfe-curriculum-ontology resources)
3. **Fetches recursively** - Follows import chains to build complete graph
4. **Merges into graph** - Adds imported triples to validation dataset

### Currently Mapped External Imports

From dfe-curriculum-ontology repository:

- `https://w3id.org/uk/curriculum/core/` → curriculum ontology
- `https://w3id.org/uk/curriculum/england/` → temporal structure
- `https://w3id.org/uk/curriculum/england/science-programme-structure` → science programme structure
- `https://w3id.org/uk/curriculum/england/science-knowledge-taxonomy` → science taxonomy

Standard W3C vocabularies (OWL, RDFS, SKOS, etc.) are implicitly available and don't need mapping.

### Benefits

- ✅ **Cross-repository validation** - Validates programmes against DfE curriculum schemes
- ✅ **Dependency visibility** - See exactly what external resources are imported
- ✅ **Version control** - Pin to specific branches or commits via GitHub URLs
- ✅ **No manual downloads** - Imports fetched automatically during validation

### Adding New Import Mappings

If you add owl:imports for new DfE curriculum resources not yet mapped, update `URI_MAPPINGS` in `scripts/merge_ttls_with_imports.py`:

```python
URI_MAPPINGS = {
    # Add new mapping
    "https://w3id.org/uk/curriculum/england/english-programme-structure":
        "https://raw.githubusercontent.com/oaknational/dfe-curriculum-ontology/main/data/national-curriculum-for-england/subjects/english/english-programme-structure.ttl",

    # ... existing mappings
}
```

## Common Validation Errors

### ClassConstraintComponent Violations

**Error:** "Programmes must specify which scheme (e.g., English Key Stage 2) they belong to."

**Cause:** The `curric:isPartOf` property points to a scheme that isn't defined or wasn't loaded.

**Fix:**
1. Verify the scheme exists in dfe-curriculum-ontology
2. Ensure the scheme URI is correctly spelled
3. Check that the scheme's file is mapped in `URI_MAPPINGS`

### Cardinality Violations

**Error:** "Every programme must have exactly one year group."

**Cause:** A programme has zero or multiple `oakcurric:hasYearGroup` properties.

**Fix:** Ensure each programme has exactly one year group declaration.

### Orphaned Resource Violations

**Error:** "Unit variant is not used in any programme (orphaned)"

**Cause:** A unit variant exists but isn't referenced by any `UnitVariantInclusion`.

**Fix:** Either add the unit variant to a programme or remove it.

### Sequence Position Violations

**Error:** "Sequence positions must be unique within a programme"

**Cause:** Multiple unit variant inclusions have the same `sequencePosition` value.

**Fix:** Ensure each inclusion in a programme has a unique sequence position.

## Best Practices

1. **Run validation locally** before pushing to catch errors early
2. **Check the CI/CD output** if validation fails to see detailed error reports
3. **Update URI mappings** when adding imports from new external files
4. **Keep constraints synchronized** with data model changes
5. **Use meaningful SHACL messages** to help diagnose validation failures

## Further Reading

- [SHACL Specification (W3C)](https://www.w3.org/TR/shacl/)
- [pyshacl Documentation](https://github.com/RDFLib/pySHACL)
- [DfE Curriculum Ontology Repository](https://github.com/oaknational/dfe-curriculum-ontology)
