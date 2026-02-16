# Standards Compliance and Interoperability

**Version:** 0.1.0
**Last Updated:** 2026-02-16

---

## Executive Summary

The Oak Curriculum Ontology has been developed as an **open, standards-compliant, interoperable semantic web resource** for representing educational curriculum data. This document demonstrates how the ontology achieves industry-leading compliance with W3C Recommendations, international educational metadata standards, and semantic web best practices.

---

## Design Objectives

The Oak Curriculum Ontology was designed to achieve:

1. **Standards Compliance**: Use established W3C Recommendations and international standards
2. **Interoperability**: Enable seamless data exchange across educational systems and platforms
3. **Discoverability**: Support web-based discovery through search engines and semantic queries
4. **Extensibility**: Allow future enhancement without breaking existing implementations
5. **Validation**: Ensure data quality through formal constraint checking
6. **Persistence**: Provide stable, long-term identifiers that remain valid as technology evolves
7. **Openness**: Use open licenses and transparent governance for community trust

---

## Standards Used

The Oak Curriculum Ontology implements the following international standards:

### 1. RDF 1.1 (Resource Description Framework)

**What it is:**
The foundational W3C standard for representing information as a graph of linked data. RDF provides a universal model for describing resources using subject-predicate-object triples.

**Standard Status:**
[W3C Recommendation](https://www.w3.org/TR/rdf11-primer/) (February 2014)

**Why we use it:**
RDF is the fundamental building block of the Semantic Web. It enables:
- **Universal data model**: Any system understanding RDF can process our data
- **Graph-based relationships**: Naturally represents complex curriculum connections
- **Extensibility**: New properties and classes can be added without breaking existing data
- **Linked data**: Enables connections to external educational resources and standards

**How we use it:**
Every curriculum element (programmes, units, lessons, content descriptors) is represented as an RDF resource with a unique URI. Relationships between elements use RDF properties.

**Example:**
```turtle
oakcurric:examboard-aqa
  rdf:type curric:ExamBoard ;
  rdfs:label "AQA"@en ;
  rdfs:comment "Assessment and Qualifications Alliance"@en .
```

**Benefits:**
- Data can be loaded into any RDF triple store (Apache Jena, GraphDB, Blazegraph)
- Standard SPARQL queries work across all implementations
- RDF tooling ecosystem (parsers, validators, visualizers) is mature and widely supported

---

### 2. OWL 2 (Web Ontology Language)

**What it is:**
W3C standard for defining formal ontologies with rich semantics. OWL extends RDF with capabilities for defining classes, properties, constraints, and logical relationships.

**Standard Status:**
[W3C Recommendation](https://www.w3.org/TR/owl2-overview/) (December 2012)

**Why we use it:**
OWL enables formal modeling of curriculum structure with:
- **Class hierarchies**: Define relationships between curriculum entity types
- **Property definitions**: Specify domains, ranges, and characteristics of relationships
- **Inverse properties**: Bidirectional navigation through the curriculum graph
- **Transitive properties**: Express inheritance (e.g., "Year 7 is part of Key Stage 3 is part of Secondary Phase")
- **Cardinality constraints**: Enforce structural rules (e.g., "every programme has exactly one year group")

**How we use it:**
The ontology defines 26 core classes (Programme, Unit, UnitVariant, Lesson, Discipline, Strand, ContentDescriptor, etc.) and 40+ properties with formal OWL semantics.

**Example:**
```turtle
curric:Programme
  rdf:type owl:Class ;
  rdfs:label "Programme"@en ;
  rdfs:comment "A structured sequence of units designed for a specific year group"@en ;
  rdfs:isDefinedBy <https://w3id.org/uk/oak/curriculum/ontology> .

curric:hasUnitVariantInclusion
  rdf:type owl:ObjectProperty ;
  rdfs:domain curric:Programme ;
  rdfs:range curric:UnitVariantInclusion ;
  owl:inverseOf curric:isUnitVariantInclusionOf .
```

**Benefits:**
- Formal semantics enable automated reasoning and inference
- Clear specifications prevent misinterpretation of data structure
- Tools can validate that data conforms to the ontology structure
- Enables discovery of implicit relationships through logical inference

---

### 3. SKOS (Simple Knowledge Organisation System)

**What it is:**
W3C standard for representing taxonomies, classification schemes, and controlled vocabularies using RDF.

**Standard Status:**
[W3C Recommendation](https://www.w3.org/TR/skos-reference/) (August 2009)

**Why we use it:**
SKOS provides established patterns for organising hierarchical knowledge:
- **Concept schemes**: organise related concepts into coherent taxonomies
- **Hierarchical relationships**: `skos:broader` and `skos:narrower` for parent-child relationships
- **Preferred labels**: Multi-lingual support with `skos:prefLabel`
- **Alternative labels**: Synonyms and variations with `skos:altLabel`
- **Definitions and scope notes**: Rich descriptive metadata

**How we use it:**
The ontology uses SKOS to represent the National Curriculum for England (2014) knowledge taxonomy:
- Disciplines, Strands, SubStrands, and ContentDescriptors are `skos:Concept` instances
- Hierarchical relationships use `skos:broader`/`skos:narrower`
- Labels and definitions use SKOS vocabulary
- Available subjects: English, Mathematics, Science (Biology, Chemistry, Physics), History, Geography, Citizenship

**Example:**
```turtle
natcurric:discipline-mathematics
  a skos:Concept, curric:Discipline ;
  skos:prefLabel "Mathematics"@en ;
  skos:topConceptOf natcurric:knowledge-taxonomy ;
  skos:narrower
    natcurric:strand-working-mathematically,
    natcurric:strand-number ,
    natcurric:strand-algebra ;
  dcterms:modified "2025-12-18T12:33:32Z"^^xsd:dateTime .
```

**Benefits:**
- Standard vocabulary for taxonomies is widely understood
- Tools designed for SKOS can process curriculum taxonomies
- Enables alignment with other SKOS-based educational standards
- Multi-lingual curriculum support through language-tagged labels

---

### 4. SHACL (Shapes Constraint Language)

**What it is:**
W3C standard for validating RDF data against a set of defined constraints (shapes). SHACL acts as a "schema validator" for RDF graphs.

**Standard Status:**
[W3C Recommendation](https://www.w3.org/TR/shacl/) (July 2017)

**Why we use it:**
SHACL ensures data quality by validating that:
- Required properties are present
- Properties have correct data types and value ranges
- Cardinality constraints are satisfied (e.g., "exactly one", "at least one")
- Values conform to expected patterns
- Structural integrity is maintained

**How we use it:**
The ontology includes comprehensive SHACL shapes (`oak-curriculum-constraints.ttl`) with 26 validation shapes covering:
- Programme structure validation
- Sequencing constraints (unique sequence positions)
- Exam board and tier consistency
- Required relationships between entities

**Example:**
```turtle
curric:ProgrammeShape
  a sh:NodeShape ;
  sh:targetClass curric:Programme ;
  sh:property [
    sh:path curric:hasYearGroup ;
    sh:minCount 1 ;
    sh:maxCount 1 ;
    sh:class curric:YearGroup ;
    sh:message "A Programme must have exactly one YearGroup"@en
  ] .
```

**Benefits:**
- Automated data quality validation before publication
- Clear error messages help data creators fix issues
- Validates complex business rules (e.g., "programmes with tiers must have exam boards")
- Standard tooling (Apache Jena, TopBraid) supports SHACL validation
- Ensures consistency across all curriculum data

---

### 5. Dublin Core Metadata Terms (DCMI)

**What it is:**
International standard for resource metadata, providing a core vocabulary for describing digital resources.

**Standard Status:**
[ISO 15836](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/), [IETF RFC 5013](https://www.ietf.org/rfc/rfc5013.txt)

**Why we use it:**
Dublin Core provides widely-recognized properties for:
- **Provenance**: Creator, publisher, creation date
- **Rights management**: License, copyright
- **Versioning**: Created, modified, issued dates
- **Description**: Title, description, subject

**How we use it:**
Every ontology file includes comprehensive Dublin Core metadata:

**Example:**
```turtle
<https://w3id.org/uk/oak/curriculum/ontology>
  dcterms:title "Oak Curriculum Ontology"@en ;
  dcterms:description "Formal semantic representation of the Oak Curriculum and linkage to the National Curriculum for England (2014)"@en ;
  dc:creator "Oak National Academy" ;
  dcterms:created "2025-11-20"^^xsd:date ;
  dcterms:modified "2026-01-15"^^xsd:date ;
  dcterms:license <http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/> ;
  dcterms:rights "Copyright © 2026 Oak National Academy."@en .
```

**Benefits:**
- Standard metadata recognized by libraries, archives, and data catalogs
- Clear provenance and licensing for legal compliance
- Version tracking for change management
- Interoperability with non-RDF systems that support Dublin Core

---

### 6. Schema.org (Educational Extension)

**What it is:**
Web vocabulary developed by Google, Microsoft, Yahoo, and Yandex for structured data markup. Schema.org's educational extension includes types and properties for learning resources and curriculum alignment.

**Standard Status:**
Community standard, [schema.org](https://schema.org/) (developed 2011-present)

**Why we use it:**
Schema.org enables:
- **Web discoverability**: Search engines understand educational content
- **Learning Resource Metadata Initiative (LRMI)**: Standard properties for describing educational resources
- **Curriculum alignment**: `AlignmentObject` connects resources to curriculum standards
- **Widespread adoption**: Used by educational publishers, OER platforms, and learning management systems

**How we use it:**
Oak extends its teaching resource classes to be compatible with Schema.org types. When Oak adds teaching resources (videos, worksheets, quizzes), they will be:
- Subclasses of schema.org types (`schema:VideoObject`, `schema:Article`, `schema:Quiz`)
- Use schema.org properties (`schema:url`, `schema:name`, `schema:duration`)
- Support LRMI curriculum alignment via `schema:educationalAlignment`

**Future example:**
```turtle
@prefix schema: <http://schema.org/> .

oakcurric:resource-video-introduction-to-cells
  a curric:Video, schema:VideoObject ;
  schema:name "Introduction to Cell Structure"@en ;
  schema:url <https://cdn.thenational.academy/videos/7826.mp4> ;
  schema:duration "PT12M30S" ;
  schema:educationalLevel "Year 7"@en ;
  schema:learningResourceType "video" ;
  schema:educationalAlignment [
    a schema:AlignmentObject ;
    schema:alignmentType "teaches" ;
    schema:educationalFramework "National Curriculum for England (2014)" ;
    schema:targetUrl natcurric:content-descriptor-cells-as-unit-of-living-organism
  ] .
```

**Benefits:**
- Resources discoverable through Google Search and Google for Education
- Compatible with major educational platforms (Khan Academy, Coursera, OER Commons)
- Standard vocabulary for describing educational characteristics (age range, difficulty, type)
- Enables curriculum alignment through AlignmentObject (resources point to Oak curriculum URIs)

---

### 7. Persistent Identifiers (w3id.org)

**What it is:**
Community service providing persistent URIs for linked data resources. w3id.org uses HTTP redirects to ensure URIs remain stable even when hosting infrastructure changes.

**Standard Status:**
Community best practice, [w3id.org](https://w3id.org/)

**Why we use it:**
Persistent identifiers ensure:
- **Long-term stability**: URIs work indefinitely, regardless of hosting changes
- **Content negotiation**: Same URI serves different formats (HTML for humans, RDF for machines)
- **Professional trust**: Signals production-ready, professionally maintained data
- **Safe referencing**: Other systems can safely use these URIs knowing they won't break

**How we use it:**
All curriculum URIs use the w3id.org namespace:
- Ontology: `https://w3id.org/uk/oak/curriculum/ontology/`
- National Curriculum Data: `https://w3id.org/uk/oak/curriculum/nationalcurriculum/`
- Oak Curriculum Data: `https://w3id.org/uk/oak/curriculum/oakcurriculum/`

w3id.org redirects these to the actual GitHub repository via HTTP 303 redirects.

**Example:**
```
User requests: https://w3id.org/uk/oak/curriculum/ontology/Programme
       ↓
w3id.org redirects (HTTP 303) to:
       ↓
GitHub: https://raw.githubusercontent.com/oaknational/oak-curriculum-ontology-public/main/ontology/oak-curriculum-ontology.ttl
```

**Benefits:**
- URIs remain valid even if Oak changes hosting providers
- Repository can move without breaking external references
- Content negotiation supports multiple formats from single URI
- Aligned with Linked Data best practices (Tim Berners-Lee's 4 principles)

---

### 8. Semantic Versioning

**What it is:**
Standard versioning scheme using MAJOR.MINOR.PATCH format to communicate the nature of changes.

**Standard Status:**
Community standard, [semver.org](https://semver.org/)

**Why we use it:**
Semantic versioning provides clear signals about:
- **Breaking changes** (MAJOR): Incompatible changes requiring consumer updates
- **New features** (MINOR): Backward-compatible additions
- **Bug fixes** (PATCH): Backward-compatible corrections

**How we use it:**
Current version: **0.1.0**

Version information is tracked through:
- Version IRIs in ontology metadata
- Git tags and releases
- CHANGELOG.md documenting changes between versions

**Example:**
```turtle
<https://w3id.org/uk/oak/curriculum/ontology/>
  owl:versionInfo "0.1.0" ;
  owl:versionIRI <https://w3id.org/uk/oak/curriculum/ontology/0.1.0> .
```

**Benefits:**
- Consumers know when updates will break their applications
- Clear change communication through CHANGELOG.md
- Aligns with software development best practices
- Version tracking through Git enables reproducibility

---

### 9. Dual Licensing: OGL v3.0 and MIT

**What it is:**
This repository uses dual licensing to appropriately cover different types of content:
- **Ontology and Data**: Open Government Licence v3.0 (OGL 3.0)
- **Code**: MIT License

**Standard Status:**
- OGL v3.0: UK government standard, [OGL v3.0](http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
- MIT License: OSI-approved open source license, [MIT License](https://opensource.org/licenses/MIT)

**Why we use dual licensing:**

**For Ontology and Data (OGL 3.0):**
The Open Government Licence ensures:
- **Free use**: Anyone can use the curriculum data for any purpose
- **Reuse**: Data can be copied, adapted, and built upon
- **Redistribution**: Modified versions can be shared
- **Attribution**: Requires acknowledgment of "Oak National Academy"

Applies to:
- `ontology/` - OWL/SKOS ontology files
- `data/` - Curriculum instance data
- This document and other documentation

**For Code (MIT License):**
The MIT License provides:
- **Permissive use**: Minimal restrictions on software reuse
- **Commercial compatibility**: No copyleft requirements
- **Liability protection**: Standard software warranty disclaimers

Applies to:
- `scripts/` - Python utilities
- `.github/workflows/` - CI/CD automation

**How we use it:**
All ontology files include OGL licensing metadata:

```turtle
<https://w3id.org/uk/oak/curriculum/ontology/>
  dcterms:license <http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/> ;
  dcterms:rights "Copyright © 2026 Oak National Academy."@en .
```

**Benefits:**
- Legal clarity for both data consumers and software developers
- Appropriate licensing for different content types
- Encourages widespread adoption and innovation
- Aligns with UK government open data initiatives
- Enables educational technology ecosystem to build on curriculum data

**Note:** This standards compliance document focuses on the ontology and data standards (OGL 3.0). Code standards are documented separately in repository documentation.

---

## Interoperability Achievements

The combination of these standards enables the Oak Curriculum Ontology to achieve interoperability:

### 1. Cross-Platform Compatibility
- **RDF triple stores**: Apache Jena, GraphDB, Blazegraph, Virtuoso
- **SPARQL endpoints**: Standard query interface for any application
- **RDF libraries**: Python (rdflib), JavaScript (rdflib.js), Java (Jena API)

### 2. Tool Ecosystem Support
- **Ontology editors**: Protégé, TopBraid Composer
- **Validators**: Apache Jena SHACL, TopBraid SHACL API
- **Visualizers**: WebVOWL, Ontospy, Protégé Graph View
- **Converters**: Any RDF format (Turtle, JSON-LD, RDF/XML, N-Triples)

### 3. Search Engine Integration
- **Schema.org markup**: Google, Bing, Yahoo, Yandex understand educational properties
- **LRMI alignment**: Resources can reference Oak curriculum URIs for discoverability
- **Structured data**: Web pages with curriculum references become searchable

### 4. Educational Platform Integration
- **Learning Management Systems**: Moodle, Canvas, Blackboard (via IMS standards)
- **OER repositories**: OER Commons, OpenStax (via LRMI alignment)
- **EdTech platforms**: Any system supporting RDF/SPARQL can query curriculum data

### 5. Government Data Infrastructure
- **UK Government Linked Data**: Compatible with data.gov.uk standards
- **Open Government Licence**: Legal framework for public sector reuse
- **Persistent identifiers**: w3id.org aligns with UK government URI patterns

---

## Compliance with Linked Data Principles

The ontology follows Tim Berners-Lee's **4 principles of Linked Data**:

1. ✅ **Use URIs as names for things**
   Every curriculum entity has a persistent HTTP URI (via w3id.org)

2. ✅ **Use HTTP URIs so people can look up those names**
   URIs are resolvable and return data when accessed

3. ✅ **Provide useful information using standards (RDF, SPARQL)**
   URIs return RDF data describing the curriculum entity

4. ✅ **Include links to other URIs for discovery**
   Curriculum entities link to National Curriculum URIs, enabling graph traversal

This makes the Oak Curriculum Ontology part of the global **Web of Data**, not just a standalone dataset.

---

## Quality Assurance

The ontology implements multiple quality assurance mechanisms:

### Automated Validation
- **SHACL constraints**: 25+ validation rules ensure structural integrity
- **RDF syntax validation**: Turtle files validated against RDF 1.1 specification
- **OWL consistency checking**: Reasoners verify logical consistency

### Version Control
- **Git repository**: Full change history with commit messages
- **Semantic versioning**: Clear communication of change impact
- **Git tags**: Version snapshots for reproducibility

### Documentation
- **Inline comments**: Every class and property documented in RDF
- **Markdown guides**: Human-readable documentation for developers

---

## Conclusion

The Oak Curriculum Ontology represents an implementation of **open, standards-based curriculum data modelling**. By leveraging:

- W3C Recommendations (RDF, OWL, SKOS, SHACL)
- International metadata standards (Dublin Core, Schema.org)
- Semantic web best practices (persistent URIs, Linked Data principles)
- Open licensing (OGL v3.0)

The ontology is **an interoperable, discoverable, and extensible open standard for curriculum representation**.

This foundation enables Oak National Academy and the broader educational community to build innovative tools, resources, and services on top of a reliable and standardised curriculum infrastructure.

---

## References

- RDF 1.1 Primer: https://www.w3.org/TR/rdf11-primer/
- OWL 2 Overview: https://www.w3.org/TR/owl2-overview/
- SKOS Reference: https://www.w3.org/TR/skos-reference/
- SHACL Specification: https://www.w3.org/TR/shacl/
- Dublin Core Metadata Terms: https://www.dublincore.org/specifications/dublin-core/dcmi-terms/
- Schema.org: https://schema.org/
- LRMI Specification: https://www.dublincore.org/specifications/lrmi/
- w3id.org: https://w3id.org/
- Semantic Versioning: https://semver.org/
- Open Government Licence v3.0: http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/
- Linked Data Principles: https://www.w3.org/DesignIssues/LinkedData.html

---

**Document Version:** 1.0
**Author:** Oak National Academy
**License:** Open Government Licence v3.0
**Last Review Date:** 2026-02-16
