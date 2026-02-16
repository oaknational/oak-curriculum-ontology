# Oak Curriculum Ontology

<!-- Version and Status Badges -->
![Version](https://img.shields.io/badge/version-0.1.0-orange)
![Status](https://img.shields.io/badge/status-early_release-yellow)
![License: MIT + OGL-3.0](https://img.shields.io/badge/License-MIT%20%2B%20OGL--UK--3.0-lightgrey.svg)
![Python](https://img.shields.io/badge/python-3.12+-blue.svg)

<!-- Build and Quality Badges -->
[![Validate Ontology](https://github.com/oaknational/oak-curriculum-ontology-public/workflows/Validate%20Ontology/badge.svg)](https://github.com/oaknational/oak-curriculum-ontology-public/actions/workflows/validate-ontology.yml)
[![Generate Documentation](https://github.com/oaknational/oak-curriculum-ontology-public/workflows/Generate%20GH%20Pages%20with%20Widoco/badge.svg)](https://github.com/oaknational/oak-curriculum-ontology-public/actions/workflows/generate-docs-widoco.yml)
[![Generate Distributions](https://github.com/oaknational/oak-curriculum-ontology-public/workflows/Generate%20Static%20Distribution%20Files/badge.svg)](https://github.com/oaknational/oak-curriculum-ontology-public/actions/workflows/generate-distributions.yml)

<!-- Standards Badges -->
[![W3C RDF](https://img.shields.io/badge/W3C-RDF%201.1-005A9C)](https://www.w3.org/TR/rdf11-primer/)
[![W3C OWL](https://img.shields.io/badge/W3C-OWL%202-005A9C)](https://www.w3.org/TR/owl2-overview/)
[![W3C SKOS](https://img.shields.io/badge/W3C-SKOS-005A9C)](https://www.w3.org/TR/skos-reference/)
[![W3C SHACL](https://img.shields.io/badge/W3C-SHACL-005A9C)](https://www.w3.org/TR/shacl/)

> **A formal semantic representation of the Oak National Academy Curriculum and its alignment to the National Curriculum for England (2014)**

Machine-readable curriculum data in W3C-standard formats (RDF, OWL, SKOS, SHACL) enabling interoperability, semantic queries, and data-driven educational tools.

📘 **[Browse Full Documentation](https://oaknational.github.io/oak-curriculum-ontology-public/)** |
🔍 **[View Ontology](ontology/oak-curriculum-ontology.ttl)** |
📊 **[Download Distributions](https://github.com/oaknational/oak-curriculum-ontology-public/releases/latest)**

Developed by [Oak National Academy](https://thenational.academy)

---

## Table of Contents

- [⚠️ Early Release Notice](#️-early-release-notice)
- [What Is This?](#what-is-this)
- [Quick Start](#quick-start)
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
- 📝 Feedback, issues, and contributions are welcome!

**We welcome:**
- 🐛 Issue reports (structure, data, documentation)
- 💡 Feature requests and suggestions
- 🤝 Contributions (see [CONTRIBUTING.md](CONTRIBUTING.md))

---

## What Is This?

The Oak Curriculum Ontology provides:

**Curriculum Structure** - Formal definitions of programmes, units, lessons, and their relationships

**Knowledge Taxonomy** - Hierarchical subject taxonomies for English, Mathematics, Science, History, Geography, and Citizenship aligned to National Curriculum (2014)

**Validation Rules** - SHACL constraints ensuring data quality and completeness

**Interoperable Data** - W3C-standard RDF enabling integration with any semantic web tool or platform

This ontology bridges official curriculum requirements (National Curriculum 2014) with practical teaching programmes, making curriculum data queryable, analyzable, and machine-processable.

---

## Quick Start

```turtle
@prefix curric: <https://w3id.org/uk/oak/curriculum/ontology/> .
@prefix natcurric: <https://w3id.org/uk/oak/curriculum/nationalcurriculum/> .
@prefix oakcurric: <https://w3id.org/uk/oak/curriculum/oakcurriculum/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

# Access a Year 7 Mathematics programme
oakcurric:programme-mathematics-year-7
  a curric:Programme ;
  rdfs:label "Mathematics Year 7"@en ;
  curric:hasYearGroup natcurric:year-group-7 ;
  curric:hasSubject natcurric:subject-mathematics ;
  curric:hasUnitVariantInclusion oakcurric:unit-variant-inclusion-1 .
```

**Namespace URIs:**
- `https://w3id.org/uk/oak/curriculum/ontology/` - Ontology classes and properties
- `https://w3id.org/uk/oak/curriculum/nationalcurriculum/` - National Curriculum (2014) data
- `https://w3id.org/uk/oak/curriculum/oakcurriculum/` - Oak curriculum programmes

---

## Key Features

✅ **26 ontology classes** defining curriculum structure (Programme, Unit, Lesson, Discipline, Strand, etc.)
✅ **26 SHACL validation shapes** ensuring data integrity
✅ **8 subject areas** with full knowledge taxonomies
✅ **National Curriculum alignment** linking Oak content to statutory requirements
✅ **Automated validation** via GitHub Actions CI/CD
✅ **Multi-format distributions** (Turtle, JSON-LD, RDF/XML, N-Triples)
✅ **Standards-compliant** (RDF 1.1, OWL 2, SKOS, SHACL, Dublin Core)
✅ **Open data** (OGL 3.0 license for ontology/data, MIT for code)

---

## Core Concepts

### Temporal Hierarchy
How curriculum is organized by age and phase:
```
Phase (Primary, Secondary)
  └─ Key Stage (KS1, KS2, KS3, KS4)
      └─ Year Group (Year 1-11)
```

### Programme Structure
How subjects are organized into teaching programmes:
```
Subject (e.g., Mathematics)
  └─ Programme (e.g., Mathematics Year 7)
      └─ Unit (coherent topic, e.g., "Fractions")
          └─ Unit Variant (exam board variations)
              └─ Lesson (individual teaching session)
```

### Knowledge Taxonomy
How subject content is organized hierarchically (SKOS):
```
Discipline (e.g., Science)
  └─ Strand (e.g., "Structure and function of living organisms")
      └─ SubStrand (e.g., "Cells and organisation")
          └─ ContentDescriptor (e.g., "Cells as fundamental unit")
```

**Current subject coverage:**
- **English** - Programme structure and knowledge taxonomy
- **Mathematics** - Programme structure and knowledge taxonomy
- **Science** - Subdivided into Biology, Chemistry, Physics with separate knowledge taxonomies
- **History** - Programme structure and knowledge taxonomy
- **Geography** - Programme structure and knowledge taxonomy
- **Citizenship** - Programme structure and knowledge taxonomy

---

## Use Cases

**Educational Platforms** - Load curriculum data into learning management systems
**Curriculum Analysis** - Query relationships between subjects, key stages, and topics
**AI/ML Training** - Use structured curriculum data for educational AI models
**Research** - Analyze curriculum structure, progression, and coverage
**Data Integration** - Link to other educational datasets via persistent URIs
**Quality Assurance** - Validate custom curriculum data against standard shapes
**Graph Databases** - Export to Neo4j for network analysis and visualization
**Semantic Search** - Enable intelligent discovery of curriculum content

---

## Getting Started

### Option 1: Download Distribution Files

Pre-generated RDF files in multiple formats available from [GitHub Releases](https://github.com/oaknational/oak-curriculum-ontology-public/releases/latest):

```bash
# Download Turtle (compact, human-readable)
curl -L -O https://github.com/oaknational/oak-curriculum-ontology-public/releases/latest/download/oak-curriculum-full.ttl

# Download JSON-LD (for web apps)
curl -L -O https://github.com/oaknational/oak-curriculum-ontology-public/releases/latest/download/oak-curriculum-full.jsonld

# Download RDF/XML (for legacy tools)
curl -L -O https://github.com/oaknational/oak-curriculum-ontology-public/releases/latest/download/oak-curriculum-full.rdf

# Download N-Triples (for streaming/line-based processing)
curl -L -O https://github.com/oaknational/oak-curriculum-ontology-public/releases/latest/download/oak-curriculum-full.nt
```

**Available formats:**
- `.ttl` (Turtle) - Compact, human-readable
- `.jsonld` (JSON-LD) - JSON-based RDF for web apps
- `.rdf` (RDF/XML) - XML-based RDF for legacy tools
- `.nt` (N-Triples) - Line-based format for streaming

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

SELECT ?programme ?subject ?label WHERE {
  ?programme curric:hasYearGroup natcurric:year-group-7 ;
             curric:hasSubject ?subject ;
             rdfs:label ?label .
}
ORDER BY ?subject
```

### Find Mathematics content descriptors

```sparql
PREFIX natcurric: <https://w3id.org/uk/oak/curriculum/nationalcurriculum/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?descriptor ?label WHERE {
  natcurric:discipline-mathematics skos:narrower+ ?descriptor .
  ?descriptor a <https://w3id.org/uk/oak/curriculum/ontology/ContentDescriptor> ;
              skos:prefLabel ?label .
}
ORDER BY ?label
```

### List units in sequence for a programme

```sparql
PREFIX curric: <https://w3id.org/uk/oak/curriculum/ontology/>
PREFIX oakcurric: <https://w3id.org/uk/oak/curriculum/oakcurriculum/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?position ?unit ?label WHERE {
  oakcurric:programme-science-year-7
    curric:hasUnitVariantInclusion ?inclusion .
  ?inclusion curric:sequencePosition ?position ;
             curric:includesUnitVariant/curric:isUnitVariantOf ?unit .
  ?unit rdfs:label ?label .
}
ORDER BY ?position
```

### Find all Key Stage 3 Science content

```sparql
PREFIX curric: <https://w3id.org/uk/oak/curriculum/ontology/>
PREFIX natcurric: <https://w3id.org/uk/oak/curriculum/nationalcurriculum/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT DISTINCT ?content ?label WHERE {
  ?discipline a curric:Discipline ;
              skos:prefLabel ?disciplineLabel .
  FILTER(CONTAINS(LCASE(?disciplineLabel), "science"))

  ?discipline skos:narrower+ ?content .
  ?content skos:prefLabel ?label .
}
ORDER BY ?label
```

---

## File Structure

```
oak-curriculum-ontology-public/
├── ontology/
│   ├── oak-curriculum-ontology.ttl       # Core classes & properties (26 classes)
│   └── oak-curriculum-constraints.ttl    # SHACL validation shapes (26 shapes)
│
├── data/
│   ├── temporal-structure.ttl            # Phases, Key Stages, Year Groups
│   ├── programme-structure.ttl           # Exam boards, tiers
│   ├── threads.ttl                       # Cross-cutting themes
│   └── subjects/
│       ├── english/
│       │   ├── english-programme-structure.ttl
│       │   ├── english-knowledge-taxonomy.ttl
│       │   └── english-key-stage-*.ttl   # KS1-KS4 programme instances
│       ├── mathematics/
│       │   ├── mathematics-programme-structure.ttl
│       │   ├── mathematics-knowledge-taxonomy.ttl
│       │   └── mathematics-key-stage-*.ttl
│       ├── biology/
│       │   ├── biology-programme-structure.ttl
│       │   ├── biology-knowledge-taxonomy.ttl
│       │   └── biology-key-stage-4.ttl
│       ├── chemistry/
│       │   ├── chemistry-programme-structure.ttl
│       │   ├── chemistry-knowledge-taxonomy.ttl
│       │   └── chemistry-key-stage-4.ttl
│       ├── physics/
│       │   ├── physics-programme-structure.ttl
│       │   ├── physics-knowledge-taxonomy.ttl
│       │   └── physics-key-stage-4.ttl
│       ├── history/
│       │   ├── history-programme-structure.ttl
│       │   ├── history-knowledge-taxonomy.ttl
│       │   └── history-key-stage-*.ttl
│       ├── geography/
│       │   ├── geography-programme-structure.ttl
│       │   ├── geography-knowledge-taxonomy.ttl
│       │   └── geography-key-stage-*.ttl
│       └── citizenship/
│           ├── citizenship-programme-structure.ttl
│           ├── citizenship-knowledge-taxonomy.ttl
│           └── citizenship-key-stage-*.ttl
│
├── scripts/
│   ├── validate.sh                       # Local SHACL validation
│   ├── export_to_neo4j.py               # Export to Neo4j with transformations
│   ├── export_to_neo4j_config.json      # Neo4j export configuration
│   ├── export_to_neo4j_ARCHITECTURE.md  # Neo4j export architecture docs
│   ├── merge_ttls_with_imports.py       # Merge TTL files with import resolution
│   ├── build_static_data.sh             # Generate distribution files (for releases)
│   └── README.md                         # Scripts documentation
│
├── distributions/ (published via GitHub Releases)
│   ├── oak-curriculum-full.ttl          # Complete dataset (Turtle)
│   ├── oak-curriculum-full.jsonld       # Complete dataset (JSON-LD)
│   ├── oak-curriculum-full.rdf          # Complete dataset (RDF/XML)
│   └── oak-curriculum-full.nt           # Complete dataset (N-Triples)
│
├── docs/
│   └── standards-compliance.md           # W3C standards documentation
│
├── .github/workflows/
│   ├── validate-ontology.yml             # Automated SHACL validation
│   ├── generate-docs-widoco.yml          # Auto-generate documentation
│   └── generate-distributions.yml        # Build distribution files
│
├── LICENSE-CODE                          # MIT License (for code)
├── LICENSE-DATA                          # OGL 3.0 (for ontology/data)
├── CITATION.cff                          # Citation metadata
├── CONTRIBUTING.md                       # Contribution guidelines
└── README.md                             # This file
```

---

## Standards Compliance

This ontology achieves **industry-leading compliance** with W3C Recommendations and international standards:

### W3C Standards

- **RDF 1.1** ([W3C Recommendation](https://www.w3.org/TR/rdf11-primer/)) - Universal data model for linked data
- **OWL 2** ([W3C Recommendation](https://www.w3.org/TR/owl2-overview/)) - Formal ontology with 26 classes and 40+ properties
- **SKOS** ([W3C Recommendation](https://www.w3.org/TR/skos-reference/)) - Knowledge taxonomy with hierarchical relationships
- **SHACL** ([W3C Recommendation](https://www.w3.org/TR/shacl/)) - 26 validation shapes for data quality

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
- **SHACL Constraints** - 26 shapes ensure structural integrity
- **Type Safety** - Modern Python type hints throughout scripts
- **Test Coverage** - Validation shapes cover all major classes

📋 **[Read full standards compliance documentation →](docs/standards-compliance.md)**

This comprehensive document explains:
- How each W3C standard is implemented
- Examples of standard usage in the ontology
- Benefits of standards compliance
- Interoperability achievements

---

## Documentation

### Auto-Generated Ontology Documentation

Complete HTML documentation with class hierarchies, properties, and visualizations:

📘 **[Browse Full Documentation](https://oaknational.github.io/oak-curriculum-ontology-public/)**

Generated automatically via WIDOCO on each release, includes:
- Complete class and property definitions
- Domain and range specifications
- Visual diagrams and WebVOWL visualization
- Downloadable formats

### Repository Documentation

- 📋 **[Standards Compliance](docs/standards-compliance.md)** - W3C standards and semantic web best practices
- 🔧 **[Scripts and Tools](scripts/README.md)** - Validation, export, and build utilities
- 🏗️ **[Neo4j Export Architecture](scripts/export_to_neo4j_ARCHITECTURE.md)** - Detailed export pipeline documentation
- 🤝 **[Contributing Guidelines](CONTRIBUTING.md)** - How to contribute to this project

### Quick Reference

| Documentation | Purpose |
|--------------|---------|
| [README.md](README.md) | This file - project overview and getting started |
| [standards-compliance.md](docs/standards-compliance.md) | W3C standards implementation details |
| [scripts/README.md](scripts/README.md) | Tool usage and CLI documentation |
| [CITATION.cff](CITATION.cff) | Citation metadata for academic use |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribution guidelines |

---

## Contributing

We welcome contributions from the community!

**Ways to contribute:**
- 🐛 Report issues with data or structure
- 💡 Suggest improvements or new features
- 📝 Improve documentation
- 🔧 Submit pull requests

**Before contributing:**
1. Read [CONTRIBUTING.md](CONTRIBUTING.md)
2. Check existing [issues](https://github.com/oaknational/oak-curriculum-ontology-public/issues)
3. Run `./scripts/validate.sh` to ensure data quality
4. Follow semantic web best practices

**Development workflow:**
1. Fork the repository
2. Create a feature branch
3. Make changes and validate locally
4. Submit pull request with clear description
5. CI/CD will automatically validate your changes

---

## License

This repository uses **dual licensing** to appropriately cover different types of content:

### Ontology and Data (OGL 3.0)

The curriculum ontology, vocabulary definitions, and curriculum data are licensed under [Open Government Licence v3.0 (OGL 3.0)](LICENSE-DATA).

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

All Python scripts, GitHub Actions workflows, and software tools are licensed under the [MIT License](LICENSE-CODE).

**Applies to:**
- `scripts/` - Python utilities
- `.github/workflows/` - CI/CD automation

**What you can do:**
- ✅ Use, modify, and redistribute freely
- ✅ Use in commercial projects
- ✅ Minimal restrictions

**Attribution:** When using this work, please credit **"Oak National Academy"**

---

## Citation

If you use this ontology in your research, please cite:

```bibtex
@dataset{oak_curriculum_ontology_2026,
  author = {{Oak National Academy}},
  title = {Oak Curriculum Ontology},
  year = {2026},
  version = {0.1.0},
  url = {https://oaknational.github.io/oak-curriculum-ontology-public/},
  doi = {10.5281/zenodo.XXXXXXX},
  note = {A formal semantic representation of the Oak Curriculum and linkage to the National Curriculum for England (2014)}
}
```

**APA Format:**
Oak National Academy. (2026). *Oak Curriculum Ontology* (Version 0.1.0) [Data set]. https://oaknational.github.io/oak-curriculum-ontology-public/

**Chicago Format:**
Oak National Academy. "Oak Curriculum Ontology." Version 0.1.0, 2026. https://oaknational.github.io/oak-curriculum-ontology-public/.

See [CITATION.cff](CITATION.cff) for machine-readable citation metadata compatible with GitHub, Zenodo, and other research platforms.

---

## Roadmap

### v0.1.0 (Current - February 2026)
- ✅ Core ontology structure (26 classes, 40+ properties)
- ✅ 8 subjects with knowledge taxonomies
- ✅ SHACL validation (26 shapes)
- ✅ Automated CI/CD pipelines
- ✅ Multi-format distributions (Turtle, JSON-LD, RDF/XML, N-Triples)
- ✅ Neo4j export tooling
- ✅ Standards compliance documentation

### v0.2.0 (Planned - Q2 2026)
- 🚧 Additional subjects (Computing, Art, Music, PE, Languages)
- 🚧 Expanded SHACL validation (pedagogical constraints)
- 🚧 Public SPARQL endpoint deployment
- 🚧 Enhanced documentation with tutorials
- 🚧 API examples for common integrations
- 🚧 Performance benchmarks

### v1.0.0 (Planned - Q4 2026)
- 🔮 Complete subject coverage (14 National Curriculum subjects)
- 🔮 Comprehensive validation suite
- 🔮 Production-grade SPARQL endpoint with SLA
- 🔮 Content negotiation for URIs
- 🔮 Integration examples with major LMS platforms
- 🔮 Research case studies and white papers

### Future Considerations
- Learning resource integration (videos, worksheets, assessments)
- Cross-curriculum skill taxonomy
- Progression models and learning pathways
- Assessment objective mappings
- Multi-language support (Welsh, Gaelic)

**Feedback welcome!** If you have suggestions for the roadmap, [open an issue](https://github.com/oaknational/oak-curriculum-ontology-public/issues).

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

Special thanks to the broader semantic web and open education communities for their tools, standards, and best practices.

---

## Contact

For questions, suggestions, or collaboration opportunities:

- **GitHub Issues**: [Report an issue](https://github.com/oaknational/oak-curriculum-ontology-public/issues)
- **Email**: Contact Oak National Academy via [thenational.academy](https://www.thenational.academy/contact)
- **Documentation**: [https://oaknational.github.io/oak-curriculum-ontology-public/](https://oaknational.github.io/oak-curriculum-ontology-public/)

---

**Developed with ❤️ by [Oak National Academy](https://thenational.academy)**

*Making curriculum data open, interoperable, and accessible to all*
