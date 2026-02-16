# Oak Curriculum Ontology

<!-- Version and Status Badges -->
![Version](https://img.shields.io/badge/version-0.1.0-orange)
![Status](https://img.shields.io/badge/status-early_release-yellow)
![License: CC0](https://img.shields.io/badge/License-CC0_1.0-lightgrey.svg)
![License: MIT + OGL-3.0](https://img.shields.io/badge/License-MIT%20%2B%20OGL--3.0-lightgrey.svg)
![Python](https://img.shields.io/badge/python-3.12+-blue.svg)

<!-- Build and Quality Badges -->
[![Validate Ontology](https://github.com/oaknational/oak-curriculum-ontology-public/workflows/Validate%20Ontology/badge.svg)](https://github.com/oaknational/oak-curriculum-ontology-public/actions/workflows/validate-ontology.yml)
[![Generate Documentation](https://github.com/oaknational/oak-curriculum-ontology-public/workflows/Generate%20GH%20Pages%20with%20Widoco/badge.svg)](https://github.com/oaknational/oak-curriculum-ontology-public/actions/workflows/generate-docs-widoco.yml)
[![Generate Distributions](https://github.com/oaknational/oak-curriculum-ontology-public/workflows/Generate%20Static%20Distribution%20Files/badge.svg)](https://github.com/oaknational/oak-curriculum-ontology-public/actions/workflows/generate-distributions.yml)

<!-- Documentation and Resources -->
[![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue)](https://oaknational.github.io/oak-curriculum-ontology-public/)
[![W3C Standards](https://img.shields.io/badge/W3C-RDF%20|%20OWL%20|%20SHACL-005A9C)](https://www.w3.org/standards/semanticweb/)

**A machine-readable semantic representation of the Oak Curriculum
and linkage to the National Curriculum for England (2014)**

Developed by [Oak National Academy](https://thenational.academy)

---

## ⚠️ Early Release Notice

This is version 0.1 - an early public release for evaluation and community feedback.  
The ontology structure, URIs, and data are under active development and **subject to change**.  

- ✅ Core ontology structure is stable  
- 🚧 Subject coverage is being expanded (currently: Science, History, Mathematics)  
- 🔄 Data validation and refinement ongoing  
- 📝 Feedback, issues, and contributions are welcome!

A semantic web ontology representing the Oak Curriculum and linkage to the National Curriculum for 
England (2014).

https://oaknational.github.io/oak-curriculum-ontology-public/

**What's included in v0.1:**
- ✅ Temporal Structure: Phases, Key Stages, Year Groups
- ✅ Programme Structure: English, Mathematics, Science, History, Geography, Citizenship
- ✅ Knowledge Taxonomy: English, Mathematics, Science, History, Geography, Citizenship
- ✅ SHACL constraints for dataset validation 

**Coming soon:**
- 🚧 Additional subjects
- 🚧 Expanded SHACL validation
- 🚧 Complete documentation

**We welcome:**
- 🐛 Issue reports (structure, data, documentation)
- 💡 Feature requests and suggestions
- 🤝 Contributions (see [CONTRIBUTING.md](CONTRIBUTING.md))


## License

This repository uses dual licensing:

### Code (MIT License)
All Python scripts, GitHub Actions workflows, and software tools are licensed under the [MIT License](LICENSE-CODE).

This includes:
- `scripts/` directory
- `.github/workflows/`

### Ontology and Data (OGL 3.0)
The curriculum ontology, vocabulary definitions, and curriculum data are licensed under [Open Government Licence v3.0 (OGL 3.0)](LICENSE-DATA).

This includes:
- `ontology/` - OWL/SKOS ontology files
- `data/` - Curriculum instance data
- `docs/` - Documentation

**Attribution:** When using this work, please credit "Oak National Academy"

---
