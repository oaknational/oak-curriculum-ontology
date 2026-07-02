# Oak Curriculum Ontology

<!-- Version and Status Badges -->
![Version](https://img.shields.io/badge/version-0.1.3-orange)
![Status](https://img.shields.io/badge/status-early_release-yellow)
![License: MIT + OGL-3.0](https://img.shields.io/badge/License-MIT%20%2B%20OGL--UK--3.0-lightgrey.svg)
![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![GitHub last commit](https://img.shields.io/github/last-commit/oaknational/oak-curriculum-ontology)

<!-- Build and Quality Badges -->
[![Validate Ontology](https://github.com/oaknational/oak-curriculum-ontology/workflows/Validate%20Ontology/badge.svg)](https://github.com/oaknational/oak-curriculum-ontology/actions/workflows/validate-ontology.yml)
[![Generate Documentation](https://github.com/oaknational/oak-curriculum-ontology/workflows/Generate%20GH%20Pages%20with%20Widoco/badge.svg)](https://github.com/oaknational/oak-curriculum-ontology/actions/workflows/generate-docs-widoco.yml)
[![Generate Distributions](https://github.com/oaknational/oak-curriculum-ontology/workflows/Generate%20Static%20Distribution%20Files/badge.svg)](https://github.com/oaknational/oak-curriculum-ontology/actions/workflows/generate-distributions.yml)

<!-- Standards Badges -->
[![W3C RDF](https://img.shields.io/badge/W3C-RDF%201.1-005A9C)](https://www.w3.org/TR/rdf11-primer/)
[![W3C OWL](https://img.shields.io/badge/W3C-OWL%202-005A9C)](https://www.w3.org/TR/owl2-overview/)
[![W3C SKOS](https://img.shields.io/badge/W3C-SKOS-005A9C)](https://www.w3.org/TR/skos-reference/)
[![W3C SHACL](https://img.shields.io/badge/W3C-SHACL-005A9C)](https://www.w3.org/TR/shacl/)

> **A formal semantic representation of the Oak National Academy Curriculum and its alignment to the National Curriculum for England (2014).**

Machine-readable curriculum data in W3C-standard formats (RDF, OWL, SKOS, SHACL) enabling interoperability, semantic queries, and data-driven educational tools — including grounded curriculum knowledge for AI systems. This repository is an Oak-developed representation and does not constitute an official DfE National Curriculum publication.

This repository contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

📘 **[Browse Full Documentation](https://oaknational.github.io/oak-curriculum-ontology/)** |
🔍 **[View Ontology](ontology/oak-curriculum-ontology.ttl)** |
📊 **[Download Distributions](https://github.com/oaknational/oak-curriculum-ontology/releases)**

Developed by [Oak National Academy](https://thenational.academy)

---

## Table of Contents

- [⚠️ Early Release Notice](#️-early-release-notice)
- [What Is This?](#what-is-this)
- [Quick Start](#quick-start)
- [Grounding AI in the Curriculum](#grounding-ai-in-the-curriculum)
- [Supporting the Curriculum Transition](#supporting-the-curriculum-transition)
- [Key Features](#key-features)
- [Core Concepts](#core-concepts)
- [Use Cases](#use-cases)
- [Getting Started](#getting-started)
- [SPARQL Examples](#sparql-examples)
- [File Structure](#file-structure)
- [Standards Compliance](#standards-compliance)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)
- [Citation](#citation)
- [Roadmap](#roadmap)

---

## ⚠️ Early Release Notice

This is version 0.1 - an early public release for evaluation and community feedback.
The ontology structure, URIs, and data are under active development and **subject to change**.

- ✅ Core ontology structure is stable
- 🚧 Subject coverage is being expanded
- 🔄 Data validation and refinement ongoing
- 📝 Feedback and suggestions are welcome!

> **Data Notice:** All National Curriculum data in this repository models the **National Curriculum for England (2014)** — the statutory curriculum until the revised National Curriculum (expected to be published in 2027 and first taught from 2028) takes effect. As the 2014 curriculum was not designed as structured data, mappings may be incomplete. For educational purposes, use [official sources](https://www.gov.uk/government/collections/national-curriculum). See [Supporting the Curriculum Transition](#supporting-the-curriculum-transition).

**We welcome:**

- 🐛 Bug reports (structure, data, documentation)
- 💡 Feature requests and suggestions
- ❓ Questions and feedback (see [CONTRIBUTING.md](CONTRIBUTING.md))

---

## What Is This?

The Oak Curriculum Ontology provides:

**Curriculum Structure** - Formal definitions of programmes, units, lessons, and their relationships

**Knowledge Taxonomy** - Hierarchical subject taxonomies for Art and Design, Citizenship, Computing, Design and Technology, English, Geography, History, Languages, Mathematics, Music, Physical Education, and The Sciences aligned to National Curriculum (2014)

**Teaching Knowledge** - Lesson-level data that bakes in learning science and Oak's curriculum principles: misconceptions with corrections, prior knowledge requirements, key learning points, pupil outcomes, and cross-curricular threads (see [Grounding AI in the Curriculum](#grounding-ai-in-the-curriculum))

**Validation Rules** - SHACL constraints ensuring data quality and completeness

**Interoperable Data** - W3C-standard RDF enabling integration with any semantic web tool or platform

This ontology bridges official curriculum requirements (National Curriculum 2014) with practical teaching programmes, making curriculum data queryable, analyzable, and machine-processable.

In this version, our knowledge taxonomy is being applied to the knowledge specified in the National Curriculum for England (2014). The data in this repository represents our best efforts to apply a consistent structure where this does not exist in the source content. The taxonomy takes inspiration from a variety of open curriculum sources (see [Acknowledgments](#acknowledgments) below).

---

## Quick Start

```turtle
@prefix curric: <https://w3id.org/uk/oak/curriculum/ontology/> .
@prefix natcurric: <https://w3id.org/uk/oak/curriculum/nationalcurriculum/> .
@prefix oakcurric: <https://w3id.org/uk/oak/curriculum/oakcurriculum/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

# A Year 7 Mathematics programme, as published in this repository
oakcurric:programme-mathematics-year-group-7
  a curric:Programme ;
  rdfs:label "Mathematics Year Group 7"@en ;
  curric:isProgrammeOf natcurric:scheme-mathematics-key-stage-3 ;
  curric:coversYearGroup natcurric:year-group-7 ;
  curric:hasUnitVariantInclusion oakcurric:inclusion-programme-mathematics-year-group-7-pos-1 .
```

**Namespace URIs:**

- `https://w3id.org/uk/oak/curriculum/ontology/` - Ontology classes and properties
- `https://w3id.org/uk/oak/curriculum/nationalcurriculum/` - National Curriculum (2014) data
- `https://w3id.org/uk/oak/curriculum/oakcurriculum/` - Oak curriculum programmes

---

## Grounding AI in the Curriculum

AI tools that plan lessons, tutor pupils, or generate teaching materials need curriculum knowledge that is structured, validated, and citable — not scraped. This repository is that grounding layer: every entity has a persistent URI, every relationship is typed, and every release is SHACL-validated in CI.

The National Curriculum (2014) mapping provides the structural baseline. On top of it sits Oak's **teaching knowledge** — lesson-level data informed by learning science and Oak's curriculum principles:

| Asset | Instances | What it gives an AI system |
| ----- | --------: | -------------------------- |
| Misconceptions | 11,207 | Common pupil errors with paired corrections, attached to each lesson — diagnosis and remediation |
| Prior knowledge requirements | 7,432 | What each unit assumes pupils already know — readiness checks and adaptive sequencing |
| Key learning points | 50,948 | Granular learning objectives for content alignment and evaluation |
| Pupil lesson outcomes | 12,517 | What a pupil should be able to do after each lesson |
| Keywords | 13,012 | Subject vocabulary attached to each lesson |
| Threads | 160 | Cross-unit conceptual progressions linking 1,530 units across year groups |
| Lesson sequencing | 15,257 | Explicit teaching-order positions from programme to unit to lesson |

For example, the misconceptions an AI tutor should anticipate when teaching negative numbers:

```sparql
PREFIX curric: <https://w3id.org/uk/oak/curriculum/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?lessonLabel ?statement ?correction WHERE {
  ?lesson a curric:Lesson ;
          rdfs:label ?lessonLabel ;
          curric:hasMisconception ?misconception .
  ?misconception curric:statement ?statement ;
                 curric:correction ?correction .
  FILTER(CONTAINS(LCASE(STR(?lessonLabel)), "negative number"))
}
ORDER BY ?lessonLabel
```

This returns pairs such as the misconception *"That addition will always make the result bigger"* alongside the correction teachers use to address it.

### How AI systems consume this data

1. **Oak Curriculum MCP server** — Oak is piloting a Model Context Protocol server exposing this curriculum as live tools for AI agents and assistants (curriculum search, lesson summaries, quizzes, misconception and prior-knowledge graphs), built on [Oak's Open API](https://open-api.thenational.academy/docs). This ontology is the formal model of the same curriculum; making it the canonical substrate of the MCP server is on the [roadmap](#roadmap).
2. **AI-ready distributions** — each [release](https://github.com/oaknational/oak-curriculum-ontology/releases) ships a SQLite database (`oak-curriculum.sqlite`) and property-graph JSONL files (`nodes.jsonl`, `relationships.jsonl`) alongside the RDF formats, so agent tools and RAG pipelines can consume the graph without an RDF stack. See [property-graph-format.md](docs/property-graph-format.md).
3. **Neo4j export** — `scripts/export_to_neo4j.py` loads the full graph into Neo4j for traversal and GraphRAG.
4. **SPARQL** — query the merged Turtle locally today; a public SPARQL endpoint is on the [roadmap](#roadmap).

---

## Supporting the Curriculum Transition

England's National Curriculum is being revised: the new curriculum is expected to be published in 2027 and first taught from 2028. This repository is deliberately structured to support — and make visible — that transition:

- **Clear version labelling** — every National Curriculum entity in this repository models the 2014 curriculum, and is labelled as such. Nothing here describes the revised curriculum yet.
- **A version-agnostic model** — the ontology (Scheme, Strand, ContentDescriptor, etc.) encodes no 2014 assumptions, and the `nationalcurriculum` namespace is deliberately not year-pinned. Whether the revised curriculum fits the same structure won't be known until it is published — where it differs, we will model and map the differences rather than force a fit.
- **Transition mapping** — publishing both curricula in one graph will allow explicit relationships between 2014 and revised content (what moved, what changed, what is new), so schools and edtech tools can plan the transition rather than diff documents by hand.

During the transition years, teachers and tools will need to work with both curricula at once. A single queryable graph holding both, with mappings between them, is the infrastructure that makes that practical.

---

## Key Features

✅ **31 ontology classes** defining curriculum structure (Programme, Unit, Lesson, Discipline, Strand, etc).  
✅ **38 SHACL validation shapes** ensuring data integrity.  
✅ **12 subject areas** with full knowledge taxonomies.
✅ **Teaching knowledge** — 11,207 misconceptions, 7,432 prior knowledge requirements, 50,948 key learning points, and 160 cross-curricular threads.  
✅ **National Curriculum alignment** linking Oak content to statutory requirements.  
✅ **Automated validation** via GitHub Actions CI/CD.  
✅ **Multi-format distributions** (Turtle, JSON-LD, RDF/XML, N-Triples, SQLite, property-graph JSONL).  
✅ **Standards-compliant** (RDF 1.1, OWL 2, SKOS, SHACL, Dublin Core).  
✅ **Open data** (OGL 3.0 license for ontology/data, MIT for code).  

---

## Core Concepts

### Temporal Hierarchy

How curriculum is organized by age and phase:

```text
Phase (Primary, Secondary)
  └─ Key Stage (KS1, KS2, KS3, KS4)
      └─ Year Group (Year 1-11)
```

### Knowledge Taxonomy

How subject content is organized hierarchically (SKOS):

```text
Discipline (e.g., Science)
  └─ Strand (e.g., "Structure and function of living organisms")
      └─ SubStrand (e.g., "Cells and organisation")
          └─ ContentDescriptor (e.g., "Cells as fundamental unit")
```

**Current subject coverage:**

- **Art and Design** - Programme structure and knowledge taxonomy
- **Citizenship** - Programme structure and knowledge taxonomy
- **Computing** - Programme structure and knowledge taxonomy
- **Design and Technology** - Programme structure and knowledge taxonomy (including Food and Nutrition)
- **English** - Programme structure and knowledge taxonomy
- **Geography** - Programme structure and knowledge taxonomy
- **History** - Programme structure and knowledge taxonomy
- **Languages** - Programme structure and knowledge taxonomy (French, German, Spanish)
- **Mathematics** - Programme structure and knowledge taxonomy
- **Music** - Programme structure and knowledge taxonomy
- **Physical Education** - Programme structure and knowledge taxonomy
- **The Sciences** - A unified subject covering Science (KS1–KS3) and separate Biology, Chemistry, Physics, and Combined Science programmes at KS4, with a single consolidated knowledge taxonomy

### Programme Structure

How subjects are organized into teaching programmes:

```text
Subject (e.g., Mathematics)
  └─ Programme (e.g., Mathematics Year 7)
      └─ Unit (coherent topic, e.g., "Fractions")
          └─ Unit Variant (exam board variations)
              └─ Lesson (individual teaching session)
```

### Key Classes

**Programme**: A structured sequence of units for a specific year group, and optionally for a specific exam board and tier. For example, "English Year 3" or "Biology Year 10 (AQA Foundation)".

**Unit**: A coherent body of knowledge and skills, such as "'Marcy and the Riddle of the Sphinx': book club". Units can have multiple unit variants for different exam boards or pedagogical approaches.

**UnitVariant**: A specific version of a unit, potentially adapted for different exam boards, tiers, or teaching contexts. Unit variants contain the ordered sequence of lessons.

**Lesson**: A single teaching session with learning activities, resources, and formative assessment.

**Thread**: A conceptual thread that weaves through multiple units, representing recurring themes or skills (e.g., "Systems Thinking", "Scale and Magnitude").

**Misconception**: A common pupil error attached to a lesson, expressed as a paired statement and correction — what pupils typically get wrong and how teachers address it.

**PriorKnowledgeRequirement**: The prerequisite knowledge a unit assumes, enabling readiness checks and adaptive sequencing.

**KeyLearningPoint**, **PupilLessonOutcome**, **Keyword**: Lesson-level learning objectives, intended pupil outcomes, and subject vocabulary.

**ExamBoard**: An awarding organization (AQA, Edexcel, OCR) that creates and assesses qualifications.

**Tier**: A level of difficulty within tiered qualifications (Foundation or Higher).

### Sequencing and Optionality

**UnitVariantInclusion**: Links a programme to a unit variant at a specific sequence position. Can include choice points where teachers select from multiple unit variant options.

**LessonInclusion**: Links a unit variant to a lesson at a specific sequence position within the unit variant.

**UnitVariantChoice**: Groups multiple unit variant options at a choice point, with configurable min/max selection constraints.

![Unit Variant Sequencing and Optionality (i) Simple Programme link](docs/images/optionality-1.png)
![Unit Variant Sequencing and Optionality (ii) Programme with Optional Unit Variants link](docs/images/optionality-2.png)
![Lesson Sequencing link](docs/images/sequencing.png)

### National Curriculum Integration

Oak units reference National Curriculum content via:

- `curric:isProgrammeOf` - Links a programme to a National Curriculum scheme
- `curric:isUnitOf` - Links a unit to a National Curriculum scheme
- `curric:includesContent` - Links a unit to specific National Curriculum content descriptors

![How the Oak Curriculum Ontology and the National Curriculum Ontology link](docs/images/model.png)

---

## Use Cases

**AI Assistants & Tutors** - Ground lesson planning, tutoring, and assessment tools in validated curriculum knowledge.  
**RAG & Knowledge Graphs** - Load AI-ready distributions into retrieval pipelines and graph databases.  
**Educational Platforms** - Load curriculum data into learning management systems.  
**Curriculum Analysis** - Query relationships between subjects, key stages, and topics.  
**Research** - Analyze curriculum structure, progression, and coverage.  
**Data Integration** - Link to other educational datasets via persistent URIs.  
**Quality Assurance** - Validate custom curriculum data against standard shapes.  
**Graph Databases** - Export to Neo4j for network analysis and visualization.  
**Semantic Search** - Enable intelligent discovery of curriculum content.  

---

## Getting Started

### Option 1: Download Distribution Files

Pre-generated RDF files in multiple formats available from [GitHub Releases](https://github.com/oaknational/oak-curriculum-ontology/releases):

```bash
# Download Turtle (compact, human-readable)
curl -L -O https://github.com/oaknational/oak-curriculum-ontology/releases/latest/download/oak-curriculum-full.ttl

# Download JSON-LD (for web apps)
curl -L -O https://github.com/oaknational/oak-curriculum-ontology/releases/latest/download/oak-curriculum-full.jsonld

# Download RDF/XML (for legacy tools)
curl -L -O https://github.com/oaknational/oak-curriculum-ontology/releases/latest/download/oak-curriculum-full.rdf

# Download N-Triples (for streaming/line-based processing)
curl -L -O https://github.com/oaknational/oak-curriculum-ontology/releases/latest/download/oak-curriculum-full.nt

# Download SQLite database (for direct programmatic and AI use, no RDF stack needed)
curl -L -O https://github.com/oaknational/oak-curriculum-ontology/releases/latest/download/oak-curriculum.sqlite

# Download property-graph JSONL (nodes and relationships, for graph databases and agent tooling)
curl -L -O https://github.com/oaknational/oak-curriculum-ontology/releases/latest/download/nodes.jsonl
curl -L -O https://github.com/oaknational/oak-curriculum-ontology/releases/latest/download/relationships.jsonl
```

**Available formats:**

- `.ttl` (Turtle) - Compact, human-readable
- `.jsonld` (JSON-LD) - JSON-based RDF for web apps
- `.rdf` (RDF/XML) - XML-based RDF for legacy tools
- `.nt` (N-Triples) - Line-based format for streaming
- `.sqlite` (SQLite) - Relational database for direct programmatic and AI use
- `.jsonl` (Property graph) - `nodes.jsonl` and `relationships.jsonl`, see [property-graph-format.md](docs/property-graph-format.md)

### Option 2: Load into Triple Store

```bash
# Example with Apache Jena TDB2
tdb2.tdbloader --loc=/path/to/database \
  ontology/oak-curriculum-ontology.ttl \
  data/**/*.ttl

# Example with GraphDB
graphdb-import -c /path/to/repo-config.ttl ontology/*.ttl data/**/*.ttl
```

### Option 3: Validate Data

```bash
# Run local validation (matches CI/CD exactly)
./scripts/validate.sh
```

This validates all TTL files against SHACL constraints with RDFS inference.

### Option 4: Export to Neo4j

```bash
# Export to Neo4j graph database with transformations
python scripts/export_to_neo4j.py --config scripts/export_to_neo4j_config.json

# Clear database first, then export fresh
python scripts/export_to_neo4j.py --config scripts/export_to_neo4j_config.json --clear
```

See [scripts/README.md](scripts/README.md) for detailed tool documentation.

---

## SPARQL Examples

### Find all Year 7 programmes

```sparql
PREFIX curric: <https://w3id.org/uk/oak/curriculum/ontology/>
PREFIX natcurric: <https://w3id.org/uk/oak/curriculum/nationalcurriculum/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?programme ?label WHERE {
  ?programme a curric:Programme ;
             curric:coversYearGroup natcurric:year-group-7 ;
             rdfs:label ?label .
}
ORDER BY ?label
```

### Find Mathematics content descriptors

```sparql
PREFIX curric: <https://w3id.org/uk/oak/curriculum/ontology/>
PREFIX natcurric: <https://w3id.org/uk/oak/curriculum/nationalcurriculum/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?descriptor ?label WHERE {
  natcurric:discipline-mathematics skos:narrower+ ?descriptor .
  ?descriptor a curric:ContentDescriptor ;
              skos:prefLabel ?label .
}
ORDER BY ?label
```

### List units in sequence for a programme

```sparql
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
```

### Find programmes by subject

```sparql
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
```

### Find all content in The Sciences taxonomy

```sparql
PREFIX curric: <https://w3id.org/uk/oak/curriculum/ontology/>
PREFIX natcurric: <https://w3id.org/uk/oak/curriculum/nationalcurriculum/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT DISTINCT ?content ?label WHERE {
  natcurric:discipline-the-sciences skos:narrower+ ?content .
  ?content skos:prefLabel ?label .
}
ORDER BY ?label
```

---

## File Structure

```text
oak-curriculum-ontology/
├── ontology/
│   ├── oak-curriculum-ontology.ttl       # Core classes & properties (31 classes)
│   └── oak-curriculum-constraints.ttl    # SHACL validation shapes (38 shapes)
│
├── data/
│   ├── temporal-structure.ttl            # Phases, Key Stages, Year Groups
│   ├── programme-structure.ttl           # Exam Boards, Tiers
│   ├── threads.ttl                       # Cross-cutting Threads
│   └── subjects/
│       ├── citizenship/
│       │   ├── citizenship-programme-structure.ttl     # Subject, Schemes, Progressions
│       │   ├── citizenship-knowledge-taxonomy.ttl      # Strands, Sub-Strands, Content Descriptors
│       │   └── citizenship-key-stage-*.ttl             # KS1-KS4 Programmes, Units, Unit Variants, Lessons
│       ├── english/
│       │   ├── english-programme-structure.ttl
│       │   ├── english-knowledge-taxonomy.ttl
│       │   └── english-key-stage-*.ttl
│       ├── geography/
│       │   ├── geography-programme-structure.ttl
│       │   ├── geography-knowledge-taxonomy.ttl
│       │   └── geography-key-stage-*.ttl
│       ├── history/
│       │   ├── history-programme-structure.ttl
│       │   ├── history-knowledge-taxonomy.ttl
│       │   └── history-key-stage-*.ttl
│       ├── art-and-design/
│       │   ├── art-and-design-programme-structure.ttl
│       │   ├── art-and-design-knowledge-taxonomy.ttl
│       │   └── art-and-design-key-stage-*.ttl
│       ├── computing/
│       │   ├── computing-programme-structure.ttl
│       │   ├── computing-knowledge-taxonomy.ttl
│       │   └── computing-key-stage-*.ttl
│       ├── design-and-technology/
│       │   ├── design-and-technology-programme-structure.ttl
│       │   ├── design-and-technology-knowledge-taxonomy.ttl
│       │   ├── design-and-technology-key-stage-*.ttl
│       │   └── cooking-nutrition-key-stage-*.ttl
│       ├── languages/
│       │   ├── languages-programme-structure.ttl
│       │   ├── languages-knowledge-taxonomy.ttl
│       │   └── french/german/spanish-key-stage-*.ttl
│       ├── mathematics/
│       │   ├── mathematics-programme-structure.ttl
│       │   ├── mathematics-knowledge-taxonomy.ttl
│       │   └── mathematics-key-stage-*.ttl
│       ├── music/
│       │   ├── music-programme-structure.ttl
│       │   ├── music-knowledge-taxonomy.ttl
│       │   └── music-key-stage-*.ttl
│       ├── physical-education/
│       │   ├── physical-education-programme-structure.ttl
│       │   ├── physical-education-knowledge-taxonomy.ttl
│       │   └── physical-education-key-stage-*.ttl
│       └── the-sciences/
│           ├── the-sciences-programme-structure.ttl
│           ├── the-sciences-knowledge-taxonomy.ttl
│           ├── science-key-stage-*.ttl
│           ├── biology-key-stage-4.ttl
│           ├── chemistry-key-stage-4.ttl
│           ├── combined-science-key-stage-4.ttl
│           └── physics-key-stage-4.ttl
│
├── docs/
│   ├── property-graph-format.md          # Property graph (Neo4j) format documentation
│   └── standards-compliance.md           # W3C standards documentation
│
├── scripts/
│   ├── build_static_data.sh              # Generate distribution files (for releases)
│   ├── check_readme_examples.py          # Check README examples and counts against the data
│   ├── export_to_neo4j_ARCHITECTURE.md   # Neo4j export architecture documentation
│   ├── export_to_neo4j_config.json       # Neo4j export configuration
│   ├── export_to_neo4j.py                # Export to Neo4j with transformations
│   ├── merge_ttls_with_imports.py        # Merge TTL files with import resolution
│   ├── README.md                         # Scripts documentation
│   ├── test_sparql_queries.py            # Testing for valid SPARQL queries
│   └── validate.sh                       # Local SHACL validation
│
├── .github/workflows/
│   ├── generate-distributions.yml        # Build distribution files
│   ├── generate-docs-widoco.yml          # Auto-generate documentation
│   ├── README.md                         # Workflows documentation
│   └── validate-ontology.yml             # Automated SHACL validation
│
├── .env.example                          # Example environment configuration for Neo4j
├── CITATION.cff                          # Citation metadata
├── CODE-LICENSE.md                       # MIT License (for code)
├── CONTRIBUTING.md                       # Contribution guidelines
├── DATA-LICENSE.md                       # OGL 3.0 (for ontology/data)
├── pyproject.toml                        # Python configuration and dependencies
├── README.md                             # This file
└── SECURITY.md                           # Policy and vulnerability reporting
```

---

## Standards Compliance

This ontology achieves compliance with W3C Recommendations and international standards:

### W3C Standards

- **RDF 1.1** ([W3C Recommendation](https://www.w3.org/TR/rdf11-primer/)) - Universal data model for linked data
- **OWL 2** ([W3C Recommendation](https://www.w3.org/TR/owl2-overview/)) - Formal ontology with 31 classes and 75 properties
- **SKOS** ([W3C Recommendation](https://www.w3.org/TR/skos-reference/)) - Knowledge taxonomy with hierarchical relationships
- **SHACL** ([W3C Recommendation](https://www.w3.org/TR/shacl/)) - 38 validation shapes for data quality

### Metadata Standards

- **Dublin Core** ([DCMI Terms](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/)) - Comprehensive metadata for provenance and versioning
- **Schema.org** - Future compatibility with educational extensions for web discoverability

### Best Practices

- **Persistent URIs** - w3id.org namespace for long-term stability
- **Semantic Versioning** - Clear version tracking following semver.org
- **Linked Data Principles** - Following Tim Berners-Lee's 4 principles
- **Content Negotiation** - Support for multiple RDF formats

### Validation & Quality

- **Automated CI/CD** - GitHub Actions validate every commit
- **SHACL Constraints** - 38 shapes ensure structural integrity
- **Test Coverage** - Validation shapes cover all major classes

📋 **[Read full standards compliance documentation →](docs/standards-compliance.md)**

This document explains:

- How each W3C standard is implemented
- Examples of standard usage in the ontology
- Benefits of standards compliance
- Interoperability achievements

---

## Documentation

### Auto-Generated Ontology Documentation

Complete HTML documentation with class hierarchies, properties, and visualizations:

📘 **[Browse Full Documentation](https://oaknational.github.io/oak-curriculum-ontology/)**

Generated automatically via WIDOCO on each release, includes:

- Complete class and property definitions
- Domain and range specifications
- Visual diagrams and WebVOWL visualization
- Downloadable formats

### Repository Documentation

- 📋 **[Standards Compliance](docs/standards-compliance.md)** - W3C standards and semantic web best practices
- 🔧 **[Scripts and Tools](scripts/README.md)** - Validation, export, and build utilities
- 🏗️ **[Neo4j Export Architecture](scripts/export_to_neo4j_ARCHITECTURE.md)** - Detailed export pipeline documentation
- 📖 **[Citation Metadata](CITATION.cff)** - Machine-readable citation for academic use
- 🤝 **[Contributing Guidelines](CONTRIBUTING.md)** - How to contribute to this project

---

## Contributing

We welcome feedback and suggestions from the community!

**During this early release (v0.1.x), we welcome:**

- 🐛 Bug reports - Issues with data quality, structure, or documentation
- 💡 Feature suggestions - Ideas for improvements or additions
- 📝 Documentation feedback - Clarifications, corrections, or enhancements
- ❓ Questions - About the ontology, data model, or usage

**How to contribute:**

1. Read [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines
2. [Open an issue](https://github.com/oaknational/oak-curriculum-ontology/issues) to share your feedback
3. Provide clear context and examples

**Note:** We are not accepting pull requests during v0.1.x while we refine the ontology structure and establish governance processes. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## License

This repository uses **dual licensing** to appropriately cover different types of content:

### Ontology and Data (OGL 3.0)

The curriculum ontology, vocabulary definitions, and curriculum data are licensed under [Open Government Licence v3.0 (OGL 3.0)](DATA-LICENSE.md).

**Applies to:**

- `ontology/` - OWL/SKOS ontology files
- `data/` - Curriculum instance data
- `docs/` - Documentation

**What you can do:**

- ✅ Use for any purpose (commercial or non-commercial)
- ✅ Copy, modify, and redistribute
- ✅ Build applications and services
- ⚠️ Must provide attribution: "Oak National Academy"

### Code (MIT License)

All Python scripts, GitHub Actions workflows, and software tools are licensed under the [MIT License](CODE-LICENSE.md).

**Applies to:**

- `scripts/` - Scripts and Python code
- `.github/workflows/` - CI/CD automation

**What you can do:**

- ✅ Use, modify, and redistribute freely
- ✅ Use in commercial projects
- ✅ Minimal restrictions
- ⚠️ Must provide attribution: "Oak National Academy"

---

## Citation

If you use this ontology in your research, please cite it using the "Cite this repository" button on GitHub, which provides citations in BibTeX, APA, Chicago, and other formats.

Alternatively, see [CITATION.cff](CITATION.cff) for machine-readable citation metadata.

---

## Roadmap

### v0.1.3 (Current - June 2026)

- ✅ Core ontology structure (31 classes, 75 properties)
- ✅ 12 subjects with knowledge taxonomies
- ✅ SHACL validation (38 shapes)
- ✅ Automated CI/CD pipelines
- ✅ Multi-format distributions (Turtle, JSON-LD, RDF/XML, N-Triples)
- ✅ Neo4j export tooling
- ✅ Standards compliance documentation

### Future Plans

- Make this ontology the canonical substrate for Oak's Curriculum MCP server, so AI agents and the published knowledge graph share one model
- Publish the revised National Curriculum (expected publication 2027, first teaching from 2028) alongside the 2014 data, with explicit mappings between the two to support transition planning
- Public SPARQL endpoint deployment
- Learning resource integration using LRMI standards (videos, worksheets, assessments etc.)
- Progression models and learning pathways
- Enhanced documentation

**Feedback welcome!** If you have suggestions for the roadmap, [open an issue](https://github.com/oaknational/oak-curriculum-ontology/issues).

---

## Related Resources

- [Oak National Academy](https://www.thenational.academy/) - Free, high-quality curriculum resources for UK schools
- [National Curriculum for England](https://www.gov.uk/government/collections/national-curriculum) - Official statutory requirements
- [UK Government Linked Data](https://www.data.gov.uk/) - UK public sector open data
- [W3C Semantic Web](https://www.w3.org/standards/semanticweb/) - Standards and specifications
- [Schema.org Education](https://schema.org/EducationalOrganization) - Educational markup vocabulary

---

## Acknowledgments

This ontology was developed by Oak National Academy with input from:

- Educational domain experts
- Semantic web practitioners
- UK curriculum specialists
- Open data community

Special thanks to the broader semantic web and open education communities for their tools, standards, and best practices. In particular, our knowledge taxonomy has been inspired by the following work:

- [Australian Curriculum](https://www.australiancurriculum.edu.au/) published by the Australian Curriculum, Assessment and Reporting Authority (ACARA).  
- [BBC Curriculum Ontology](https://www.bbc.co.uk/ontologies/curriculum) published by the BBC, for describing the National Curricula within the UK.

---

## Contact

For questions, suggestions, or collaboration opportunities:

- **GitHub Issues**: [Report an issue](https://github.com/oaknational/oak-curriculum-ontology/issues)
- **Documentation**: [https://oaknational.github.io/oak-curriculum-ontology/](https://oaknational.github.io/oak-curriculum-ontology/)

---

**Developed by [Oak National Academy](https://thenational.academy)**
