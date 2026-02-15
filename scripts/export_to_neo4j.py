#!/usr/bin/env python3
"""
Export RDF/TTL curriculum data to Neo4j AuraDB using rdflib-neo4j.

Configuration file specifies which data to export and how to transform it.

"""

import os
import sys
import re
import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from contextlib import contextmanager
from abc import ABC, abstractmethod

from rdflib import Graph, Namespace, URIRef, BNode
from rdflib.collection import Collection
from rdflib_neo4j import Neo4jStoreConfig, Neo4jStore, HANDLE_VOCAB_URI_STRATEGY
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# PYDANTIC MODELS - Configuration Validation
# ============================================================================

class LabelMappingConfig(BaseModel):
    """Configuration for replacing node labels."""
    source_label: str = "Resource"
    target_label: str = "Oak"
    uri_pattern: str
    description: Optional[str] = None


class FileDiscoveryConfig(BaseModel):
    """Configuration for discovering TTL files to import."""
    base_dir: str = "data/oak-curriculum"
    include_files: List[str] = []
    include_patterns: List[str] = []
    exclude_patterns: List[str] = ["**/versions/**"]


class FilterConfig(BaseModel):
    """Configuration for filtering RDF triples."""
    exclude_entities_by_type: List[str] = []
    exclude_properties_by_type: Dict[str, List[str]] = {}
    exclude_predicates: List[str] = []  # Predicates to exclude globally (e.g., "broader")


class RDFSourceConfig(BaseModel):
    """Configuration for RDF data source."""
    namespaces: Dict[str, str]
    file_discovery: FileDiscoveryConfig
    filters: FilterConfig = FilterConfig()


class Neo4jConnectionConfig(BaseModel):
    """Configuration for Neo4j connection."""
    database: str = "neo4j"
    batching: bool = True
    batch_size: int = 5000  # Number of triples per batch (default: 5000)


class ConditionalRelationshipMapping(BaseModel):
    """Conditional relationship mapping based on target node label."""
    when_target_label: str
    new_type: str


class InclusionFlatteningConfig(BaseModel):
    """Configuration for flattening inclusion nodes."""
    description: str
    inclusion_node_label: str
    source_node_label: str
    target_node_label: str
    relationship_type: str
    relationship_property_mappings: Dict[str, str] = {}
    copy_target_properties: Dict[str, str] = {}


class Neo4jExportConfig(BaseModel):
    """Complete configuration for Neo4j export."""
    model_config = {"extra": "allow"}  # Allow extra fields like _notes

    rdf_source: RDFSourceConfig
    neo4j_connection: Neo4jConnectionConfig = Neo4jConnectionConfig()
    label_mapping: Union[LabelMappingConfig, List[LabelMappingConfig]] = Field(validation_alias="label_mappings")
    remove_labels: List[str] = []  # Labels to remove from main_label nodes
    uri_slug_extraction: Dict[str, str] = {}
    property_mappings: Dict[str, Dict[str, str]] = {}
    multi_valued_properties: Dict[str, List[str]] = {}  # Node type -> list of array properties
    extract_object_uris_as_properties: Dict[str, Dict[str, str]] = {}  # Node type -> {predicate: property_name}
    relationship_type_mappings: Dict[str, Union[str, List[ConditionalRelationshipMapping]]] = {}
    reverse_relationships: Dict[str, str] = {}
    inclusion_flattening: List[InclusionFlatteningConfig] = []


# ============================================================================
# CONFIGURATION LOADER
# ============================================================================

class ExportConfig:
    """Manages configuration loading and environment variables."""

    def __init__(self, config_path: Path, env_path: Optional[Path] = None):
        """
        Load configuration from JSON file and environment.

        Args:
            config_path: Path to JSON configuration file
            env_path: Optional path to .env file
        """
        self.config_path = config_path
        self.env_path = env_path or config_path.parent.parent / ".env"

        # Load environment
        load_dotenv(self.env_path)

        # Load and validate config
        with open(config_path, 'r') as f:
            config_dict = json.load(f)

        self.config = Neo4jExportConfig(**config_dict)

        # Load Neo4j credentials from environment
        self.neo4j_uri = os.getenv("NEO4J_URI")
        self.neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD")
        self.neo4j_database = os.getenv("NEO4J_DATABASE", self.config.neo4j_connection.database)

        if not self.neo4j_uri or not self.neo4j_password:
            raise ValueError("NEO4J_URI and NEO4J_PASSWORD must be set in .env file")

    def get_auth_data(self) -> Dict[str, str]:
        """Get Neo4j authentication data."""
        return {
            'uri': self.neo4j_uri,
            'database': self.neo4j_database,
            'user': self.neo4j_username,
            'pwd': self.neo4j_password
        }


# ============================================================================
# RDF LOADER
# ============================================================================

