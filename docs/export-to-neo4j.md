# Exporting Oak Curriculum Ontology to Neo4j AuraDB

This guide explains how to export Oak Curriculum Ontology TTL files to Neo4j AuraDB using **rdflib-neo4j**.

## Why rdflib-neo4j?

- ✅ Works with AuraDB (cloud-hosted Neo4j)
- ✅ Client-side RDF import (no server plugin needed)
- ✅ Compatible with validated TTL files
- ✅ Supports namespace mapping and custom prefixes

## Prerequisites

### 1. Neo4j AuraDB Instance

- Create an AuraDB account at https://console.neo4j.io/
- Create an AuraDB Professional instance (Free tier works too)
- Note your connection URI: `neo4j+s://xxxxx.databases.neo4j.io`

### 2. Python Environment

```bash
# Install dependencies
uv pip install rdflib-neo4j neo4j==5.15.0 python-dotenv

# Or using pip
pip install rdflib-neo4j neo4j==5.15.0 python-dotenv
```

**Important**: Use neo4j driver version **5.15.0** (not 5.28+) due to compatibility issues with AuraDB.

### 3. Environment Configuration

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env` with your AuraDB credentials:

```env
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-auradb-password
NEO4J_DATABASE=neo4j
```

---

## Export Process

### Run the Export Script

```bash
# Using project virtual environment
.venv/bin/python scripts/export_to_neo4j.py

# Clear database first, then export (fresh start)
.venv/bin/python scripts/export_to_neo4j.py --clear
```

### Command Line Options

- **No flags**: Append to existing data (incremental)
- **`--clear`**: Delete all nodes before importing (fresh start)

### What Gets Exported

The script automatically discovers and exports **data files only** (not ontology definitions):

**Top-level data files:**
- `data/oak-curriculum/programme-structure.ttl` - Exam boards, tiers
- `data/oak-curriculum/threads.ttl` - Cross-cutting curriculum threads

**Programme files:**
- All `*.ttl` files in `data/oak-curriculum/programmes/**/` (auto-discovered)

**Excluded:**
- ❌ `ontology/oak-curriculum-ontology.ttl` - Schema definitions (not needed in graph)
- ❌ `ontology/oak-curriculum-constraints.ttl` - SHACL validation rules
- ❌ Files in `versions/` directories - Historical versions

### Expected Output

```
============================================================
Oak Curriculum Ontology → Neo4j AuraDB Export
============================================================
Target: neo4j+s://xxxxx.databases.neo4j.io
Database: neo4j
------------------------------------------------------------
Connecting to AuraDB...
✓ Connected to AuraDB!
Found 5 TTL files to export:
  - data/oak-curriculum/programme-structure.ttl
  - data/oak-curriculum/threads.ttl
  - data/oak-curriculum/programmes/english/english-key-stage-2.ttl
  - data/oak-curriculum/programmes/science/science-key-stage-3.ttl
  - data/oak-curriculum/programmes/science/combined-science-key-stage-4.ttl

============================================================

Exporting: programme-structure.ttl
----------------------------------------
✓ Added 39 triples (39 total)

Exporting: threads.ttl
----------------------------------------
✓ Added 24 triples (63 total)

[... more files ...]

Exporting: english-key-stage-2.ttl
----------------------------------------
✓ Added 143 triples (550 total)

============================================================
Committing to AuraDB...
✓ Successfully exported 550 triples to Neo4j!

============================================================
Post-processing: Replacing Resource labels with Oak labels...
✓ Relabeled 121 Oak nodes (Resource → Oak)
  Note: 24 nodes kept Resource label (external URIs)

============================================================
Extracting URI slugs as properties...
✓ Tier: Extracted slug to 'tierSlug' (2 nodes)
✓ ExamBoard: Extracted slug to 'boardSlug' (3 nodes)
✓ Programme: Extracted slug to 'programmeSlug' (8 nodes)
✓ Total slugs extracted: 59

============================================================
Applying custom property mappings...
✓ Tier: 'label' → 'tierTitle' (2 nodes)
✓ Tier: 'comment' → 'tierDescription' (2 nodes)
✓ ExamBoard: 'comment' → 'boardDescription' (3 nodes)
✓ Total properties renamed: 7

============================================================
Verifying export...
✓ Total nodes in AuraDB: 202

Oak entity types:
  Lesson: 23
  LessonInclusion: 27
  UnitVariantInclusion: 18
  UnitVariant: 13
  Programme: 8
  Unit: 8

