# Property Graph JSONL Format Reference

## Purpose and Audience

`nodes.jsonl` and `relationships.jsonl` represent the Oak Curriculum knowledge graph in a format that can be imported directly into any property graph database — Neo4j, Amazon Neptune (PG mode), TigerGraph, ArangoDB, JanusGraph, and others.

This format is for engineers and data practitioners who want to query, traverse, or analyse the Oak Curriculum Ontology using a graph database or graph analytics tooling.

## Relationship to the RDF Distributions

The JSONL files contain the same data as the RDF distributions (`oak-curriculum-full.ttl`, `.jsonld`, `.rdf`, `.nt`) but expressed in property graph terms rather than RDF terms:

| RDF concept | Property graph concept |
|---|---|
| Named individual (URI) | Node |
| `rdf:type` → ontology class | Node label |
| Datatype property literal | Node property |
| Object property (URI → URI) | Relationship |

No schema transformations are applied. Property names match the ontology predicates exactly (camelCase, unchanged). Inclusion nodes are preserved as first-class nodes with their properties. This is a faithful representation of the ontology schema.

This is **not** the same as the bespoke Neo4j export (`export-to-neo4j.yml`), which renames properties, flattens Inclusion nodes, and reverses some relationship directions for a specific application schema.

---

## Node Schema

### Field reference

| Field | Type | Description |
|---|---|---|
| `id` | string (URI) | Full URI — globally unique, dereferenceable |
| `labels` | array of string | Local name(s) of `rdf:type` class(es) from the ontology |
| `properties` | object | Literal property values, keyed by predicate local name |

### Example

```json
{
  "id": "https://w3id.org/uk/curriculum/oak-data/programme-mathematics-year-group-1",
  "labels": ["Programme"],
  "properties": {
    "name": "Mathematics Year Group 1",
    "isNationalCurriculum": true,
    "isRequired": true,
    "isExamined": false
  }
}
```

### Property naming conventions

- All property names are the local name of the RDF predicate (e.g. `isNationalCurriculum`, `sequencePosition`).
- `rdfs:label` is mapped to `"name"` — in property graph databases, "label" is a reserved concept for node type classification. `"name"` is the standard equivalent across graph products.
- Multi-valued properties (same predicate, multiple values) are represented as JSON arrays.
- Language tags are stripped — all data is English.

### XSD type coercion

| XSD type | JSON type |
|---|---|
| `xsd:boolean` | `true` / `false` |
| `xsd:integer`, `xsd:positiveInteger`, `xsd:nonNegativeInteger` | integer |
| `xsd:decimal`, `xsd:float`, `xsd:double` | float |
| `xsd:string`, `xsd:anyURI`, `xsd:dateTime`, `rdfs:Literal` | string |

---

## Relationship Schema

### Field reference

| Field | Type | Description |
|---|---|---|
| `type` | string | Local name of the RDF predicate (camelCase, unchanged) |
| `startNodeId` | string (URI) | Subject node URI |
| `endNodeId` | string (URI) | Object node URI |
| `properties` | object | Always `{}` — relationship metadata lives on nodes |

### Example

```json
{
  "type": "hasUnitVariantInclusion",
  "startNodeId": "https://w3id.org/uk/curriculum/oak-data/programme-mathematics-year-group-1",
  "endNodeId": "https://w3id.org/uk/curriculum/oak-data/inclusion-programme-mathematics-year-group-1-pos-1",
  "properties": {}
}
```

### Excluded predicates

The following predicates are not written as relationships (they are either captured as node labels, represent RDF/OWL infrastructure, or are ontology metadata):

```
rdf:type            captured as node labels
rdf:first           rdf:List infrastructure
rdf:rest            rdf:List infrastructure
rdfs:subClassOf     ontology metadata
rdfs:subPropertyOf  ontology metadata
rdfs:domain         ontology metadata
rdfs:range          ontology metadata
owl:inverseOf       ontology metadata
owl:equivalentClass ontology metadata
owl:onProperty      ontology metadata
owl:someValuesFrom  ontology metadata
owl:allValuesFrom   ontology metadata
owl:imports         file-level imports
owl:versionIRI      file-level versioning
owl:priorVersion    file-level versioning
```

---

## Node Types (Classes)

### Programme

Represents a curriculum programme (subject + year group combination).

| Property | Type | Description |
|---|---|---|
| `name` | string | Human-readable name |
| `isNationalCurriculum` | boolean | Whether this is a national curriculum programme |
| `isRequired` | boolean | Whether the programme is required |
| `isExamined` | boolean | Whether the programme is examined |

Key relationships: `coversSubject`, `coversYearGroup`, `hasUnitVariantInclusion`

### UnitVariantInclusion

A reified relationship node representing a unit variant's inclusion in a programme at a specific sequence position.

| Property | Type | Description |
|---|---|---|
| `sequencePosition` | integer | Ordering within the parent programme |

Key relationships: `includesUnitVariant` (to `UnitVariant`)

### UnitVariantChoice

A reified node representing a choice point where one of several unit variants can be selected.

| Property | Type | Description |
|---|---|---|
| `sequencePosition` | integer | Ordering within the parent programme |
| `minChoices` | integer | Minimum number of units to select |
| `maxChoices` | integer | Maximum number of units to select |

Key relationships: `hasUnitVariantOption` (to `UnitVariant`)

### UnitVariant

A variant of a curriculum unit (e.g. core, foundation, higher).

| Property | Type | Description |
|---|---|---|
| `name` | string | Human-readable name |

