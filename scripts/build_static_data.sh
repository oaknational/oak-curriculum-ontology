#!/bin/bash
# Generate static distribution files from RDF data
# Outputs: Turtle, JSON-LD, RDF/XML, N-Triples

set -e

echo "=========================================="
echo "Building Static Distribution Files"
echo "=========================================="
echo ""

# Output directory
OUTPUT_DIR="distributions"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# Collect all source TTL files
echo "Collecting source files..."

# Build list of all TTL files to merge
SOURCE_FILES=""

# Ontology files
for file in ontology/*.ttl; do
    if [ -f "$file" ]; then
        SOURCE_FILES="$SOURCE_FILES $file"
        echo "  + $file"
    fi
done

# Core data files
for file in data/*.ttl; do
    if [ -f "$file" ]; then
        SOURCE_FILES="$SOURCE_FILES $file"
        echo "  + $file"
    fi
done

# Subject data files (all subjects, all key stages)
for file in data/subjects/**/*.ttl; do
    if [ -f "$file" ]; then
        SOURCE_FILES="$SOURCE_FILES $file"
        echo "  + $file"
    fi
done

echo ""
echo "Generating distribution formats..."

# Generate merged Turtle file (canonical format)
echo "  Generating Turtle (.ttl)..."
riot --output=TTL $SOURCE_FILES > "$OUTPUT_DIR/oak-curriculum-full.ttl"
echo "    Created oak-curriculum-full.ttl"

# Generate JSON-LD from merged Turtle
echo "  Generating JSON-LD (.jsonld)..."
riot --output=JSONLD "$OUTPUT_DIR/oak-curriculum-full.ttl" > "$OUTPUT_DIR/oak-curriculum-full.jsonld"
echo "    Created oak-curriculum-full.jsonld"

# Generate RDF/XML from merged Turtle
echo "  Generating RDF/XML (.rdf)..."
riot --output=RDFXML "$OUTPUT_DIR/oak-curriculum-full.ttl" > "$OUTPUT_DIR/oak-curriculum-full.rdf"
echo "    Created oak-curriculum-full.rdf"

# Generate N-Triples from merged Turtle
echo "  Generating N-Triples (.nt)..."
riot --output=NTRIPLES "$OUTPUT_DIR/oak-curriculum-full.ttl" > "$OUTPUT_DIR/oak-curriculum-full.nt"
echo "    Created oak-curriculum-full.nt"

echo ""
echo "=========================================="
echo "Distribution Summary"
echo "=========================================="
echo ""

# Show file sizes
echo "Generated files:"
ls -lh "$OUTPUT_DIR"/* | awk '{print "  " $9 " (" $5 ")"}'

echo ""
TOTAL_SIZE=$(du -sh "$OUTPUT_DIR" | cut -f1)
echo "Total distribution size: $TOTAL_SIZE"
echo ""
