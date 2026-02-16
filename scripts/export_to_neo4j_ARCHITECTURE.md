# Neo4j Export Script Architecture

## Overview

The `export_to_neo4j.py` script exports RDF/TTL curriculum data to Neo4j AuraDB with extensive transformations to optimize the graph structure for querying and traversal.

**Key Features:**
- Config-driven (reusable for other RDF repositories)
- Strategy pattern for extensible transformations
- Batched processing for performance
- Comprehensive error handling with retry logic
- Type-safe with modern Python 3.11+ type hints

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         MAIN PIPELINE                            │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
         ┌───────────────────────────────────────┐
         │   1. Parse CLI Arguments              │
         │      --config, --clear, --dry-run,    │
         │      --list-files, --verbose          │
         └───────────────────┬───────────────────┘
                             │
                             ▼
         ┌───────────────────────────────────────┐
         │   2. Load & Validate Configuration    │
         │      - JSON config file               │
         │      - Environment variables (.env)   │
         │      - Pydantic validation            │
         └───────────────────┬───────────────────┘
                             │
                             ▼
         ┌───────────────────────────────────────┐
         │   3. Clear Database (optional)        │
         │      - Delete nodes by label          │
         │      - Batched deletion (1000/batch)  │
         └───────────────────┬───────────────────┘
                             │
                             ▼
         ┌───────────────────────────────────────┐
         │   4. Discover TTL Files               │
         │      - Glob patterns from config      │
         │      - Ordered for dependencies       │
         └───────────────────┬───────────────────┘
                             │
                             ▼
         ┌───────────────────────────────────────┐
         │   5. Connect to Neo4j                 │
         │      - rdflib-neo4j store             │
         │      - With retry on connection       │
         └───────────────────┬───────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────┐
│              6. LOAD & AGGREGATE TTL FILES                 │
│                   (RDFLoader class)                        │
└────────────────────────────────────────────────────────────┘
         │
         │  For each TTL file:
         │  ┌─────────────────────────────────────────────┐
         │  │  a) Parse TTL → RDF Graph                   │
         │  │  b) Extract metadata (slugs, types, etc.)   │
         │  │  c) Filter unwanted triples                 │
         │  │     - Ontology declarations                 │
         │  │     - Excluded predicates                   │
         │  │     - Excluded entity types                 │
         │  │  d) Add triples to Neo4j (batched)          │
         │  │  e) Aggregate metadata across files         │
         │  └─────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────┐
│         7. APPLY TRANSFORMATIONS (Pipeline)                │
│              (TransformationPipeline class)                │
└────────────────────────────────────────────────────────────┘
         │
         │  Transformations (in order):
         │  ┌─────────────────────────────────────────────┐
         │  │  1.  Label Mapping (Resource → NatCurric)   │
         │  │  2.  Add External Type Labels               │
         │  │  3.  Remove Unwanted Labels                 │
         │  │  4.  Slug Extraction                        │
         │  │  5.  Object URI Properties                  │
         │  │  6.  Multi-Valued Properties                │
         │  │  7.  Property Mapping (rename)              │
         │  │  8.  Relationship Type Mapping              │
         │  │  9.  Reverse Relationships                  │
         │  │  10. Inclusion Flattening                   │
         │  │  11. CamelCase → UPPER_CASE                 │
         │  │  12. External Relationships                 │
         │  │  13. Cleanup Orphaned Nodes                 │
         │  │  14. Drop Resource Constraint               │
         │  └─────────────────────────────────────────────┘
         │
         ▼
         ┌───────────────────────────────────────┐
         │   8. Verify Export                    │
         │      - Count nodes by label           │
         │      - Log statistics                 │
         └───────────────────┬───────────────────┘
                             │
                             ▼
         ┌───────────────────────────────────────┐
         │   9. Finalize & Close                 │
         │      - Final commit (with retry)      │
         │      - Close Neo4j store              │
         └───────────────────────────────────────┘
