#!/usr/bin/env python3
"""
Merge TTL files into a single file, recursively resolving owl:imports.

Excludes any files inside directories named "versions".

"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import Graph, URIRef

logger = logging.getLogger(__name__)

# OWL imports predicate
OWL_IMPORTS = URIRef("http://www.w3.org/2002/07/owl#imports")

# Core ontology filename
OAK_ONTOLOGY_FILENAME = "oak-curriculum-ontology.ttl"

# Static URI pattern mappings: (pattern_substring, path_parts)
URI_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("w3id.org/uk/oak/curriculum/core", ("ontology", OAK_ONTOLOGY_FILENAME)),
    ("w3id.org/uk/oak/curriculum/oak-ontology", ("ontology", OAK_ONTOLOGY_FILENAME)),
    ("w3id.org/uk/oak/curriculum/oakcurriculum/programme-structure", ("data", "programme-structure.ttl")),
    ("w3id.org/uk/oak/curriculum/oakcurriculum/threads", ("data", "threads.ttl")),
    ("w3id.org/uk/oak/curriculum/nationalcurriculum/temporal-structure", ("data", "temporal-structure.ttl")),
    # Handle URIs with typo (missing "oak" in path)
    ("w3id.org/uk/curriculum/oakcurriculum/programme-structure", ("data", "programme-structure.ttl")),
    ("w3id.org/uk/curriculum/oakcurriculum/threads", ("data", "threads.ttl")),
]

# Science-related subjects that are stored in data/subjects/science/
SCIENCE_SUBJECTS = {"biology", "chemistry", "physics", "combined-science", "science"}

# Default configuration
DEFAULT_OUTPUT_FILE = Path("/tmp/combined-data.ttl")
DEFAULT_ROOT_PATHS = ["data"]


@dataclass
class TTLMerger:
    """Merge TTL files with recursive owl:imports resolution."""

    repo_root: Path
    graph: Graph = field(default_factory=Graph)
    seen_files: set[Path] = field(default_factory=set)
    seen_uris: set[str] = field(default_factory=set)

    def _try_path(self, *path_parts: str) -> Path | None:
        """Return path if it exists, otherwise None."""
        path = self.repo_root.joinpath(*path_parts)
        return path if path.exists() else None

    def _resolve_subject_uri(self, import_uri_str: str) -> Path | None:
        """
        Resolve nationalcurriculum subject URIs (programme-structure or knowledge-taxonomy).

        Handles patterns like:
        - nationalcurriculum/{subject}-programme-structure
        - nationalcurriculum/{subject}-knowledge-taxonomy
        """
        for suffix in ("programme-structure", "knowledge-taxonomy"):
            match = re.search(rf"nationalcurriculum/([\w-]+)-{suffix}", import_uri_str)
            if match:
                subject = match.group(1)
                subject_dir = "science" if subject in SCIENCE_SUBJECTS else subject
                path = self._try_path("data", "subjects", subject_dir, f"{subject}-{suffix}.ttl")
                if path:
                    return path
        return None

    def _resolve_special_uri(self, uri_str: str) -> Path | None:
        """Resolve special URI patterns to local paths."""
        stripped = uri_str.rstrip("/")

        # Handle /ontology suffix (without oak- prefix)
        if stripped.endswith("w3id.org/uk/oak/curriculum/ontology"):
            return self._try_path("ontology", OAK_ONTOLOGY_FILENAME)

        # Handle nationalcurriculum base URI
        if stripped.endswith("w3id.org/uk/oak/curriculum/nationalcurriculum"):
            return self._try_path("data", "temporal-structure.ttl")

        # Handle oak-data files
        if "w3id.org/uk/oak/curriculum/oak-data/" in uri_str:
            filename = uri_str.split("oak-data/")[-1].rstrip("/")
            return self._try_path("data", f"{filename}.ttl")

        return None

    def resolve_import_uri(self, import_uri: URIRef | str) -> Path | str | None:
        """Resolve an import URI to a local path or remote URL."""
        import_uri_str = str(import_uri)

        # Check if it's already a GitHub raw URL
        if "raw.githubusercontent.com" in import_uri_str:
            return import_uri_str

        # Check static pattern mappings
        for pattern, path_parts in URI_PATTERNS:
            if pattern in import_uri_str:
                if path := self._try_path(*path_parts):
                    return path

        # Try special URI patterns
        if path := self._resolve_special_uri(import_uri_str):
            return path

        # Handle nationalcurriculum subject URIs
        if path := self._resolve_subject_uri(import_uri_str):
            return path

        # Check if it's a local file path
        import_path = Path(import_uri_str)
        return import_path if import_path.exists() else None

    def parse_with_imports(self, file_path_or_uri: Path | URIRef | str) -> None:
        """Parse a TTL file and recursively parse any owl:imports."""
        if isinstance(file_path_or_uri, Path):
            self._parse_local_file(file_path_or_uri)
        else:
            self._parse_uri(file_path_or_uri)

        self._process_imports(file_path_or_uri)

    def _parse_local_file(self, file_path: Path) -> None:
        """Parse a local TTL file."""
        resolved_path = file_path.resolve()

        if resolved_path in self.seen_files:
            return
        if "versions" in resolved_path.parts:
            logger.debug("Skipping versioned file: %s", resolved_path)
            return
        if not resolved_path.exists():
            logger.warning("File does not exist: %s", resolved_path)
            return

        logger.info("Parsing: %s", resolved_path)
        self.graph.parse(str(resolved_path), format="turtle")
        self.seen_files.add(resolved_path)

    def _parse_uri(self, uri: URIRef | str) -> None:
        """Parse a TTL file from a URI."""
        import_uri_str = str(uri)

        if import_uri_str in self.seen_uris:
            return
        self.seen_uris.add(import_uri_str)

        resolved = self.resolve_import_uri(uri)
        if resolved is None:
            logger.warning("Cannot resolve import URI: %s", import_uri_str)
            return

        # If resolved to a local file
        if isinstance(resolved, Path):
            resolved_path = resolved.resolve()
            if resolved_path in self.seen_files:
                return
            logger.info("Resolved: %s -> %s", import_uri_str, resolved)
            self.seen_files.add(resolved_path)
            try:
                self.graph.parse(str(resolved_path), format="turtle")
            except Exception as e:
                logger.error("Error parsing %s: %s", resolved_path, e)
            return

        # Remote URL - fetch and parse
        logger.info("Fetching: %s -> %s", import_uri_str, resolved)

        try:
            with urllib.request.urlopen(resolved, timeout=30) as response:
                self.graph.parse(data=response.read(), format="turtle")
        except urllib.error.URLError as e:
            logger.error("Error fetching %s: %s", resolved, e)
        except Exception as e:
            logger.error("Error parsing %s: %s", resolved, e)

    def _process_imports(self, current_file: Path | URIRef | str) -> None:
        """Process owl:imports from the current graph state."""
        for obj in self.graph.objects(None, OWL_IMPORTS):
            import_uri_str = str(obj)

            if import_uri_str in self.seen_uris:
                continue

            # Try to resolve as a local file first
            import_path = Path(import_uri_str)
            if import_path.is_absolute() and import_path.exists():
                self.parse_with_imports(import_path)
            elif not import_path.is_absolute() and isinstance(current_file, Path):
                rel_path = current_file.parent / import_path
                if rel_path.exists():
                    self.parse_with_imports(rel_path)
                    continue

            # Otherwise treat as a URI that needs resolution
            self.parse_with_imports(str(obj))

    def merge(self, root_paths: list[str]) -> None:
        """Merge TTL files from the given root paths."""
        for path_str in root_paths:
            path = self.repo_root / path_str
            if path.is_dir():
                for ttl_file in sorted(path.rglob("*.ttl")):
                    self.parse_with_imports(ttl_file)
            elif path.is_file():
                self.parse_with_imports(path)
            else:
                logger.warning("Root path not found: %s", path_str)

    def save(self, output_file: Path) -> None:
        """Serialize the merged graph to a file."""
        self.graph.serialize(destination=str(output_file), format="turtle")
        logger.info("Merged %d files into %s", len(self.seen_files), output_file)


def main() -> int:
    """Merge TTL files and resolve owl:imports."""
    parser = argparse.ArgumentParser(
        description="Merge TTL files into a single file, resolving owl:imports.",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help=f"Output file path (default: {DEFAULT_OUTPUT_FILE})",
    )
    parser.add_argument(
        "-r", "--repo-root",
        type=Path,
        default=None,
        help="Repository root directory (default: parent of scripts/)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (debug) logging",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress info messages, only show warnings and errors",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=DEFAULT_ROOT_PATHS,
        help=f"Paths to scan for TTL files (default: {DEFAULT_ROOT_PATHS})",
    )
    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        level = logging.DEBUG
    elif args.quiet:
        level = logging.WARNING
    else:
        level = logging.INFO

    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")

    repo_root = args.repo_root or Path(__file__).parent.parent

    try:
        merger = TTLMerger(repo_root=repo_root)
        merger.merge(args.paths)
        merger.save(args.output)
        return 0
    except Exception as e:
        logger.error("Failed to merge TTL files: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