class RDFLoader:
    """Handles TTL file discovery, loading, and filtering."""

    def __init__(self, config: RDFSourceConfig, project_root: Path, export_config: 'Neo4jExportConfig' = None):
        """
        Initialize RDF loader.

        Args:
            config: RDF source configuration
            project_root: Project root directory
            export_config: Full export config (for multi-valued properties and slug extraction)
        """
        self.config = config
        self.export_config = export_config
        self.project_root = project_root
        self.data_dir = project_root / config.file_discovery.base_dir

        # Create namespace objects from config
        self.namespaces = {}
        for prefix, uri in config.namespaces.items():
            self.namespaces[prefix] = Namespace(uri)

        # Keep shortcuts for commonly used namespaces
        self.OWL = self.namespaces.get('owl', Namespace("http://www.w3.org/2002/07/owl#"))
        self.RDF = self.namespaces.get('rdf', Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#"))

    def _resolve_rdf_type(self, graph: Graph, node_label: str) -> Optional[URIRef]:
        """
        Find RDF type URI for a given node label by trying all namespaces.

        Eliminates repeated namespace resolution pattern.
        """
        for prefix, ns in self.namespaces.items():
            type_uri = ns[node_label]
            if list(graph.subjects(self.RDF.type, type_uri)):
                return type_uri
        return None

    def _resolve_predicate(self, graph: Graph, property_name: str) -> Optional[URIRef]:
        """
        Find predicate URI for a given property name by trying all namespaces.

        Eliminates repeated namespace resolution pattern.
        """
        for prefix, ns in self.namespaces.items():
            pred_uri = ns[property_name]
            if (None, pred_uri, None) in graph:
                return pred_uri
        return None

    def discover_files(self) -> List[Path]:
        """
        Discover TTL files based on configuration.

        Processes include_files and include_patterns in order, allowing
        interleaving of specific files and glob patterns. This ensures
        correct import order when relationships depend on nodes from earlier files.

        Returns:
            List of paths to TTL files (in discovery order)
        """
        ttl_files = []

        # Process include_files first (in order)
        for file in self.config.file_discovery.include_files:
            file_path = self.data_dir / file
            if file_path.exists():
                ttl_files.append(file_path)
            else:
                logger.warning(f"File not found: {file}")

        # Process include_patterns (in order)
        for pattern in self.config.file_discovery.include_patterns:
            # Use glob directly on the data_dir
            # Supports both ** (recursive) and * (single level) patterns
            matched_files = sorted(self.data_dir.glob(pattern))

            for ttl_file in matched_files:
                # Only include .ttl files
                if ttl_file.suffix != '.ttl':
                    continue

                # Check exclude patterns
                if self._is_excluded(ttl_file):
                    continue

                # Avoid duplicates (file might already be in include_files)
                if ttl_file not in ttl_files:
                    ttl_files.append(ttl_file)

        return ttl_files

    def _is_excluded(self, file_path: Path) -> bool:
        """Check if file matches any exclude patterns."""
        for pattern in self.config.file_discovery.exclude_patterns:
            # Handle patterns like "**/versions/**"
            # Extract the key directory name from the pattern
            pattern_clean = pattern.replace("**/", "").replace("/**", "")
            if pattern_clean in file_path.parts:
                return True
        return False

    def load_and_filter(self, ttl_file: Path) -> tuple[Graph, int, int, Dict, Dict, Dict, Dict, List[tuple]]:
        """
        Load TTL file and filter out unwanted triples.

        Args:
            ttl_file: Path to TTL file

        Returns:
            Tuple of (filtered_graph, original_count, filtered_count)
        """
        # Parse TTL file
        graph = Graph()
        graph.parse(ttl_file, format="turtle")
        original_count = len(graph)

        filtered_count = 0

        # CRITICAL: Extract multi-valued properties BEFORE filtering
        # RDF lists use rdf:first/rdf:rest which are filtered out later
        multi_valued_data = self._extract_multi_valued_properties(graph)

        # Filter 1: Remove entities by type
        for subject_type in self.config.filters.exclude_entities_by_type:
            # Parse namespace prefix (e.g., "owl:Ontology")
            if ":" in subject_type:
                prefix, local_name = subject_type.split(":", 1)
                if prefix in self.namespaces:
                    type_uri = self.namespaces[prefix][local_name]
                else:
                    logger.warning(f"Unknown namespace prefix '{prefix}' in filter '{subject_type}' - skipping")
                    continue
            else:
                type_uri = URIRef(subject_type)

            # Find subjects of this type
            subjects_to_remove = set(graph.subjects(self.RDF.type, type_uri))

            # Remove all triples with these subjects
            for subject in subjects_to_remove:
                triples_to_remove = list(graph.triples((subject, None, None)))
                for triple in triples_to_remove:
                    graph.remove(triple)
                    filtered_count += 1

        # Filter 2: Remove specific properties from specific node types
        for node_type, properties_to_exclude in self.config.filters.exclude_properties_by_type.items():
            # Parse node type
            if ":" in node_type:
                prefix, local_name = node_type.split(":", 1)
                if prefix in self.namespaces:
                    type_uri = self.namespaces[prefix][local_name]
                else:
                    logger.warning(f"Unknown namespace prefix '{prefix}' in property filter '{node_type}' - skipping")
                    continue
            else:
                type_uri = URIRef(node_type)

            # Find all subjects of this type
            subjects_of_type = set(graph.subjects(self.RDF.type, type_uri))

            # For each property to exclude
            for prop_to_exclude in properties_to_exclude:
                # Parse property predicate
                if ":" in prop_to_exclude:
                    prop_prefix, prop_local = prop_to_exclude.split(":", 1)
                    if prop_prefix in self.namespaces:
                        property_uri = self.namespaces[prop_prefix][prop_local]
                    else:
                        logger.warning(f"Unknown namespace prefix '{prop_prefix}' in property '{prop_to_exclude}' - skipping")
                        continue
                else:
                    property_uri = URIRef(prop_to_exclude)

                # Remove triples with this property for subjects of this type
                for subject in subjects_of_type:
                    triples_to_remove = list(graph.triples((subject, property_uri, None)))
                    for triple in triples_to_remove:
                        graph.remove(triple)
                        filtered_count += 1

        # Filter 3: Remove specific predicates globally
        for predicate_to_exclude in self.config.filters.exclude_predicates:
            # Parse namespace prefix (e.g., "skos:broader")
            if ":" in predicate_to_exclude:
                prefix, local_name = predicate_to_exclude.split(":", 1)
                if prefix in self.namespaces:
                    predicate_uri = self.namespaces[prefix][local_name]
                else:
                    logger.warning(f"Unknown namespace prefix '{prefix}' in predicate filter '{predicate_to_exclude}' - skipping")
                    continue
            else:
                predicate_uri = URIRef(predicate_to_exclude)

            # Remove all triples with this predicate
            triples_to_remove = list(graph.triples((None, predicate_uri, None)))
            for triple in triples_to_remove:
                graph.remove(triple)
                filtered_count += 1

        # Normalize text literals (remove line breaks and extra whitespace)
        self._normalize_text_literals(graph)

        # Extract slugs and object URI properties during loading
        # (multi_valued_data already extracted before filtering)
        slug_data = self._extract_slugs(graph)
        uri_property_data = self._extract_object_uri_properties(graph)

        # Extract RDF types for all nodes (to add as Neo4j labels later)
        rdf_types_data = self._extract_rdf_types(graph)

        # Extract external relationships (to prevent rdflib-neo4j from creating Resource nodes)
        external_relationships = self._extract_external_relationships(graph)

        return graph, original_count, filtered_count, multi_valued_data, slug_data, uri_property_data, rdf_types_data, external_relationships

    def _normalize_text_literals(self, graph: Graph):
        """Normalize text literals by removing excess whitespace and line breaks."""
        from rdflib import Literal

        def clean_text(text: str) -> str:
            """Clean a single text string."""
            # Replace line breaks and tabs with spaces
            text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
            # Collapse multiple spaces into one
            text = re.sub(r'\s+', ' ', text)
            # Trim leading/trailing whitespace
            return text.strip()

        # Find all triples with literal objects that need cleaning
        triples_to_update = []
        for s, p, o in graph:
            if isinstance(o, Literal) and isinstance(o.value, str):
                if '\n' in o or '\r' in o or '\t' in o or '  ' in o:
                    cleaned = clean_text(str(o))
                    # Preserve language tag if present
                    new_literal = Literal(cleaned, lang=o.language) if o.language else Literal(cleaned)
                    triples_to_update.append((s, p, o, new_literal))

        # Update the graph
        for s, p, old_o, new_o in triples_to_update:
            graph.remove((s, p, old_o))
            graph.add((s, p, new_o))

    def _extract_multi_valued_properties(self, graph: Graph) -> Dict[str, Dict[str, List[str]]]:
        """
        Extract RDF lists and convert them to Neo4j array properties.

        RDF lists use the Turtle syntax: curric:aims ( "value1" "value2" "value3" )
        This is serialized as blank nodes with rdf:first/rdf:rest predicates.

        This method extracts all values from configured RDF list properties and
        returns them as Python lists for Neo4j array storage.

        Also removes these triples from the graph to prevent rdflib-neo4j from
        creating duplicate/incorrect properties when the list structure is later
        destroyed by filtering out rdf:first/rdf:rest predicates.

        Returns:
            Dict mapping node_label -> {property_name: {uri: [values]}}
        """
        if not self.export_config or not self.export_config.multi_valued_properties:
            return {}

        multi_valued_data = {}
        triples_to_remove = []

        for node_label, properties in self.export_config.multi_valued_properties.items():
            type_uri = self._resolve_rdf_type(graph, node_label)
            if not type_uri:
                continue

            subjects = set(graph.subjects(self.RDF.type, type_uri))

            for prop in properties:
                predicate = self._resolve_predicate(graph, prop)
                if not predicate:
                    continue

                # Extract RDF list values for each subject
                prop_data = {}
                for subject in subjects:
                    for obj in graph.objects(subject, predicate):
                        # Object should be an RDF list (blank node with rdf:first)
                        if isinstance(obj, BNode) and (obj, self.RDF.first, None) in graph:
                            try:
                                # Extract all members from the RDF list
                                values = [str(item) for item in Collection(graph, obj)]
                                prop_data[str(subject)] = values

                                # Mark main triple for removal
                                # The blank node structure (rdf:first/rdf:rest) will be removed
                                # by the predicate filtering step that happens later
                                triples_to_remove.append((subject, predicate, obj))

                                logger.debug(f"  Extracted RDF list for {subject} {prop}: {len(values)} items")
                            except Exception as e:
                                logger.warning(f"Could not parse RDF list for {subject} property {prop}: {e}")
                        else:
                            logger.warning(f"Property {prop} for {subject} is not an RDF list - skipping")

                if prop_data:
                    if node_label not in multi_valued_data:
                        multi_valued_data[node_label] = {}
                    multi_valued_data[node_label][prop] = prop_data

        # Remove the extracted triples from the graph
        for triple in triples_to_remove:
            graph.remove(triple)

        if triples_to_remove:
            logger.info(f"  Extracted and removed {len(triples_to_remove)} multi-valued property triples to prevent duplicates")

        return multi_valued_data

    def _extract_slugs(self, graph: Graph) -> Dict[str, Dict[str, str]]:
        """
        Extract URI slugs for configured node types.

        Returns:
            Dict mapping node_label -> {uri: slug}
        """
        if not self.export_config or not self.export_config.uri_slug_extraction:
            return {}

        slug_data = {}

        for node_label, slug_property in self.export_config.uri_slug_extraction.items():
            type_uri = self._resolve_rdf_type(graph, node_label)
            if not type_uri:
                continue

            # Find all subjects of this type and extract slugs
            subjects = set(graph.subjects(self.RDF.type, type_uri))
            slug_data[node_label] = {
                str(subject): str(subject).split('/')[-1]
                for subject in subjects
            }

        return slug_data

    def _extract_object_uri_properties(self, graph: Graph) -> Dict[str, Dict[str, Dict[str, str]]]:
        """
        Extract object URIs from specific predicates to be set as properties.
        Also removes these triples from the graph.

        Returns:
            Dict mapping node_label -> {property_name: {subject_uri: object_uri}}
        """
        if not self.export_config or not self.export_config.extract_object_uris_as_properties:
            return {}

        uri_property_data = {}
        triples_to_remove = []

        for node_label, predicate_mappings in self.export_config.extract_object_uris_as_properties.items():
            type_uri = self._resolve_rdf_type(graph, node_label)
            if not type_uri:
                continue

            subjects = set(graph.subjects(self.RDF.type, type_uri))

            for predicate_name, property_name in predicate_mappings.items():
                predicate = self._resolve_predicate(graph, predicate_name)
                if not predicate:
                    continue

                # Extract object URIs for each subject
                prop_data = {}
                for subject in subjects:
                    for obj in graph.objects(subject, predicate):
                        # Store the object URI as a string
                        prop_data[str(subject)] = str(obj)
                        # Mark triple for removal
                        triples_to_remove.append((subject, predicate, obj))

                if prop_data:
                    if node_label not in uri_property_data:
                        uri_property_data[node_label] = {}
                    uri_property_data[node_label][property_name] = prop_data

        # Remove the extracted triples from the graph
        for triple in triples_to_remove:
            graph.remove(triple)

        return uri_property_data

    def _extract_rdf_types(self, graph: Graph) -> Dict[str, str]:
        """
        Extract RDF types for all nodes.
        Returns mapping of {uri: type_label} where type_label is the class name (e.g., "Scheme", "Programme").

        This allows us to add type-based labels in Neo4j for nodes using external ontology classes,
        since rdflib-neo4j only creates labels for local ontology types.
        """
        rdf_types = {}

        # Get all rdf:type triples
        for subject, predicate, obj in graph.triples((None, self.RDF.type, None)):
            # Skip owl:Ontology and other non-entity types
            if obj in [self.OWL.Ontology, self.OWL.Class, self.OWL.ObjectProperty, self.OWL.DatatypeProperty]:
                continue

            subject_uri = str(subject)
            type_uri = str(obj)

            # Extract the class name from the type URI
            # e.g., "https://w3id.org/uk/curriculum/core/Scheme" → "Scheme"
            # e.g., "https://w3id.org/uk/curriculum/oak-ontology/Programme" → "Programme"
            type_label = type_uri.split('/')[-1].split('#')[-1]

            # Store the mapping
            rdf_types[subject_uri] = type_label

        logger.info(f"  Extracted RDF types for {len(rdf_types)} nodes")
        return rdf_types

    def _extract_external_relationships(self, graph: Graph) -> List[tuple]:
        """
        Extract relationships to external (non-Oak) resources.
        These will be recreated after import to connect to pre-existing external nodes.

        Automatically detects ALL predicates where the object is in an external namespace
        (eng:, curric:, etc.) rather than hard-coding predicate names.

        Note: Excludes rdf:type predicates - these define node types (classes) not relationships.
        rdflib-neo4j handles types specially by converting them to Neo4j labels.

        Returns:
            List of tuples: (subject_uri, predicate_uri, object_uri)
        """
        external_rels = []
        triples_to_remove = []

        # Define external namespaces (not Oak-owned data)
        external_namespaces = [
            'https://w3id.org/uk/curriculum/england/',  # eng: namespace
            'https://w3id.org/uk/curriculum/core/',     # curric: namespace
        ]

        # Iterate through ALL triples and find those pointing to external resources
        for s, p, o in graph:
            # Skip rdf:type predicates - these define node types (classes), not relationships
            # rdflib-neo4j handles types by converting them to Neo4j labels
            if p == self.RDF.type:
                continue

            # Only process URIRef objects (not literals)
            if isinstance(o, URIRef):
                obj_str = str(o)

                # Check if object is in an external namespace
                is_external = any(obj_str.startswith(ns) for ns in external_namespaces)

                # Check if subject is Oak data (not external)
                subj_str = str(s)
                is_oak_subject = subj_str.startswith('https://w3id.org/uk/curriculum/oak-data')

                # Extract if: Oak subject → external object
                if is_oak_subject and is_external:
                    external_rels.append((subj_str, str(p), obj_str))
                    triples_to_remove.append((s, p, o))

        # Remove from graph so rdflib-neo4j doesn't create Resource nodes
        removed_count = 0
        for triple in triples_to_remove:
            graph.remove(triple)
            removed_count += 1

        if external_rels:
            logger.info(f"✓ Extracted and removed {len(external_rels)} external relationships from graph")
            logger.info(f"  Removed {removed_count} triples to prevent Resource node creation")
        else:
            logger.info(f"No external relationships found in this file")

        return external_rels


# ============================================================================
# NEO4J CONNECTION
# ============================================================================

class Neo4jConnection:
    """Context manager for Neo4j RDF store connection (rdflib-neo4j only)."""

    def __init__(self, auth_data: Dict[str, str], custom_prefixes: Dict[str, str], config: Neo4jConnectionConfig):
        """
        Initialize Neo4j RDF store connection.

        Args:
            auth_data: Neo4j authentication dictionary
            custom_prefixes: RDF namespace prefixes
            config: Neo4j connection configuration
        """
        self.auth_data = auth_data
        self.custom_prefixes = custom_prefixes
        self.config = config
        self.store = None
        self.graph = None

    def __enter__(self):
        """Open Neo4j RDF store."""
        # Create rdflib-neo4j store
        store_config = Neo4jStoreConfig(
            auth_data=self.auth_data,
            custom_prefixes=self.custom_prefixes,
            handle_vocab_uri_strategy=HANDLE_VOCAB_URI_STRATEGY.MAP,
            batching=self.config.batching
        )

        self.store = Neo4jStore(config=store_config)
        self.graph = Graph(store=self.store, identifier=self.auth_data['uri'])

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close Neo4j RDF store."""
        if self.store:
            self.store.close()

    def commit(self):
        """Commit RDF graph changes."""
        if self.graph:
            self.graph.commit()


# ============================================================================
# TRANSFORMATION ARCHITECTURE
# ============================================================================

class Transformation(ABC):
    """
    Abstract base class for all Neo4j transformations.

    Each transformation is a separate class following the Strategy pattern.
    This makes transformations:
    - Easy to test independently
    - Easy to add/remove without modifying existing code
    - Reusable in different contexts
    - Configuration-driven
    """

    @abstractmethod
    def name(self) -> str:
        """Return human-readable name for logging."""
        pass

    @abstractmethod
    def should_run(self, config: Neo4jExportConfig) -> bool:
        """Check if transformation should run based on config."""
        pass

    @abstractmethod
    def execute(self, session, config: Neo4jExportConfig, main_labels: List[str], **data) -> int:
        """
        Execute transformation.

        Args:
            session: Neo4j session
            config: Export configuration
            main_labels: List of main node labels (e.g., ['OakCurric', 'NatCurric'])
            **data: Additional data (slug_data, multi_valued_data, etc.)

        Returns:
            Count of affected nodes
        """
        pass


class LabelMappingTransformation(Transformation):
    """Replace source labels with target labels for nodes matching URI pattern."""

    def name(self) -> str:
        return "Label Mapping"

    def should_run(self, config: Neo4jExportConfig) -> bool:
        return config.label_mapping is not None

    def execute(self, session, config: Neo4jExportConfig, main_labels: List[str], **data) -> int:
        # Handle both single label mapping and list of label mappings
        label_configs = config.label_mapping if isinstance(config.label_mapping, list) else [config.label_mapping]

        total_count = 0
        for label_config in label_configs:
            source_label = label_config.source_label
            target_label = label_config.target_label
            uri_pattern = label_config.uri_pattern

            result = session.run(f"""
                MATCH (n:{source_label})
                WHERE n.uri STARTS WITH $pattern
                SET n:{target_label}
                REMOVE n:{source_label}
                RETURN count(n) as count
            """, pattern=uri_pattern)

            record = result.single()
            count = record["count"] if record else 0

            if count > 0:
                logger.info(f"✓ Relabeled {count} nodes: {source_label} → {target_label} (pattern: {uri_pattern[:50]}...)")

            total_count += count

        return total_count


class RemoveLabelsTransformation(Transformation):
    """Remove unwanted labels from main label nodes."""

    def name(self) -> str:
        return "Remove Unwanted Labels"

    def should_run(self, config: Neo4jExportConfig) -> bool:
        return bool(config.remove_labels)

    def execute(self, session, config: Neo4jExportConfig, main_labels: List[str], **data) -> int:
        total_removed = 0
        for main_label in main_labels:
            for label_to_remove in config.remove_labels:
                result = session.run(f"""
                    MATCH (n:{main_label}:{label_to_remove})
                    REMOVE n:{label_to_remove}
                    RETURN count(n) as count
                """)
                record = result.single()
                count = record["count"] if record else 0
                if count > 0:
                    logger.info(f"✓ Removed '{label_to_remove}' label from {count} {main_label} nodes")
                    total_removed += count

        return total_removed


class SlugExtractionTransformation(Transformation):
    """Apply pre-extracted URI slugs to nodes.

    Optimized: Batches all slug extractions into a single query using UNWIND with
    node label and property name included in the data.
    """

    def name(self) -> str:
        return "Slug Extraction"

    def should_run(self, config: Neo4jExportConfig) -> bool:
        return bool(config.uri_slug_extraction)

    def execute(self, session, config: Neo4jExportConfig, main_labels: List[str], **data) -> int:
        slug_data = data.get('slug_data', {})
        if not slug_data:
            return 0

        # Consolidate all slug data with their target property names
        # We still need separate queries per node type because SET n.{property} can't be parameterized
        # But we batch all URIs for each node type into one query

        total_slugs = 0
        node_types_processed = []

        for main_label in main_labels:
            for node_label, uri_slug_map in slug_data.items():
                slug_property = config.uri_slug_extraction.get(node_label)
                if not slug_property or not uri_slug_map:
                    continue

                # Batch all URIs for this node type
                batch_data = [{"uri": uri, "slug": slug} for uri, slug in uri_slug_map.items()]

                result = session.run(f"""
                    UNWIND $data AS item
                    MATCH (n:{node_label}:{main_label})
                    WHERE n.uri = item.uri
                    SET n.{slug_property} = item.slug
                    RETURN count(n) as count
                """, data=batch_data)

                record = result.single()
                count = record["count"] if record else 0
                if count > 0:
                    node_types_processed.append(f"{node_label}:{main_label}({count})")
                    total_slugs += count

        if node_types_processed:
            logger.info(f"✓ Applied slugs: {', '.join(node_types_processed)}")

        return total_slugs


class ObjectUriPropertyTransformation(Transformation):
    """Apply pre-extracted object URI properties to nodes."""

    def name(self) -> str:
        return "Object URI Properties"

    def should_run(self, config: Neo4jExportConfig) -> bool:
        return bool(config.extract_object_uris_as_properties)

    def execute(self, session, config: Neo4jExportConfig, main_labels: List[str], **data) -> int:
        uri_property_data = data.get('uri_property_data', {})
        if not uri_property_data:
            return 0

        total_properties = 0
        for main_label in main_labels:
            for node_label, prop_data in uri_property_data.items():
                for property_name, uri_value_map in prop_data.items():
                    result = session.run(f"""
                        UNWIND $data AS item
                        MATCH (n:{node_label}:{main_label})
                        WHERE n.uri = item.uri
                        SET n.{property_name} = item.value
                        RETURN count(n) as count
                    """, data=[{"uri": uri, "value": value} for uri, value in uri_value_map.items()])

                    record = result.single()
                    count = record["count"] if record else 0
                    if count > 0:
                        logger.info(f"✓ {node_label}:{main_label}.{property_name} set ({count} nodes)")
                        total_properties += count

        return total_properties


class PropertyMappingTransformation(Transformation):
    """Rename properties based on node type.

    Optimized: Consolidates all property mappings for a node type into a single query.
    """

    def name(self) -> str:
        return "Property Mapping"

    def should_run(self, config: Neo4jExportConfig) -> bool:
        return bool(config.property_mappings)

    def execute(self, session, config: Neo4jExportConfig, main_labels: List[str], **data) -> int:
        total_renamed = 0

        for main_label in main_labels:
            for node_label, mappings in config.property_mappings.items():
                if not mappings:
                    continue

                # Build consolidated SET and REMOVE clauses for all properties
                set_clauses = []
                remove_clauses = []
                where_clauses = []

                for old_prop, new_prop in mappings.items():
                    set_clauses.append(f"n.{new_prop} = n.{old_prop}")
                    remove_clauses.append(f"n.{old_prop}")
                    where_clauses.append(f"n.{old_prop} IS NOT NULL")

                # Combined query: rename all properties for this node type in one go
                # Use CASE to handle properties that may not exist on all nodes
                query = f"""
                    MATCH (n:{node_label}:{main_label})
                    WHERE {" OR ".join(where_clauses)}
                    SET {", ".join(set_clauses)}
                    REMOVE {", ".join(remove_clauses)}
                    RETURN count(n) as count
                """

                result = session.run(query)
                record = result.single()
                count = record["count"] if record else 0

                if count > 0:
                    props_str = ", ".join([f"'{old}'→'{new}'" for old, new in mappings.items()])
                    logger.info(f"✓ {node_label}:{main_label}: {props_str} ({count} nodes)")
                    total_renamed += count

        return total_renamed


class MultiValuedPropertiesTransformation(Transformation):
    """Apply pre-extracted multi-valued properties as arrays."""

    def name(self) -> str:
        return "Multi-Valued Properties"

    def should_run(self, config: Neo4jExportConfig) -> bool:
        return bool(config.multi_valued_properties)

    def execute(self, session, config: Neo4jExportConfig, main_labels: List[str], **data) -> int:
        multi_valued_data = data.get('multi_valued_data', {})
        if not multi_valued_data:
            return 0

        total_consolidated = 0
        for main_label in main_labels:
            for node_label, prop_data in multi_valued_data.items():
                for prop, uri_values_map in prop_data.items():
                    result = session.run(f"""
                        UNWIND $data AS item
                        MATCH (n:{node_label}:{main_label})
                        WHERE n.uri = item.uri
                        SET n.{prop} = item.values
                        RETURN count(n) as count
                    """, data=[{"uri": uri, "values": values} for uri, values in uri_values_map.items()])

                    record = result.single()
                    count = record["count"] if record else 0
                    if count > 0:
                        logger.info(f"✓ {node_label}:{main_label}.{prop} consolidated ({count} nodes)")
                        total_consolidated += count

        return total_consolidated


class RelationshipTypeMappingTransformation(Transformation):
    """Rename relationship types."""

    def name(self) -> str:
        return "Relationship Type Mapping"

    def should_run(self, config: Neo4jExportConfig) -> bool:
        return bool(config.relationship_type_mappings)

    def execute(self, session, config: Neo4jExportConfig, main_labels: List[str], **data) -> int:
        total_renamed = 0

        for old_type, mapping in config.relationship_type_mappings.items():
            # Case 1: Simple string mapping (backward compatible)
            if isinstance(mapping, str):
                new_type = mapping
                result = session.run(f"""
                    MATCH (a)-[old:{old_type}]->(b)
                    CREATE (a)-[new:{new_type}]->(b)
                    SET new = properties(old)
                    WITH old, count(*) as count
                    DELETE old
                    RETURN count
                """)
                record = result.single()
                count = record["count"] if record else 0
                if count > 0:
                    logger.info(f"✓ '{old_type}' → '{new_type}' ({count} relationships)")
                    total_renamed += count

            # Case 2: Conditional mapping based on target label
            elif isinstance(mapping, list):
                for condition in mapping:
                    target_label = condition.when_target_label
                    new_type = condition.new_type

                    result = session.run(f"""
                        MATCH (a)-[old:{old_type}]->(b:{target_label})
                        CREATE (a)-[new:{new_type}]->(b)
                        SET new = properties(old)
                        WITH old, count(*) as count
                        DELETE old
                        RETURN count
                    """)
                    record = result.single()
                    count = record["count"] if record else 0
                    if count > 0:
                        logger.info(f"✓ '{old_type}' → '{new_type}' (target: {target_label}, {count} relationships)")
                        total_renamed += count

        return total_renamed


class ReverseRelationshipsTransformation(Transformation):
    """Reverse relationship directions."""

    def name(self) -> str:
        return "Reverse Relationships"

    def should_run(self, config: Neo4jExportConfig) -> bool:
        return bool(config.reverse_relationships)

    def execute(self, session, config: Neo4jExportConfig, main_labels: List[str], **data) -> int:
        total_reversed = 0
        for old_type, new_type in config.reverse_relationships.items():
            result = session.run(f"""
                MATCH (a)-[old:{old_type}]->(b)
                CREATE (b)-[new:{new_type}]->(a)
                SET new = properties(old)
                WITH old, count(*) as count
                DELETE old
                RETURN count
            """)
            record = result.single()
            count = record["count"] if record else 0
            if count > 0:
                logger.info(f"✓ Reversed '{old_type}' → '{new_type}' ({count} relationships)")
                total_reversed += count

        return total_reversed


class InclusionFlatteningTransformation(Transformation):
    """Flatten inclusion nodes into direct relationships."""

    def name(self) -> str:
        return "Inclusion Flattening"

    def should_run(self, config: Neo4jExportConfig) -> bool:
        return bool(config.inclusion_flattening)

    def execute(self, session, config: Neo4jExportConfig, main_labels: List[str], **data) -> int:
        total_flattened = 0

        for flattening_config in config.inclusion_flattening:
            inclusion_label = flattening_config.inclusion_node_label
            source_label = flattening_config.source_node_label
            target_label = flattening_config.target_node_label
            rel_type = flattening_config.relationship_type
            prop_mappings = flattening_config.relationship_property_mappings

            # Build property SET clause
            set_clauses = []
            for old_prop, new_prop in prop_mappings.items():
                set_clauses.append(f"new.{new_prop} = inclusion.{old_prop}")
            set_clause = ", ".join(set_clauses) if set_clauses else ""

            query = f"""
                MATCH (source:{source_label})-[]->(inclusion:{inclusion_label})-[]->(target:{target_label})
                CREATE (source)-[new:{rel_type}]->(target)
                {f"SET {set_clause}" if set_clause else ""}
                WITH inclusion, count(*) as count
                DETACH DELETE inclusion
                RETURN count
            """

            result = session.run(query)
            record = result.single()
            count = record["count"] if record else 0
            if count > 0:
                logger.info(f"✓ Flattened {inclusion_label} ({count} nodes)")
                total_flattened += count

        return total_flattened


class CamelCaseConversionTransformation(Transformation):
    """Convert camelCase relationship types to UPPER_CASE."""

    def name(self) -> str:
        return "CamelCase Conversion"

    def should_run(self, config: Neo4jExportConfig) -> bool:
        return True  # Always run to standardize relationship names

    def execute(self, session, config: Neo4jExportConfig, main_labels: List[str], **data) -> int:
        # Get all relationship types
        result = session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")
        rel_types = [record["relationshipType"] for record in result]

        # Find camelCase types (not already processed)
        camel_case_types = [
            rt for rt in rel_types
            if rt[0].islower() and any(c.isupper() for c in rt)
        ]

        total_converted = 0
        for old_type in camel_case_types:
            # Convert to UPPER_CASE
            new_type = re.sub(r'([a-z])([A-Z])', r'\1_\2', old_type).upper()

            result = session.run(f"""
                MATCH (a)-[old:{old_type}]->(b)
                CREATE (a)-[new:{new_type}]->(b)
                SET new = properties(old)
                WITH old, count(*) as count
                DELETE old
                RETURN count
            """)
            record = result.single()
            count = record["count"] if record else 0
            if count > 0:
                logger.info(f"✓ '{old_type}' → '{new_type}' ({count} relationships)")
                total_converted += count

        return total_converted


class CleanupOrphanedResourceNodesTransformation(Transformation):
    """Delete orphaned Resource nodes that shouldn't exist."""

    def name(self) -> str:
        return "Cleanup Orphaned Resource Nodes"

    def should_run(self, config: Neo4jExportConfig) -> bool:
        return True  # Always cleanup

    def execute(self, session, config: Neo4jExportConfig, main_labels: List[str], **data) -> int:
        # Delete nodes that have ONLY the Resource label (garbage nodes from import)
        # After transformations, all legitimate nodes should have additional labels
        result = session.run("""
            MATCH (r)
            WHERE labels(r) = ['Resource']
            DETACH DELETE r
            RETURN count(r) as count
        """)

        record = result.single()
        count = record["count"] if record else 0
        if count > 0:
            logger.info(f"✓ Deleted {count} orphaned Resource nodes (no other labels)")

        return count


class DropResourceConstraintTransformation(Transformation):
    """Drop the Resource URI constraint created by rdflib-neo4j (not needed in final graph)."""

    def name(self) -> str:
        return "Drop Resource Constraint"

    def should_run(self, config: Neo4jExportConfig) -> bool:
        return True  # Always drop

    def execute(self, session, config: Neo4jExportConfig, main_labels: List[str], **data) -> int:
        # Drop the n10s_unique_uri constraint if it exists
        try:
            session.run("DROP CONSTRAINT n10s_unique_uri IF EXISTS")
            logger.info("✓ Dropped n10s_unique_uri constraint (not needed - no Resource nodes in final graph)")
            return 1
        except Exception as e:
            logger.warning(f"Could not drop constraint: {e}")
            return 0


class AddExternalTypeLabelsTransformation(Transformation):
    """Add type-based labels for nodes using external ontology classes (e.g., curric:Scheme)."""

    def name(self) -> str:
        return "Add External Type Labels"

    def should_run(self, config: Neo4jExportConfig) -> bool:
        return True  # Always run to add missing type labels

    def execute(self, session, config: Neo4jExportConfig, main_labels: List[str], **data) -> int:
        """
        Add type labels for nodes using external ontology classes.
        rdflib-neo4j only creates labels for types in the local ontology (oakcurric:),
        not for external ontology types (curric:, eng:). This transformation uses the extracted
        RDF type information to add the appropriate labels.
        """
        rdf_types_data = data.get('rdf_types_data', {})
        if not rdf_types_data:
            logger.info("  No RDF type data available")
            return 0

        total_labeled = 0

        # Group URIs by their type label
        type_to_uris = {}
        for uri, type_label in rdf_types_data.items():
            if type_label not in type_to_uris:
                type_to_uris[type_label] = []
            type_to_uris[type_label].append(uri)

        # Add each type label to its nodes - iterate over all main labels
        for main_label in main_labels:
            for type_label, uris in type_to_uris.items():
                # Only add labels for types that aren't already added by rdflib-neo4j
                # (rdflib-neo4j adds labels for oakcurric: types like Programme, Unit, Lesson)
                # This handles external types like curric:Scheme
                result = session.run(f"""
                    UNWIND $uris AS uri
                    MATCH (n:{main_label} {{uri: uri}})
                    WHERE NOT $type_label IN labels(n)
                    SET n:{type_label}
                    RETURN count(n) as count
                """, uris=uris, type_label=type_label)

                record = result.single()
                count = record["count"] if record else 0
                if count > 0:
                    logger.info(f"✓ Added {type_label} label to {count} {main_label} nodes")
                    total_labeled += count

        return total_labeled


class ExternalRelationshipsTransformation(Transformation):
    """Create relationships to pre-existing external nodes

    Optimized for performance:
    - Pre-caches all target node labels in a single query (Option 5)
    - Batches relationships by type using UNWIND (Option 1)
    """

    def name(self) -> str:
        return "External Relationships"

    def should_run(self, config: Neo4jExportConfig) -> bool:
        return True  # Run if external relationships exist

    def _pre_cache_target_labels(self, session, target_uris: List[str]) -> Dict[str, List[str]]:
        """
        Pre-cache all target node labels in a single query.

        Args:
            session: Neo4j session
            target_uris: List of target URIs to look up

        Returns:
            Dict mapping URI to list of labels
        """
        if not target_uris:
            return {}

        # Deduplicate URIs
        unique_uris = list(set(target_uris))

        logger.info(f"  Pre-caching labels for {len(unique_uris)} unique target nodes...")

        result = session.run("""
            UNWIND $uris AS uri
            MATCH (n {uri: uri})
            WHERE NOT 'Resource' IN labels(n)
            RETURN n.uri AS uri, labels(n) AS labels
        """, uris=unique_uris)

        label_cache = {}
        for record in result:
            label_cache[record["uri"]] = record["labels"]

        logger.info(f"  ✓ Cached labels for {len(label_cache)} nodes (found in Neo4j)")

        return label_cache

    def _apply_relationship_transformations(self, predicate_name: str, config: Neo4jExportConfig,
                                            target_uri: str, label_cache: Dict[str, List[str]]) -> tuple:
        """
        Apply relationship type mappings and reversals to match config.
        Uses pre-cached labels instead of querying per relationship.

        Returns:
            Tuple of (final_rel_type, should_reverse)
        """
        # Check if this predicate should be reversed
        if predicate_name in config.reverse_relationships:
            return config.reverse_relationships[predicate_name], True

        # Check if this predicate should be renamed
        if predicate_name in config.relationship_type_mappings:
            mapping = config.relationship_type_mappings[predicate_name]

            # Handle conditional mapping
            if isinstance(mapping, list):
                # Use cached labels instead of querying
                target_labels = label_cache.get(target_uri, [])
                for condition in mapping:
                    if condition.when_target_label in target_labels:
                        return condition.new_type, False
                # No match, use original
                return predicate_name, False
            else:
                # Simple string mapping
                return mapping, False

        # No transformation needed
        return predicate_name, False

    def execute(self, session, config: Neo4jExportConfig, main_labels: List[str], **data) -> int:
        external_rels = data.get('external_relationships', [])
        if not external_rels:
            logger.info("No external relationships to create")
            return 0

        logger.info(f"Processing {len(external_rels)} external relationships...")

        # Show sample relationships
        logger.info(f"Sample relationships to create:")
        for subj, pred, obj in external_rels[:3]:
            logger.info(f"  {subj.split('/')[-1]} -[{pred.split('/')[-1]}]-> {obj.split('/')[-1]}")

        # Option 5: Pre-cache all target node labels in a single query
        target_uris = [obj for _, _, obj in external_rels]
        label_cache = self._pre_cache_target_labels(session, target_uris)

        # Group relationships by (rel_type, should_reverse) for batched execution
        # Key: (rel_type, should_reverse), Value: [(subject_uri, object_uri), ...]
        grouped_rels: Dict[tuple, List[tuple]] = {}
        missing_targets = []

        for subject_uri, predicate_uri, object_uri in external_rels:
            # Check if target exists in cache
            if object_uri not in label_cache:
                missing_targets.append(object_uri)
                continue

            # Extract predicate name from URI (e.g., "isProgrammeOf")
            predicate_name = predicate_uri.split('/')[-1].split('#')[-1]

            # Apply transformations using cached labels (no query needed)
            final_rel_type, should_reverse = self._apply_relationship_transformations(
                predicate_name, config, object_uri, label_cache
            )

            # Convert camelCase to UPPER_CASE
            final_rel_type = re.sub(r'([a-z])([A-Z])', r'\1_\2', final_rel_type).upper()

            # Group by relationship type and direction
            key = (final_rel_type, should_reverse)
            if key not in grouped_rels:
                grouped_rels[key] = []
            grouped_rels[key].append((subject_uri, object_uri))

        # Option 1: Execute batched UNWIND queries per relationship type
        created_count = 0

        for (rel_type, should_reverse), rel_pairs in grouped_rels.items():
            # Build batch data
            batch_data = [{"subject": s, "object": o} for s, o in rel_pairs]

            if should_reverse:
                # Create: (target)-[REL]->(source)
                query = f"""
                    UNWIND $batch AS rel
                    MATCH (source {{uri: rel.subject}})
                    MATCH (target {{uri: rel.object}})
                    CREATE (target)-[r:{rel_type}]->(source)
                    RETURN count(*) as count
                """
            else:
                # Create: (source)-[REL]->(target)
                query = f"""
                    UNWIND $batch AS rel
                    MATCH (source {{uri: rel.subject}})
                    MATCH (target {{uri: rel.object}})
                    CREATE (source)-[r:{rel_type}]->(target)
                    RETURN count(*) as count
                """

            try:
                result = session.run(query, batch=batch_data)
                record = result.single()
                count = record["count"] if record else 0
                created_count += count
                direction = "reversed" if should_reverse else "forward"
                logger.info(f"  ✓ Created {count} {rel_type} relationships ({direction})")
            except Exception as e:
                logger.error(f"  ✗ Failed to create {rel_type} relationships: {e}")

        if created_count > 0:
            logger.info(f"✓ Created {created_count} total relationships to external nodes")

        if missing_targets:
            unique_missing = set(missing_targets)
            logger.warning(f"⚠ Could not create {len(missing_targets)} relationships - {len(unique_missing)} unique target nodes don't exist:")
            for uri in list(unique_missing)[:5]:  # Show first 5 unique
                logger.warning(f"  - {uri}")
            if len(unique_missing) > 5:
                logger.warning(f"  ... and {len(unique_missing) - 5} more unique targets")

        return created_count


# ============================================================================
# TRANSFORMATION PIPELINE
# ============================================================================

class TransformationPipeline:
    """
    Executes transformations in order.

    This is the orchestrator that runs each transformation if applicable.
    Follows the Strategy pattern with a list of transformation strategies.
    """

    def __init__(self, driver, database: str, transformations: List[Transformation]):
        """
        Initialize pipeline.

        Args:
            driver: Neo4j driver
            database: Database name
            transformations: Ordered list of transformations to execute
        """
        self.driver = driver
        self.database = database
        self.transformations = transformations

    def _ensure_uri_index(self, session, main_labels: List[str]):
        """
        Create index on uri property for fast lookups during transformations.
        This is CRITICAL for performance - without it, URI lookups are O(n) full scans.
        """
        for main_label in main_labels:
            logger.info(f"Creating index on {main_label}.uri for fast lookups...")
            try:
                # Create index if it doesn't exist (Neo4j 4.x+ syntax)
                session.run(f"CREATE INDEX idx_{main_label.lower()}_uri IF NOT EXISTS FOR (n:{main_label}) ON (n.uri)")
                # Wait for index to be online
                session.run("CALL db.awaitIndexes(300)")
                logger.info(f"✓ Index on {main_label}.uri ready")
            except Exception as e:
                logger.warning(f"Could not create index (may already exist): {e}")

    def execute(self, config: Neo4jExportConfig, **data):
        """
        Execute all applicable transformations.

        Args:
            config: Export configuration
            **data: Additional data (slug_data, multi_valued_data, etc.)
        """
        logger.info("\n" + "=" * 60)
        logger.info("Applying transformations...")
        logger.info("=" * 60)

        # Get all main labels from label mappings
        if isinstance(config.label_mapping, list):
            main_labels = [lm.target_label for lm in config.label_mapping]
        else:
            main_labels = [config.label_mapping.target_label]

        logger.info(f"Processing nodes with labels: {', '.join(main_labels)}")

        with self.driver.session(database=self.database) as session:
            # CRITICAL: Create index on uri FIRST for fast lookups (for ALL labels)
            self._ensure_uri_index(session, main_labels)

            for transformation in self.transformations:
                if transformation.should_run(config):
                    logger.info("\n" + "=" * 60)
                    logger.info(f"Running: {transformation.name()}")

                    count = transformation.execute(session, config, main_labels, **data)

                    if count == 0:
                        logger.info(f"  No changes made")

        logger.info("\n" + "=" * 60)
        logger.info("✓ All transformations complete")

    def verify_export(self):
        """Verify export by checking node counts."""
        logger.info("\n" + "=" * 60)
        logger.info("Verifying export...")

        with self.driver.session(database=self.database) as session:
            result = session.run("MATCH (n) RETURN labels(n) as labels, count(n) as count ORDER BY count DESC")

            logger.info("\nNode counts by label:")
            for record in result:
                labels = ":".join(record["labels"])
                count = record["count"]
                logger.info(f"  {labels}: {count}")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def clear_neo4j_data(auth_data: Dict[str, str], labels: Union[str, List[str]]) -> None:
    """
    Clear all nodes with the specified label(s) from Neo4j.
    Uses batched deletion to prevent connection timeouts on large datasets.

    Args:
        auth_data: Dictionary with Neo4j connection credentials
                  (uri, database, user, pwd)
        labels: The node label(s) to clear (e.g., 'NatCurric', 'OakCurric')
    """
    # Normalize to list
    label_list = labels if isinstance(labels, list) else [labels]
    label_str = ", ".join(label_list)

    logger.info("\n" + "=" * 60)
    logger.info(f"Clearing existing {label_str} data from Neo4j...")
    logger.info("IMPORTANT: Clearing ALL labels before building new data")
    logger.info("=" * 60)

    driver = GraphDatabase.driver(
        auth_data['uri'],
        auth=(auth_data['user'], auth_data['pwd'])
    )

    try:
        with driver.session(database=auth_data['database']) as session:
            total_deleted = 0

            for label in label_list:
                # Count nodes before deletion
                count_result = session.run(
                    f"MATCH (n:{label}) RETURN count(n) as count"
                )
                count_record = count_result.single()
                node_count = count_record["count"] if count_record else 0

                if node_count == 0:
                    logger.info(f"No {label} nodes found")
                    continue

                logger.info(f"Found {node_count:,} {label} nodes to delete")
                logger.info(f"Deleting in batches to prevent connection timeout...")

                # Delete in batches to prevent connection timeout
                batch_size = 1000
                deleted_count = 0

                while True:
                    # Delete one batch at a time
                    result = session.run(f"""
                        MATCH (n:{label})
                        WITH n LIMIT {batch_size}
                        DETACH DELETE n
                        RETURN count(n) as deleted
                    """)
                    record = result.single()
                    batch_deleted = record["deleted"] if record else 0

                    if batch_deleted == 0:
                        break

                    deleted_count += batch_deleted
                    logger.info(f"  Deleted {deleted_count:,} / {node_count:,} {label} nodes...")

                logger.info(f"✓ Deleted {deleted_count:,} {label} nodes and their relationships")
                total_deleted += deleted_count

            if total_deleted == 0:
                logger.info(f"Database is already clear")
            else:
                logger.info(f"\n✓ Total deleted: {total_deleted:,} nodes across all labels")
                logger.info("✓ Database cleared - ready for fresh import")

    finally:
        driver.close()

    logger.info("=" * 60)


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Export Oak Curriculum Ontology to Neo4j AuraDB."""

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Export RDF/TTL curriculum data to Neo4j AuraDB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/export_to_neo4j.py --config scripts/export_to_neo4j_config.json

  # Clear database first, then export
  python scripts/export_to_neo4j.py --config scripts/export_to_neo4j_config.json --clear
        """
    )
    parser.add_argument('--clear', action='store_true',
                        help='Clear data from Neo4j database before import (scope defined by config)')
    parser.add_argument('--config', type=str, required=True,
                        help='Path to configuration file (required)')
    args = parser.parse_args()

    try:
        # Load configuration
        project_root = Path(__file__).parent.parent
        config_path = Path(args.config)

        if not config_path.exists():
            logger.error(f"Configuration file not found: {config_path}")
            sys.exit(1)

        logger.info("=" * 60)
        logger.info("RDF/TTL Curriculum Data → Neo4j AuraDB Export")
        logger.info("=" * 60)

        # Load and validate configuration
        export_config = ExportConfig(config_path)
        logger.info(f"✓ Configuration loaded and validated")
        logger.info(f"Target: {export_config.neo4j_uri}")
        logger.info(f"Database: {export_config.neo4j_database}")
        logger.info("-" * 60)

        # Clear data if requested
        if args.clear:
            # Get all target labels from label mapping(s)
            if isinstance(export_config.config.label_mapping, list):
                labels_to_clear = [lm.target_label for lm in export_config.config.label_mapping]
            else:
                labels_to_clear = export_config.config.label_mapping.target_label

            clear_neo4j_data(
                export_config.get_auth_data(),
                labels_to_clear
            )

        # Discover TTL files
        rdf_loader = RDFLoader(export_config.config.rdf_source, project_root, export_config.config)
        ttl_files = rdf_loader.discover_files()

        logger.info(f"Found {len(ttl_files)} TTL files to export:")
        for f in ttl_files:
            logger.info(f"  - {f.relative_to(project_root)}")

        # Connect to Neo4j and load data (don't use context manager - keep store open)
        logger.info("\n" + "=" * 60)
        logger.info("Connecting to AuraDB...")

        # Create store config
        store_config = Neo4jStoreConfig(
            auth_data=export_config.get_auth_data(),
            custom_prefixes=export_config.config.rdf_source.namespaces,
            handle_vocab_uri_strategy=HANDLE_VOCAB_URI_STRATEGY.MAP,
            batching=export_config.config.neo4j_connection.batching,
            batch_size=export_config.config.neo4j_connection.batch_size
        )

        # Create store and graph (like original)
        neo4j_store = Neo4jStore(config=store_config)
        neo4j_graph = Graph(store=neo4j_store, identifier=export_config.neo4j_uri)

        logger.info("✓ Connected to AuraDB!")

        # Load each TTL file
        total_triples = 0
        total_filtered = 0
        all_multi_valued_data = {}  # Accumulate multi-valued properties from all files
        all_slug_data = {}  # Accumulate slug data from all files
        all_uri_property_data = {}  # Accumulate object URI properties from all files
        all_rdf_types_data = {}  # Accumulate RDF type information from all files
        all_external_relationships = []  # Accumulate external relationships from all files

        logger.info("\n" + "=" * 60)
        for ttl_file in ttl_files:
            logger.info(f"\nExporting: {ttl_file.name}")
            logger.info("-" * 40)

            try:
                # Load and filter (now returns multi-valued, slug, URI property data, and external relationships)
                filtered_graph, original_count, filtered_count, multi_valued_data, slug_data, uri_property_data, rdf_types_data, external_relationships = rdf_loader.load_and_filter(ttl_file)

                # Merge multi-valued data
                for node_label, prop_data in multi_valued_data.items():
                    if node_label not in all_multi_valued_data:
                        all_multi_valued_data[node_label] = {}
                    for prop, uri_values in prop_data.items():
                        if prop not in all_multi_valued_data[node_label]:
                            all_multi_valued_data[node_label][prop] = {}
                        all_multi_valued_data[node_label][prop].update(uri_values)

                # Merge slug data
                for node_label, uri_slug_map in slug_data.items():
                    if node_label not in all_slug_data:
                        all_slug_data[node_label] = {}
                    all_slug_data[node_label].update(uri_slug_map)

                # Merge URI property data
                for node_label, prop_data in uri_property_data.items():
                    if node_label not in all_uri_property_data:
                        all_uri_property_data[node_label] = {}
                    for prop, uri_values in prop_data.items():
                        if prop not in all_uri_property_data[node_label]:
                            all_uri_property_data[node_label][prop] = {}
                        all_uri_property_data[node_label][prop].update(uri_values)

                # Merge RDF types data
                all_rdf_types_data.update(rdf_types_data)

                # Merge external relationships
                all_external_relationships.extend(external_relationships)

                # Add to Neo4j with commits after each batch to flush buffer
                batch_size = export_config.config.neo4j_connection.batch_size
                triple_count = 0

                for triple in filtered_graph:
                    neo4j_graph.add(triple)
                    triple_count += 1

                    # Commit after each batch to flush buffer completely
                    if triple_count % batch_size == 0:
                        neo4j_graph.commit()

                # Final commit for any remaining triples
                neo4j_graph.commit()

                file_triple_count = len(filtered_graph)
                total_triples += file_triple_count
                total_filtered += filtered_count

                if filtered_count > 0:
                    logger.info(f"✓ Added {file_triple_count} triples (filtered {filtered_count} ontology triples)")
                else:
                    logger.info(f"✓ Added {file_triple_count} triples")
                logger.info(f"  ✓ Committed in {(file_triple_count // batch_size) + 1} batches. Running total: {total_triples} triples")

            except Exception as e:
                logger.error(f"✗ Failed to export {ttl_file.name}: {e}")
                continue

        # Final summary
        logger.info("\n" + "=" * 60)
        logger.info(f"✓ Successfully exported {total_triples} triples to Neo4j!")
        if total_filtered > 0:
            logger.info(f"  (Filtered out {total_filtered} ontology declaration triples)")

        # Create separate driver for transformations (like original version)
        # IMPORTANT: Store stays open!
        driver = GraphDatabase.driver(
            export_config.neo4j_uri,
            auth=(export_config.neo4j_username, export_config.neo4j_password)
        )

        try:
            # Create transformation pipeline
            pipeline = TransformationPipeline(
                driver=driver,
                database=export_config.neo4j_database,
                transformations=[
                    LabelMappingTransformation(),
                    AddExternalTypeLabelsTransformation(),  # Add type labels for external ontology classes (e.g., Scheme)
                    RemoveLabelsTransformation(),
                    SlugExtractionTransformation(),
                    ObjectUriPropertyTransformation(),
                    MultiValuedPropertiesTransformation(),  # Run BEFORE PropertyMapping so arrays are consolidated first
                    PropertyMappingTransformation(),  # Run AFTER MultiValued so property renaming works on consolidated arrays
                    RelationshipTypeMappingTransformation(),
                    ReverseRelationshipsTransformation(),
                    InclusionFlatteningTransformation(),
                    CamelCaseConversionTransformation(),
                    ExternalRelationshipsTransformation(),  # Create relationships to existing external nodes
                    CleanupOrphanedResourceNodesTransformation(),  # Cleanup duplicate/orphaned Resource nodes
                    DropResourceConstraintTransformation(),  # Must run LAST - drop unused constraint
                ]
            )

            # Execute all transformations
            pipeline.execute(
                config=export_config.config,
                slug_data=all_slug_data,
                multi_valued_data=all_multi_valued_data,
                uri_property_data=all_uri_property_data,
                rdf_types_data=all_rdf_types_data,
                external_relationships=all_external_relationships
            )

            # Verify export
            pipeline.verify_export()

        finally:
            driver.close()
            # Final commit to flush any remaining buffer before closing
            # Note: Data should already be committed via per-file commits above
            logger.info("\nClosing Neo4j store...")
            try:
                neo4j_graph.commit()
                logger.info("✓ Final buffer flushed")
            except Exception as e:
                logger.warning(f"⚠️  Final commit failed (data should already be in Neo4j from per-file commits): {e}")

            try:
                neo4j_store.close()
                logger.info("✓ Store closed")
            except Exception as e:
                logger.warning(f"⚠️  Store close failed (non-critical): {e}")

        logger.info("\n" + "=" * 60)
        logger.info("✅ EXPORT COMPLETE!")
        logger.info("\nNext steps:")
        logger.info("1. Open Neo4j Browser in Aura Console")
        logger.info("2. Run: MATCH (n) RETURN labels(n), count(n)")
        logger.info("3. Explore your Oak Curriculum data!")

    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
