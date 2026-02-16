# Scripts

Utility scripts for working with the Oak Curriculum Ontology.

## Quick Reference

| Script | Purpose | When to Use |
|--------|---------|-------------|
| [`validate.sh`](#validate) | Validate RDF data with SHACL | Before committing data changes |
| [`export_to_neo4j.py`](#export-to-neo4j) | Export RDF to Neo4j graph database | Deploy data to Neo4j for querying |
| [`merge_ttls_with_imports.py`](#merge-ttl-files) | Merge TTL files resolving imports | Create single combined RDF file |
| [`build_static_data.sh`](#build-distributions) | Generate distribution files | Publish data in multiple formats |

---

## validate.sh

**Purpose:** Validate all RDF data against SHACL constraints (matches CI/CD validation)

**Usage:**
```bash
./scripts/validate.sh
```

**What it does:**
1. Merges all TTL files using `merge_ttls_with_imports.py`
2. Validates Turtle syntax
3. Runs SHACL validation with RDFS inference

**Requirements:**
- Python with `rdflib` and `pyshacl` (automatically handled with `uv`)

**Output:**
- ✅ Success if all validation passes
- ❌ Error details if validation fails

---

## export_to_neo4j.py

**Purpose:** Export RDF curriculum data to Neo4j AuraDB with extensive graph transformations

**Usage:**
```bash
# Basic export
python scripts/export_to_neo4j.py --config scripts/export_to_neo4j_config.json

# Clear database first
python scripts/export_to_neo4j.py --config scripts/export_to_neo4j_config.json --clear

# Dry run (validate without executing)
python scripts/export_to_neo4j.py --config scripts/export_to_neo4j_config.json --dry-run

# List files that would be processed
python scripts/export_to_neo4j.py --config scripts/export_to_neo4j_config.json --list-files

# Verbose logging
python scripts/export_to_neo4j.py --config scripts/export_to_neo4j_config.json --verbose
```

**What it does:**
1. Loads and filters TTL files from `data/` directory
2. Imports RDF triples to Neo4j using `rdflib-neo4j`
3. Applies 14 graph transformations:
   - Label mapping (Resource → NatCurric/OakCurric)
   - Property renaming (label → programmeTitle, etc.)
   - Slug extraction from URIs
   - Relationship flattening (inclusion patterns)
   - Multi-valued property arrays
   - External relationship creation
   - Cleanup and optimization

**Requirements:**
- Neo4j AuraDB instance
- `.env` file with Neo4j credentials (see below)
- Python dependencies: `rdflib`, `rdflib-neo4j`, `neo4j`, `pydantic`, `python-dotenv`, `tqdm`

**Configuration:**

Create a `.env` file in the project root:
```bash
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password-here
NEO4J_DATABASE=neo4j
```

Edit `scripts/export_to_neo4j_config.json` to customize:
- Which TTL files to import
- Label mappings
- Property mappings
- Relationship transformations

**Architecture:**

For detailed documentation on the script architecture, transformations, and configuration:
- See [`export_to_neo4j_ARCHITECTURE.md`](./export_to_neo4j_ARCHITECTURE.md)

**Performance:**
- Batched processing (5000 triples/batch)
- Indexed URI lookups
- Pre-cached relationship labels
- Retry logic with exponential backoff
- Progress bars with `tqdm`

---

## merge_ttls_with_imports.py

**Purpose:** Merge multiple TTL files into a single file, recursively resolving `owl:imports`

**Usage:**
```bash
# Merge data/ directory (default)
python scripts/merge_ttls_with_imports.py

# Merge specific paths
python scripts/merge_ttls_with_imports.py ontology/ data/

# Custom output file
python scripts/merge_ttls_with_imports.py -o /tmp/my-output.ttl

# Verbose logging
python scripts/merge_ttls_with_imports.py -v

# Quiet mode (warnings/errors only)
python scripts/merge_ttls_with_imports.py -q
```

**What it does:**
1. Discovers all `.ttl` files in specified paths
2. Parses each file and extracts `owl:imports` declarations
3. Recursively resolves imports (local files and remote URLs)
4. Merges all triples into a single RDF graph
5. Outputs combined Turtle file

**Features:**
- ✅ Resolves local file imports
- ✅ Resolves remote HTTP(S) imports
- ✅ Handles relative import paths
- ✅ Skips files in `versions/` directories
- ✅ Avoids duplicate imports (caches seen files/URIs)
- ✅ Supports GitHub raw URLs

**Requirements:**
- Python with `rdflib`

**Default Output:**
- `/tmp/combined-data.ttl`

---

## build_static_data.sh

**Purpose:** Generate static distribution files in multiple RDF formats

**Usage:**
```bash
./scripts/build_static_data.sh
```

**What it does:**
1. Collects all TTL files from:
   - `ontology/*.ttl`
   - `data/*.ttl`
   - `data/subjects/**/*.ttl`
2. Generates distribution files:
   - **Turtle** (`.ttl`) - Canonical format
   - **JSON-LD** (`.jsonld`) - JSON-based RDF
   - **RDF/XML** (`.rdf`) - XML-based RDF
   - **N-Triples** (`.nt`) - Line-based format

**Requirements:**
- Apache Jena toolkit with `riot` command
- Install: https://jena.apache.org/download/

**Output:**
- Directory: `distributions/`
- Files:
  - `oak-curriculum-full.ttl`
  - `oak-curriculum-full.jsonld`
  - `oak-curriculum-full.rdf`
  - `oak-curriculum-full.nt`

**Use Case:**
- Publishing curriculum data in standard RDF formats
- Providing downloadable distribution files
- Supporting different RDF tooling ecosystems

---

## Development

### Type Checking

All Python scripts pass `mypy --strict` validation:

```bash
# Check export script
uv run mypy --strict scripts/export_to_neo4j.py

# Check merge script
uv run mypy --strict scripts/merge_ttls_with_imports.py
```

Configuration in `pyproject.toml`:
- Strict mode enabled
- Python 3.12 target
- Complete type hints throughout

### Code Quality

**Python scripts:**
- ✅ Modern type hints (PEP 585, PEP 604)
- ✅ Comprehensive error handling
- ✅ CLI argument parsing with `argparse`
- ✅ Progress bars for long operations
- ✅ Retry logic for transient failures
- ✅ Dataclasses for structured data

**Shell scripts:**
- ✅ Strict error handling (`set -eo pipefail`)
- ✅ Pre-flight validation checks
- ✅ Clear success/failure output
- ✅ Helpful error messages

### Dependencies

Python dependencies are managed in `pyproject.toml`:

```bash
# Install runtime dependencies
uv pip install -e .

# Install dev dependencies (includes mypy, ruff)
uv pip install -e ".[dev]"
```

---

## Troubleshooting

### "Module not found" errors

If you see import errors, install dependencies:
```bash
uv pip install -e .
```

### "riot command not found"

For `build_static_data.sh`, install Apache Jena:
- Download: https://jena.apache.org/download/
- Ensure `riot` is in your `PATH`

### Neo4j connection errors

Check your `.env` file:
- Verify `NEO4J_URI` is correct
- Verify `NEO4J_PASSWORD` is correct
- Test connection with Neo4j Browser

### SHACL validation failures

Run `validate.sh` with verbose output to see constraint violations:
```bash
./scripts/validate.sh
```

Common issues:
- Missing required properties
- Invalid URI patterns
- Type mismatches
- Cardinality violations

---

## Contributing

When adding new scripts:
1. Add type hints for Python scripts
2. Validate with `mypy --strict`
3. Add usage examples to this README
4. Use consistent CLI patterns (argparse, verbose flags, etc.)
5. Include error handling and helpful error messages
