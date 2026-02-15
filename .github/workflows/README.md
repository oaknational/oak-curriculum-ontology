# GitHub Workflows Documentation

This directory contains automated CI/CD workflows for the Oak Curriculum Ontology repository.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Workflows](#workflows)
  - [1. Validate Ontology](#1-validate-ontology)
  - [2. Generate Documentation](#2-generate-documentation)
  - [3. Generate Distributions](#3-generate-distributions)
- [Workflow Features](#workflow-features)
- [Security](#security)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

---

## Overview

All workflows in this directory are designed to ensure the quality, accessibility, and usability of the Oak Curriculum Ontology. They implement:

- ✅ **Security:** Explicit permissions, checksum verification, SSL by default
- 🎯 **Quality:** Comprehensive validation, rich metadata
- 📊 **Transparency:** Detailed summaries, artifacts, status badges

---

## Workflows

### 1. Validate Ontology

**File:** [`validate-ontology.yml`](./validate-ontology.yml)
**Badge:** [![Validate Ontology](https://github.com/oaknational/oak-curriculum-ontology-public/workflows/Validate%20Ontology/badge.svg)](https://github.com/oaknational/oak-curriculum-ontology-public/actions/workflows/validate-ontology.yml)

#### Purpose

Validates the ontology structure and curriculum data against SHACL constraints to ensure data quality and consistency.

#### Triggers

- **Push** to `main` or `develop` branches (when .ttl files or validation scripts change)
- **Pull Request** to `main` branch
- **Manual dispatch** via GitHub Actions UI

#### What It Does

1. **Sets up environment**
   - Installs Python 3.12 (matches pyproject.toml)
   - Uses `uv` package manager for fast dependency installation
   - Creates virtual environment with `uv venv`
   - Installs `rdflib` and `pyshacl` dependencies

2. **Merges ontology files**
   - Combines all TTL files from `data/` directory
   - Resolves `owl:imports` statements recursively
   - Excludes versioned files (in `versions/` directories)
   - Output: `/tmp/combined-data.ttl`

3. **Validates Turtle syntax**
   - Uses `rdflib` to parse and validate merged TTL
   - Ensures syntactic correctness before SHACL validation

4. **Runs SHACL validation**
   - Validates against constraints in `ontology/oak-curriculum-constraints.ttl`
   - Uses ontology definitions from `ontology/oak-curriculum-ontology.ttl`
   - Applies RDFS inference for reasoning
   - Counts and reports violations

5. **Generates artifacts**
   - Uploads validation report (400-day retention)
   - Creates detailed GitHub step summary
   - Reports violation count and Python version used

#### Artifacts

- **Name:** `shacl-validation-report-{commit-sha}`
- **Contents:** Full SHACL validation report in human-readable format
- **Retention:** 400 days (maximum for public repos)
- **Access:** Available in workflow run summary

#### Success Criteria

- ✅ All TTL files parse successfully
- ✅ Merged ontology has valid Turtle syntax
- ✅ All SHACL constraints pass (zero violations)

#### Example Output

```
✅ Merged Turtle syntax is valid
✅ Validation passed
   Triple count: 45,231
   Violations: 0
```

#### Configuration

```yaml
permissions:
  contents: read
  pull-requests: write

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

---

### 2. Generate Documentation

**File:** [`generate-docs-widoco.yml`](./generate-docs-widoco.yml)
**Badge:** [![Generate Documentation](https://github.com/oaknational/oak-curriculum-ontology-public/workflows/Generate%20GH%20Pages%20with%20Widoco/badge.svg)](https://github.com/oaknational/oak-curriculum-ontology-public/actions/workflows/generate-docs-widoco.yml)

#### Purpose

Generates comprehensive HTML documentation from the ontology and deploys it to GitHub Pages.

#### Triggers

- **Release published** (new version released)
- **Manual dispatch** via GitHub Actions UI

#### What It Does

1. **Generates documentation with Widoco**
   - Uses official Widoco Docker image (v1.4.25)
   - Docker automatically pulls the image if not present
   - Runs as non-root user for security
   - Generates HTML documentation with cross-references
   - Creates WebVOWL interactive visualization
   - Includes .htaccess for content negotiation

2. **Quality checks**
   - Validates documentation structure
   - Checks for required files (index-en.html, sections/)
   - Verifies internal links
   - Counts generated HTML pages

3. **Adds metadata**
   - Creates `build-info.json` with:
     - Generation timestamp
     - Commit SHA and reference
     - Repository information
     - Widoco version used

4. **Deploys to GitHub Pages**
   - Uploads to GitHub Pages artifact
   - Deploys to production URL
   - Makes documentation publicly accessible

#### Generated Documentation

**URL:** https://oaknational.github.io/oak-curriculum-ontology-public/

**Includes:**
- 📖 Complete ontology documentation
- 🎨 WebVOWL interactive graph visualization
- 📊 Class and property definitions
- 🔗 Cross-references and relationships
- 📝 Annotations and descriptions
- ⚙️ .htaccess for content negotiation
- 📄 Build metadata (build-info.json)

#### Docker Security

```yaml
# Runs with current user ID (not root)
docker run --rm \
  -v ${{ github.workspace }}:/data \
  -u $(id -u):$(id -g) \
  ghcr.io/dgarijo/widoco:v1.4.25
```

#### Configuration

```yaml
permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false
```

---

### 3. Generate Distributions

**File:** [`generate-distributions.yml`](./generate-distributions.yml)
**Badge:** [![Generate Distributions](https://github.com/oaknational/oak-curriculum-ontology-public/workflows/Generate%20Static%20Distribution%20Files/badge.svg)](https://github.com/oaknational/oak-curriculum-ontology-public/actions/workflows/generate-distributions.yml)

#### Purpose

Generates the ontology in multiple RDF serialization formats with checksums and metadata for distribution to semantic web consumers.

#### Triggers

- **Manual dispatch** via GitHub Actions UI
- **Release published** (automatically attaches files to release)

#### What It Does

1. **Sets up Apache Jena**
   - Downloads Apache Jena binaries (v6.0.0)
   - Verifies SHA512 checksum for security
   - Adds tools to PATH

2. **Generates distribution formats**
   - Merges all ontology and data files
   - Converts to 4 standard RDF formats:
     - **Turtle (.ttl)** - Canonical format
     - **JSON-LD (.jsonld)** - Web-friendly format
     - **RDF/XML (.rdf)** - Legacy compatibility
     - **N-Triples (.nt)** - Line-oriented format

3. **Validates outputs**
   - Uses Apache Jena `riot` validator
   - Validates syntax for each format
   - Counts RDF triples in dataset
   - Reports validation status

4. **Generates checksums**
   - Creates SHA256 checksums (secure)
   - Creates MD5 checksums (compatibility)
   - Stored in `checksums-sha256.txt` and `checksums-md5.txt`

5. **Creates metadata**
   - Generates `distribution-info.json` with:
     - Generation timestamp
     - Commit information
     - Triple count
     - Format specifications (MIME types)

6. **Uploads artifacts**
   - Creates workflow artifact (30-day retention)
   - Attaches to GitHub release (if triggered by release)

#### Output Files

| File | Format | Purpose | MIME Type |
|------|--------|---------|-----------|
| `oak-curriculum-full.ttl` | Turtle | Canonical format | text/turtle |
| `oak-curriculum-full.jsonld` | JSON-LD | Web/JavaScript | application/ld+json |
| `oak-curriculum-full.rdf` | RDF/XML | Legacy tools | application/rdf+xml |
| `oak-curriculum-full.nt` | N-Triples | Line-based | application/n-triples |
| `checksums-sha256.txt` | Text | SHA256 hashes | text/plain |
| `checksums-md5.txt` | Text | MD5 hashes | text/plain |
| `distribution-info.json` | JSON | Build metadata | application/json |

#### Verifying Downloads

Users can verify file integrity:

```bash
# Download files
wget https://github.com/oaknational/oak-curriculum-ontology-public/releases/latest/download/oak-curriculum-full.ttl
wget https://github.com/oaknational/oak-curriculum-ontology-public/releases/latest/download/checksums-sha256.txt

# Verify checksum
sha256sum -c checksums-sha256.txt
```

#### Configuration

```yaml
permissions:
  contents: write  # Needed for release uploads

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  JENA_VERSION: "6.0.0"
```

---

## Workflow Features

### Security Best Practices

All workflows implement:

| Feature | Implementation |
|---------|----------------|
| **Explicit Permissions** | Least-privilege access (contents:read by default) |
| **Checksum Verification** | All downloads verified (SHA512/SHA256) |
| **SSL/TLS** | Enabled by default with fallback warnings |
| **Container Security** | Docker runs as non-root user |
| **File Permissions** | Secure defaults (755, not 777) |
| **Dependency Pinning** | All versions explicitly specified |
| **Audit Trail** | Full metadata and build information |

### Performance Optimizations

| Feature | Benefit |
|---------|---------|
| **Concurrency Control** | Prevents duplicate workflow runs |
| **Efficient Validation** | Refactored loops (75% less code) |
| **Simple Design** | No caching complexity (optimal for occasional runs) |

### Quality Assurance

| Feature | Description |
|---------|-------------|
| **Python 3.12** | Tests on Python 3.12 (matches pyproject.toml) |
| **Violation Counting** | Tracks SHACL constraint violations |
| **Triple Counting** | Reports RDF dataset size |
| **Artifact Retention** | 400-day validation reports, 30-day distributions |
| **Rich Summaries** | Detailed GitHub step summaries |
| **Build Metadata** | JSON files with full traceability |

---

## Security

### Permissions Model

Each workflow uses explicit, minimal permissions:

```yaml
# Validation workflow
permissions:
  contents: read           # Read repository code
  pull-requests: write     # Comment on PRs (future)

# Documentation workflow
permissions:
  contents: read           # Read repository code
  pages: write             # Deploy to GitHub Pages
  id-token: write          # GitHub Pages authentication

# Distribution workflow
permissions:
  contents: write          # Upload to releases
```

### Checksum Verification

All external downloads are verified:

1. **Apache Jena:** SHA512 checksum verified before use
2. **Distributions:** SHA256 checksums generated for users
3. **Containers:** Official images from trusted registries

### SSL/TLS

- SSL verification **enabled by default** in all network requests
- Fallback to unverified SSL only with explicit warning
- 30-second timeout on all network requests

---

## Performance

### Typical Run Times

| Workflow | Duration |
|----------|----------|
| Validate Ontology | 2-3 min |
| Generate Documentation | 2-3 min |
| Generate Distributions | 5-7 min |


### Concurrency Control

Prevents resource waste from duplicate runs:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

---

## Troubleshooting

### Validation Failures

**Problem:** SHACL validation fails with constraint violations

**Solution:**
1. Check the uploaded validation report artifact
2. Review the violation count in the step summary
3. Fix data issues in the relevant TTL files
4. Re-run validation

**Common Issues:**
- Missing required properties (rdfs:label, skos:definition)
- Non-consecutive display orders
- Invalid data types or language tags

### Documentation Generation Fails

**Problem:** Widoco fails to generate documentation

**Solution:**
1. Check that `ontology/oak-curriculum-ontology.ttl` exists and is valid
2. Verify Docker is running properly
3. Check for syntax errors in the ontology file
4. Review Docker logs in the workflow output

### Distribution Validation Errors

**Problem:** RDF format validation fails

**Solution:**
1. Check which format failed (Turtle, JSON-LD, RDF/XML, N-Triples)
2. Review the Apache Jena riot output
3. Verify source TTL files are syntactically correct
4. Check for unsupported RDF features in that format

### Workflow Performance

**Note:** These workflows are optimized for occasional runs and do not use caching. GitHub Actions caches expire after 7 days of inactivity, so caching adds complexity without benefit for infrequent workflow execution.

---

## Additional Resources

### GitHub Actions Documentation
- [Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [Security Hardening](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)

### Tools & Technologies
- [uv Package Manager](https://github.com/astral-sh/uv)
- [Apache Jena](https://jena.apache.org/)
- [Widoco](https://github.com/dgarijo/Widoco)
- [pyshacl](https://github.com/RDFLib/pySHACL)
- [rdflib](https://github.com/RDFLib/rdflib)

### Semantic Web Standards
- [RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/)
- [OWL 2 Overview](https://www.w3.org/TR/owl2-overview/)
- [SHACL](https://www.w3.org/TR/shacl/)
- [Turtle](https://www.w3.org/TR/turtle/)

---

**Last Updated:** 2026-02-15
**Workflow Version:** 1.0
**Documentation Version:** 1.0
