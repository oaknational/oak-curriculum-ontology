## Description

- List of changes

**Scope check**: does this PR change the ontology model or curriculum data
(`ontology/`, `data/`), or only docs/tooling? Model and data changes need
sign-off from the ontology owner.

## Issue(s)

Fixes #

## How to test

1. `./scripts/validate.sh` — SHACL validation passes
2. `uv run --extra dev --extra export pytest` — tests pass
3. `uv run pre-commit run --all-files` — markdown and hooks clean

## Checklist

- [ ] Validation passes locally (`./scripts/validate.sh`)
- [ ] README examples/counts still match the data (CI enforces this)
- [ ] Version strings unchanged, or aligned everywhere (CI enforces this)
- [ ] No ontology/data changes — or ontology owner approved
- [ ] Tests added or updated where appropriate