```

---

## Key Components

### 1. Configuration System

**File:** `export_to_neo4j_config.json`

**Purpose:** Config-driven design makes the script reusable for different RDF repositories.

**Key Sections:**
- `rdf_source` - TTL file discovery, namespaces, filters
- `neo4j_connection` - Connection settings, batch sizes
- `label_mapping` - Transform labels (e.g., Resource → NatCurric)
- `property_mappings` - Rename properties per node type
- `uri_slug_extraction` - Extract URI slugs as properties
- `multi_valued_properties` - RDF lists → Neo4j arrays
- `relationship_type_mappings` - Rename relationships
- `reverse_relationships` - Flip relationship direction
- `inclusion_flattening` - Flatten reified relationships

**Validation:** Pydantic models ensure type safety and validation.

---

### 2. RDFLoader Class

**Responsibility:** Load, filter, and extract metadata from TTL files.

**Key Methods:**

#### `discover_files() -> list[Path]`
- Finds TTL files using glob patterns
- Respects include/exclude patterns
- Returns files in discovery order

#### `load_and_filter(ttl_file) -> FilteredGraphResult`
- Parses TTL file into RDF graph
- Extracts metadata BEFORE filtering:
  - Multi-valued properties (RDF lists)
  - URI slugs
  - Object URI properties
  - RDF types
  - External relationships
- Filters unwanted triples:
  - By entity type (e.g., owl:Ontology)
  - By property type
  - By predicate globally
- Returns structured FilteredGraphResult dataclass

#### Filtering Methods:
- `_filter_by_entity_type()` - Remove subjects of specific types
- `_filter_properties_by_type()` - Remove properties from specific types
- `_filter_predicates_globally()` - Remove predicates everywhere

#### Extraction Methods:
- `_extract_multi_valued_properties()` - RDF lists → Python lists
- `_extract_slugs()` - Last URI segment → property
- `_extract_object_uri_properties()` - Object URIs → properties
- `_extract_rdf_types()` - All rdf:type triples
- `_extract_external_relationships()` - Relationships to external nodes

---

### 3. Transformation System

**Architecture:** Strategy Pattern

Each transformation is an independent class implementing the `Transformation` interface:

```python
class Transformation(ABC):
    @abstractmethod
    def name() -> str: ...

    @abstractmethod
    def should_run(config) -> bool: ...

    @abstractmethod
    def execute(session, config, main_labels, data) -> int: ...
```

#### Key Transformations:

**LabelMappingTransformation**
- Replaces generic labels with domain-specific ones
- Example: Resource → NatCurric (for National Curriculum nodes)

**InclusionFlatteningTransformation**
- Flattens reified relationships into direct edges with properties
- Example: (Unit)-[inclusion]->(Lesson) → (Unit)-[HAS_LESSON{lessonOrder}]->(Lesson)
- Optimizes graph for Neo4j traversals

**PropertyMappingTransformation**
- Renames properties based on node type
- Example: Phase.label → Phase.phaseTitle

**ExternalRelationshipsTransformation**
- Creates relationships to external nodes
- Pre-caches target labels to avoid N+1 queries

---

### 4. Error Handling & Retry Logic

**Retry Function:** `retry_on_transient_error()`
- Exponential backoff (2s → 4s → 8s)
- Max 3 retries
- Only retries transient errors:
  - `TransientError`
  - `ServiceUnavailable`
- Does NOT retry:
  - `AuthError` (fail fast)
  - `CypherSyntaxError` (bug in script)

**Error Types Handled:**
- **Config errors:** FileNotFoundError, JSON parsing, validation
- **TTL parsing:** File not found, permission denied, malformed TTL
- **Neo4j connection:** ServiceUnavailable, AuthError
- **Neo4j operations:** TransientError with retry

---

### 5. Performance Optimizations

#### Batching
- **Import:** 5000 triples per batch (configurable)
- **Deletion:** 1000 nodes per batch
- **Relationships:** UNWIND batching for bulk creation

#### Indexing
- Creates index on `uri` property for all main labels
- CRITICAL for performance (O(1) vs O(n) lookups)
- Waits for index to be online (300s timeout)

#### Pre-caching
- Caches target node labels before creating relationships
- Avoids N+1 query problem
- Example: 1000 relationships = 1 cache query instead of 1000 lookups

#### Progress Tracking
- `tqdm` progress bars for file processing
- Real-time feedback on long operations

---

## Data Flow

### Input: TTL Files
```turtle
# Example: subjects/mathematics/ks1-mathematics-programme-structure.ttl
natcurric:ks1-mathematics-programme a curric:Programme ;
    rdfs:label "KS1 Mathematics Programme" ;
    curric:aims ( "Develop number fluency" "Problem solving" ) .