Key relationships: `hasLessonInclusion`, `coversThread`

### LessonInclusion

A reified relationship node representing a lesson's inclusion in a unit variant at a specific sequence position.

| Property | Type | Description |
|---|---|---|
| `sequencePosition` | integer | Ordering within the parent unit variant |

Key relationships: `includesLesson` (to `Lesson`)

### Lesson

An individual curriculum lesson.

| Property | Type | Description |
|---|---|---|
| `name` | string | Human-readable lesson title |
| `whyThisWhyNow` | string | Pedagogical rationale |

Key relationships: `coversKeyword`, `hasQuiz`

### Thread

A thematic strand that runs across unit variants.

| Property | Type | Description |
|---|---|---|
| `name` | string | Thread name |

### Keyword

A curriculum vocabulary item.

| Property | Type | Description |
|---|---|---|
| `name` | string | The keyword term |

### ExternalReference

A stub node representing a URI from the national curriculum repository that is referenced by Oak data but whose full definition lives in a separate repository.

| Property | Type | Description |
|---|---|---|
| `namespace` | string | Either `"nat-data-2014"` or `"nat-data-2028"` |

See [ExternalReference Stubs](#externalreference-stubs) below.

---

## Inclusion Nodes: Why They Exist

`LessonInclusion`, `UnitVariantInclusion`, and `UnitVariantChoice` are reified relationship nodes — they exist because the Oak Curriculum Ontology needs to attach metadata (specifically `sequencePosition`, `minChoices`, `maxChoices`) to what would otherwise be a plain edge.

For example, a `Programme` does not simply `hasLesson` a `Lesson`. It `hasUnitVariantInclusion` an `UnitVariantInclusion` node, which in turn `includesUnitVariant` a `UnitVariant`, which `hasLessonInclusion` a `LessonInclusion` node, which `includesLesson` a `Lesson`. The `sequencePosition` on each inclusion node records the ordering.

```
Programme
  --[hasUnitVariantInclusion]--> UnitVariantInclusion {sequencePosition: 1}
    --[includesUnitVariant]--> UnitVariant
      --[hasLessonInclusion]--> LessonInclusion {sequencePosition: 1}
        --[includesLesson]--> Lesson
```

This structure is preserved faithfully in the JSONL format. If you want a flattened view (direct Programme → Lesson edges), you can derive it in your graph database or via Cypher/Gremlin queries after import.

---

## ExternalReference Stubs

### Background

The national curriculum data (`nat-data-2014`, `nat-data-2028`) lives in a separate repository. The Oak Curriculum data references these URIs (e.g. a `Programme` `coversYearGroup` a national curriculum `YearGroup`), but the full definitions of those nodes are not present in this repository.

Property graph databases require both endpoints of a relationship to exist as nodes. To preserve these edges, the JSONL export includes stub nodes for all referenced national curriculum URIs:

```json
{
  "id": "https://w3id.org/uk/curriculum/nat-data-2014/year-group-1",
  "labels": ["ExternalReference"],
  "properties": {"namespace": "nat-data-2014"}
}
```

This is consistent with how the RDF distributions handle these references — they include the pointer, just not the definition.

### Cross-repo join

When the national curriculum repository produces its own JSONL export using the same URI-based node ID scheme, a consumer can concatenate both sets of files:

```bash
cat oak-nodes.jsonl national-curriculum-nodes.jsonl > combined-nodes.jsonl
cat oak-relationships.jsonl national-curriculum-relationships.jsonl > combined-relationships.jsonl
```

A graph database import deduplicates by `id`. The full typed national curriculum entries supersede the `ExternalReference` stubs, producing a single fully-connected knowledge graph.

---

## Example: Neo4j Import via APOC

With [APOC](https://neo4j.com/labs/apoc/) installed, import nodes and relationships from files placed in the Neo4j import directory:

```cypher
// Import nodes
CALL apoc.load.jsonArray('file:///nodes.jsonl') YIELD value AS row
CALL apoc.create.node(row.labels, row.properties { .*, id: row.id })
YIELD node
RETURN count(node) AS nodeCount;

// Import relationships
CALL apoc.load.jsonArray('file:///relationships.jsonl') YIELD value AS row
MATCH (s {id: row.startNodeId}), (e {id: row.endNodeId})
CALL apoc.create.relationship(s, row.type, row.properties, e)
YIELD rel
RETURN count(rel) AS relCount;
```

Create an index on `id` before importing for performance:

```cypher
CREATE INDEX node_id IF NOT EXISTS FOR (n:Programme) ON (n.id);
```

Or a universal index across all labels (Neo4j 5+):

```cypher
CREATE LOOKUP INDEX node_lookup IF NOT EXISTS FOR (n) ON EACH labels(n);
```

---

## Example: Filter by Node Type Using `jq`

```bash
# All Programme nodes
jq 'select(.labels | contains(["Programme"]))' distributions/nodes.jsonl

# All hasUnitVariantInclusion relationships
jq 'select(.type == "hasUnitVariantInclusion")' distributions/relationships.jsonl

# All ExternalReference stubs from nat-data-2014
jq 'select(.labels == ["ExternalReference"] and .properties.namespace == "nat-data-2014")' distributions/nodes.jsonl

# Count nodes by label (first label only)
jq -r '.labels[0]' distributions/nodes.jsonl | sort | uniq -c | sort -rn

# Count relationships by type
jq -r '.type' distributions/relationships.jsonl | sort | uniq -c | sort -rn
```