============================================================
✅ EXPORT COMPLETE!
```

---

## Understanding the Data Model

### RDF → Neo4j Mapping

**rdflib-neo4j** converts RDF to Neo4j as follows:

| RDF Concept | Neo4j Representation |
|-------------|---------------------|
| RDF Resources (subjects) | Nodes with label `:Oak` (Oak data) or `:Resource` (external) |
| RDF Types (`rdf:type`) | Additional node labels |
| RDF Object Properties | Relationships |
| RDF Datatype Properties | Node properties |
| Namespaced predicates | Prefixed relationship/property names |

### Configurable Label Replacement

The script replaces the generic `:Resource` label from rdflib-neo4j with a **configurable custom label** based on URI patterns. This is defined in the configuration file.

**Default for Oak data**: Nodes with URIs starting with `https://w3id.org/uk/curriculum/oak` get the `:Oak` label.

**Benefits:**
- **Identifies data provenance**: Clearly marks the data source
- **Enables multi-source graphs**: Distinguish Oak data from DfE curriculum or other sources
- **Simplifies queries**: `MATCH (p:Programme:Oak)` instead of generic `:Resource`
- **Follows Neo4j best practices**: Meaningful labels for categorization
- **Reusable script**: Change the config to use for other data sources (`:DfE`, `:Custom`, etc.)

### URI Slug Extraction

The script can **extract the local name from URIs** and store it as a property. This is useful for creating human-readable identifiers.

**Example**: For a Tier with URI `https://w3id.org/uk/curriculum/oak-data/tier-higher`, the script extracts `tier-higher` and stores it as `tierSlug`.

**Configuration:**
```json
{
  "uri_slug_extraction": {
    "Tier": "tierSlug",
    "Programme": "programmeSlug"
  }
}
```

**Result in Neo4j:**
```cypher
(:Tier {
  uri: "https://w3id.org/uk/curriculum/oak-data/tier-higher",
  tierSlug: "tier-higher"  ← Extracted from URI
})
```

### Custom Property Mappings

The script supports **custom property name mappings** via a configuration file. This allows you to rename RDF properties to more meaningful Neo4j property names for specific node types.

**Example**: Map `rdfs:comment` to `tierDescription` for Tier nodes instead of the generic `comment`.

#### Configuration File

`scripts/neo4j_property_mappings.json`:
```json
{
  "label_mapping": {
    "source_label": "Resource",
    "target_label": "Oak",
    "uri_pattern": "https://w3id.org/uk/curriculum/oak",
    "description": "Replaces source_label with target_label for nodes matching uri_pattern"
  },

  "property_mappings": {
    "Tier": {
      "comment": "tierTitle"
    },
    "ExamBoard": {
      "comment": "boardDescription"
    },
    "Programme": {
      "comment": "programmeDescription"
    }
  }
}
```

#### Label Mapping Configuration

The `label_mapping` section controls how nodes are relabeled:

| Field | Description | Example |
|-------|-------------|---------|
| `source_label` | Label to replace (from rdflib-neo4j) | `"Resource"` |
| `target_label` | New label to apply | `"Oak"`, `"DfE"`, `"Custom"` |
| `uri_pattern` | URI prefix to match nodes | `"https://w3id.org/uk/curriculum/oak"` |

**Example for DfE data:**
```json
{
  "label_mapping": {
    "source_label": "Resource",
    "target_label": "DfE",
    "uri_pattern": "https://w3id.org/uk/curriculum/core"
  }
}
```

#### How It Works

1. **Per-type mappings**: Different node types can have different property names
2. **Safe renaming**: Only renames properties that exist on nodes
3. **Oak-only**: Only applies to nodes with `:Oak` label
4. **Preserves data**: Copies value to new property, removes old property

#### Example Result

**Before mapping:**
```
(:Tier {uri: "...", label: "Foundation", comment: "Foundation level..."})
```

**After mapping:**
```
(:Tier {uri: "...", label: "Foundation", tierTitle: "Foundation level..."})
```

#### Adding New Mappings

Edit `scripts/neo4j_property_mappings.json`:

```json
{
  "property_mappings": {
    "YourNodeType": {
      "old_property_name": "new_property_name",
      "another_old": "another_new"
    }
  }
}
```

Then run the export script - mappings are applied automatically during import.

### Namespace Prefixes

The export uses these custom prefixes:

- `oakcurric:` → `ns0__` (Oak ontology)
- `oak:` → `ns1__` (Oak data)
- `curric:` → `ns2__` (Core curriculum)
- `eng:` → `ns3__` (England curriculum)
- `rdfs:` → `ns4__`
- `rdf:` → `ns5__`
- `owl:` → `ns6__`

