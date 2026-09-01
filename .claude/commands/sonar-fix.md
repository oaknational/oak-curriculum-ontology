---
description: Fetch SonarCloud quality gate findings and fix them
argument-hint: "[PR number | 'main' | blank for current branch's PR]"
allowed-tools: Bash(curl:*), Bash(gh:*), Bash(git:*), Bash(uv:*), Read, Edit, Write, Grep, Glob
---

Fetch the open SonarCloud findings for `$1` and fix them.

## Context

- Project key: `oaknational_oak-curriculum-ontology-public`
- The project is public, so the SonarCloud Web API needs no authentication.
  Do not add a token. If a `SONAR_TOKEN` is ever needed, read it from the
  environment — never write a credential into a file.

## Step 1 — work out the target

- `$1` is a number: analyse that pull request.
- `$1` is `main`, or is empty and the branch has no PR: analyse `main`.
- `$1` is empty: use `gh pr view --json number -q .number` for the current branch.

## Step 2 — fetch the findings

For a pull request:

```sh
curl -s "https://sonarcloud.io/api/issues/search?componentKeys=oaknational_oak-curriculum-ontology-public&pullRequest=<N>&resolved=false&ps=100"
```

For `main`, drop the `pullRequest` parameter.

To see why the gate failed rather than the raw issue list:

```sh
gh api "repos/oaknational/oak-curriculum-ontology/commits/<sha>/check-runs" \
  -q '.check_runs[] | select(.name|test("Sonar")) | {conclusion, title: .output.title, summary: .output.summary}'
```

Summarise as a table of `rule | file:line | message` before changing anything.

## Step 3 — fix

Group the work by rule, and prefer a real fix over a suppression.

Before applying a fix repo-wide, **verify it actually works locally** — several
Sonar suggestions do not hold here:

- `uv run --locked` / `uv sync --locked` is correct and is already used
  everywhere. Keep it.
- `--no-build` (S8541) **breaks the build**: it refuses to build this project's
  own editable install. It is suppressed in `.sonarcloud.properties` with a
  rationale. Do not "fix" these by adding the flag.
- `wget` must download from `archive.apache.org`, not `dlcdn.apache.org`, so
  that `--max-redirect=0` (S6506) can be used. dlcdn 302s to the archive.

Run the checks CI runs before concluding:

```sh
uv run --locked --extra dev --extra export ruff check scripts/ tests/ conftest.py
uv run --locked --extra dev --extra export pytest
```

If a finding is a false positive, add `# NOSONAR` with a comment explaining
why — that convention is already used in `scripts/cli_paths.py`. If a rule is
unachievable for a structural reason, add a documented
`sonar.issue.ignore.multicriteria` entry to `.sonarcloud.properties` rather
than silencing it in the SonarCloud UI, so the reasoning stays in the repo.

## Step 4 — report

State what was fixed, what was suppressed and why, and anything you could not
fix. Do not claim the gate will pass until CI confirms it.
