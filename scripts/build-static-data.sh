#!/bin/bash
# Generate static distribution files from RDF data
# Outputs: Turtle, JSON-LD, RDF/XML

set -e

echo "=========================================="
echo "🏗️  Building Static Distribution Files"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m'

# Output directory
OUTPUT_DIR="distributions"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/subjects" "$OUTPUT_DIR/keystages" "$OUTPUT_DIR/themes"

# Build common data file list
echo -e "${BLUE}📦 Collecting data files...${NC}"
DATA_FILES=""
DATA_FILES="$DATA_FILES --data=ontology/dfe-curriculum-ontology.ttl"
DATA_FILES="$DATA_FILES --data=data/national-curriculum-for-england/temporal-structure.ttl"

# Check if themes file exists
if [ -f "data/national-curriculum-for-england/themes.ttl" ]; then
    DATA_FILES="$DATA_FILES --data=data/national-curriculum-for-england/themes.ttl"
fi

# Add all subject files
for file in data/national-curriculum-for-england/subjects/**/*.ttl; do
    if [ -f "$file" ]; then
        DATA_FILES="$DATA_FILES --data=$file"
    fi
done

echo -e "${GREEN}✓${NC} Data files collected"
echo ""

# Helper function to generate RDF formats from CONSTRUCT query
generate_rdf_formats() {
    local name=$1
    local construct_query=$2
    local output_base=$3

    echo -e "${BLUE}📋 Generating $name...${NC}"

    # Generate Turtle (native format)
    arq $DATA_FILES \
        --query="$construct_query" \
        --results=TTL > "${output_base}.ttl"
    echo -e "${GREEN}  ✓${NC} $(basename ${output_base}).ttl"

    # Convert Turtle to JSON-LD
    riot --formatted=JSONLD "${output_base}.ttl" > "${output_base}.jsonld"
    echo -e "${GREEN}  ✓${NC} $(basename ${output_base}).jsonld"

    # Convert Turtle to RDF/XML
    riot --formatted=RDFXML "${output_base}.ttl" > "${output_base}.rdf"
    echo -e "${GREEN}  ✓${NC} $(basename ${output_base}).rdf"
}

# Generate subjects index in all RDF formats
generate_rdf_formats \
    "subjects index" \
    "queries/subjects-index.sparql" \
    "$OUTPUT_DIR/subjects/index"

# Generate Science KS3 in all RDF formats
generate_rdf_formats \
    "Science KS3" \
    "queries/science-ks3.sparql" \
    "$OUTPUT_DIR/subjects/science-ks3"

# Generate full curriculum in all RDF formats
generate_rdf_formats \
    "full curriculum dataset" \
    "queries/full-curriculum.sparql" \
    "$OUTPUT_DIR/curriculum-full"

# Calculate statistics
echo ""
echo "=========================================="
TOTAL_FILES=$(find "$OUTPUT_DIR" -type f | wc -l | tr -d ' ')
TOTAL_SIZE=$(du -sh "$OUTPUT_DIR" | cut -f1)
echo -e "${GREEN}✅ Generated $TOTAL_FILES distribution files ($TOTAL_SIZE)${NC}"
echo "=========================================="
echo ""

# List files by format
echo "Generated files:"
echo ""
echo -e "${BLUE}Turtle (RDF):${NC}"
find "$OUTPUT_DIR" -name "*.ttl" -exec echo "  - {}" \;
echo ""
echo -e "${BLUE}JSON-LD (RDF):${NC}"
find "$OUTPUT_DIR" -name "*.jsonld" -exec echo "  - {}" \;
echo ""
echo -e "${BLUE}RDF/XML:${NC}"
find "$OUTPUT_DIR" -name "*.rdf" -exec echo "  - {}" \;
echo ""