Example:
- TTL: `oakcurric:hasYearGroup`
- Neo4j: `:ns0__hasYearGroup` (relationship type)

---

## Configuration Files

### Neo4j Post-Processing Configuration

**Location**: `scripts/neo4j_property_mappings.json`

**Purpose**: Configure label replacement and property name mappings for imported RDF data.

**Full Format**:
```json
{
  "label_mapping": {
    "source_label": "Resource",
    "target_label": "Oak",
    "uri_pattern": "https://w3id.org/uk/curriculum/oak"
  },

  "property_mappings": {
    "NodeLabel": {
      "source_property": "target_property"
    }
  }
}
```

**Processing Order**:
1. Import TTL files to Neo4j (nodes get `:Resource` label)
2. **Label replacement**: Replace `:Resource` with custom label based on URI pattern
3. **URI slug extraction**: Extract local names from URIs as properties
4. **Property mappings**: Rename properties for specific node types

**Notes**:
- Label mapping: Applies to nodes matching `uri_pattern`
- Property mappings: Only affects nodes with the `target_label` from label mapping
- Properties are renamed (copied then deleted)
- If config file is missing, post-processing steps are skipped

**Reusability**:
This script can be reused for different data sources by changing the config:
- Oak data → `:Oak` label
- DfE curriculum data → `:DfE` label
- Custom sources → `:YourLabel` label

### Environment Configuration

**Location**: `.env` (project root)

**Required variables**:
```env
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
```

---

## Troubleshooting

### Connection Failed: "Unable to retrieve routing information"

**Cause**: Neo4j driver version incompatibility.

**Fix**:
```bash
uv pip install neo4j==5.15.0
```

Version 5.28+ has known issues with AuraDB routing.

### "Authentication failed"

**Cause**: Wrong password.

**Fix**:
1. Reset password in AuraDB Console
2. Update `.env` file
3. Run export again

### "Instance not running"

**Cause**: AuraDB instance is paused.

**Fix**:
1. Go to https://console.neo4j.io/
2. Click "Resume" on your instance
3. Wait 30 seconds for it to start
4. Run export again

### Export completes but 0 triples loaded

**Cause**: TTL files not found or empty.

**Fix**:
- Check files exist in `data/oak-curriculum/` and `ontology/`
- Verify TTL files are not empty
- Check script output for "Skipping missing file" warnings

---

## Re-exporting

To re-export fresh data, use the `--clear` flag:

```bash
.venv/bin/python scripts/export_to_neo4j.py --clear
```

This will:
1. Delete all existing nodes and relationships
2. Import fresh data from TTL files

**Alternative**: Manually clear in Neo4j Browser:
```cypher
MATCH (n) DETACH DELETE n
```

---

## Quick Reference

### Key Features

| Feature | Description |
|---------|-------------|
| **Auto-discovery** | Finds all TTL files in `data/oak-curriculum/` |
| **Oak labels** | Replaces `:Resource` with `:Oak` for provenance |
| **Property mappings** | Rename properties per node type via config |
| **--clear flag** | Option to clear database before import |
| **Verification** | Shows entity counts and samples |

### Important Files

| File | Purpose |
|------|---------|
| `scripts/export_to_neo4j.py` | Main export script |
| `scripts/neo4j_property_mappings.json` | Property name mappings |
| `.env` | Neo4j connection credentials |
| `docs/export-to-neo4j.md` | This documentation |

### Common Queries

**Count nodes by type:**
```cypher
MATCH (n:Oak)
RETURN labels(n) as types, count(*) as count
ORDER BY count DESC
```

**Find all programmes:**
```cypher
MATCH (p:Programme:Oak)
RETURN p.label, p.isExamined, p.examType
ORDER BY p.label
```

**Check property mappings worked:**
```cypher
MATCH (t:Tier:Oak)
RETURN t.tierTitle, keys(t)
```

**Explore relationships:**
```cypher
MATCH (p:Programme:Oak)-[r]->(n)
RETURN type(r) as relationship, labels(n) as target, count(*) as count
ORDER BY count DESC
```

---

## Resources

- **rdflib-neo4j Documentation**: https://neo4j.com/labs/rdflib-neo4j/
- **rdflib-neo4j GitHub**: https://github.com/neo4j-labs/rdflib-neo4j
- **Neo4j Cypher Manual**: https://neo4j.com/docs/cypher-manual/current/
- **Neo4j Aura Console**: https://console.neo4j.io/