```

### Stage 1: Loaded into RDF Graph
- Parse with rdflib
- Extract metadata (aims list, slug, etc.)
- Filter ontology declarations

### Stage 2: Import to Neo4j
```cypher
// Initial state (via rdflib-neo4j)
(:Resource {
  uri: "https://w3id.org/uk/oak/curriculum/nationalcurriculum/ks1-mathematics-programme",
  label: "KS1 Mathematics Programme"
})
```

### Stage 3: Transformed
```cypher
// After transformations
(:NatCurric:Programme {
  uri: "https://w3id.org/uk/oak/curriculum/nationalcurriculum/ks1-mathematics-programme",
  programmeTitle: "KS1 Mathematics Programme",  // Renamed
  programmeSlug: "ks1-mathematics-programme",    // Extracted
  aims: ["Develop number fluency", "Problem solving"],  // Multi-valued
  lastUpdated: "2025-01-15"
})
```

---

## CLI Usage

### Basic Export
```bash
python scripts/export_to_neo4j.py --config scripts/export_to_neo4j_config.json
```

### Clear Database First
```bash
python scripts/export_to_neo4j.py --config scripts/export_to_neo4j_config.json --clear
```

### Dry Run (Validation)
```bash
python scripts/export_to_neo4j.py --config scripts/export_to_neo4j_config.json --dry-run
```

### List Files
```bash
python scripts/export_to_neo4j.py --config scripts/export_to_neo4j_config.json --list-files
```

### Verbose Logging
```bash
python scripts/export_to_neo4j.py --config scripts/export_to_neo4j_config.json --verbose
```

---

## Testing Strategy

### Unit Tests (To Be Added)
- `test_rdf_loader.py` - Filtering, extraction methods
- `test_transformations.py` - Each transformation independently
- `test_config.py` - Configuration validation
- `test_retry.py` - Retry logic

### Integration Tests (To Be Added)
- `test_pipeline.py` - Full pipeline with sample data
- `test_error_handling.py` - Error scenarios

### Running Tests
```bash
uv run pytest tests/
```

---

## Configuration for Other RDF Repositories

To adapt this script for another RDF repository:

1. **Update `rdf_source.namespaces`** with your ontology's namespaces
2. **Update `rdf_source.file_discovery`** to point to your TTL files
3. **Adjust `label_mapping`** for your node types
4. **Customize `property_mappings`** for your entity types
5. **Define `inclusion_flattening`** if your ontology uses inclusion patterns
6. **Add `reverse_relationships` or `relationship_type_mappings`** as needed

The script is designed to be reusable across different RDF domains.

---

## Dependencies

**Runtime:**
- `rdflib>=7.5.0` - RDF parsing and manipulation
- `rdflib-neo4j>=0.6.0` - Neo4j store for rdflib
- `neo4j>=5.0.0` - Neo4j Python driver
- `pydantic>=2.0.0` - Configuration validation
- `python-dotenv>=1.0.0` - Environment variable loading
- `tqdm>=4.66.0` - Progress bars

**Development:**
- `pytest>=8.0.0` - Testing framework
- `mypy>=1.8.0` - Static type checking
- `ruff>=0.2.0` - Linting and formatting

---

## Maintenance

### Adding a New Transformation

1. Create a new class extending `Transformation`:

```python
class MyNewTransformation(Transformation):
    def name(self) -> str:
        return "My New Transformation"

    def should_run(self, config: Neo4jExportConfig) -> bool:
        return hasattr(config, 'my_new_config')

    def execute(self, session, config, main_labels, data) -> int:
        # Your transformation logic here
        count = self._execute_count_query(
            session,
            "MATCH (n:MyType) SET n.newProp = 'value' RETURN count(n) as count",
            operation_desc="Set newProp on MyType nodes"
        )
        return count
```

2. Add to pipeline in `apply_transformations()`:

```python
transformations=[
    # ... existing transformations
    MyNewTransformation(),  # Add here
]
```

### Modifying Configuration

Update both:
1. `export_to_neo4j_config.json` - The actual config
2. Pydantic models in script - For validation

---

## Troubleshooting

### Common Issues

**"Neo4j authentication failed"**
- Check `.env` file exists
- Verify `NEO4J_PASSWORD` is correct

**"TTL parsing failed"**
- Check TTL file is valid Turtle format
- Run: `rapper -i turtle file.ttl` to validate

**"Transient error"**
- Script will retry automatically (3 attempts)
- If persists, check Neo4j is running and responsive

**"Index creation timeout"**
- Large datasets may need more time
- Increase `INDEX_AWAIT_TIMEOUT_SECONDS` constant

---

## Performance Tuning

### Batch Sizes
```python
# Adjust in config or constants
DEFAULT_BATCH_SIZE = 5000  # Increase for faster import
DELETE_BATCH_SIZE = 1000   # Increase for faster deletion
```

### Retry Configuration
```python
MAX_RETRIES = 3                  # Number of retry attempts
RETRY_DELAY_SECONDS = 2          # Initial delay
RETRY_BACKOFF_MULTIPLIER = 2     # Exponential backoff
```

### Index Wait Time
```python
INDEX_AWAIT_TIMEOUT_SECONDS = 300  # 5 minutes
```

---

## Code Quality

**Strengths:**
- ✅ Clean architecture (Strategy pattern, SRP)
- ✅ Type-safe (modern type hints, Pydantic)
- ✅ Well-documented (docstrings, comments)
- ✅ Error handling with retry logic
- ✅ Performance optimized (batching, indexing, caching)
- ✅ Testable design (extracted functions)

**Areas for Improvement:**
- ⚠️ Add comprehensive test suite
- ⚠️ Run mypy --strict for full type checking

---

## Version History

**v0.1.0** (Current)
- Initial refactored version
- Modern Python 3.11+ type hints
- Strategy pattern for transformations
- Comprehensive error handling
- CLI flags (--dry-run, --verbose, --list-files)
- Progress bars
- Retry logic with exponential backoff

---

## License

This script is part of the Oak Curriculum Ontology project.
License: MIT
