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

Group the work by rule. Strongly prefer a real fix over a suppression: Sonar's
suggested fix is usually correct, and when it looks impossible the obstacle is
more often our own setup than the rule.

Verify each fix locally before applying it repo-wide — and verify it against
the *exact* dependency set the failing command uses. Testing with heavier
extras than a command needs will make a workable fix look impossible.

Established patterns here:

- `--locked` on every `uv` call. Already in place; keep it.
- `--no-build` (S8541) works as a two-step: `uv sync --locked --no-build
  --no-install-project` to build the environment, then `uv run --no-sync
  --no-build` to use it. `--no-install-project` skips this project's own
  editable install, which is safe because `[tool.setuptools] packages` is
  empty. It is a `uv sync` flag only — `uv run` rejects it.
- `owlready2` publishes no wheel, so any install pulling it cannot use
  `--no-build`. It is isolated in the `sql` extra for that reason; keep it out
  of `dev` and `export`.
- `wget` must download from `archive.apache.org`, not `dlcdn.apache.org`, so
  that `--max-redirect=0` (S6506) can be used. dlcdn 302s to the archive.
- Container permission findings (S2612): do not make a bind mount
  world-writable. Prefer writing inside the container and `docker cp`-ing the
  result out. Running the container as the runner's UID is not safe in general
  — Widoco writes to its own working directory and fails that way.

Run the checks CI runs before concluding:

```sh
uv run --locked --extra dev --extra export ruff check scripts/ tests/ conftest.py
uv run --locked --extra dev --extra export pytest
```

If a finding is a false positive, add `# NOSONAR` with a comment explaining
why — that convention is already used in `scripts/cli_paths.py`. Note it
silences every rule on that line, not just the one you meant.

If a rule is genuinely unachievable, add a documented
`sonar.issue.ignore.multicriteria` entry to `.sonarcloud.properties` rather
than silencing it in the SonarCloud UI, so the reasoning stays in the repo.
Be warned that these entries have repeatedly failed to take effect under
Automatic Analysis: do not assume adding one clears a finding, always re-check
the gate afterwards, and treat it as a last resort rather than a quick escape.

## Step 4 — report

State what was fixed, what was suppressed and why, and anything you could not
fix. Do not claim the gate will pass until CI confirms it.
