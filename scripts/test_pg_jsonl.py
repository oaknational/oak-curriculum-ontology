#!/usr/bin/env python3
"""
test_pg_jsonl.py — Smoke test for property graph JSONL distribution files.

Loads nodes.jsonl and relationships.jsonl and verifies graph integrity:

  1. Both files are non-empty
  2. No dangling relationship endpoints — every startNodeId and endNodeId
     in relationships.jsonl has a corresponding id in nodes.jsonl
  3. Node type diversity — at least two distinct label types are present
     beyond ExternalReference (guards against namespace misdetection)
  4. Stub ratio — ExternalReference stubs are fewer than 10% of total nodes
  5. Sample traversal — picks the most populated node type, selects the
     first node of that type, and confirms it has at least one outgoing
     relationship whose endpoint also exists in the node set

Exits 0 if all checks pass. Exits 1 if any check fails, printing details
of each failure. Does not require any dependencies beyond the Python
standard library.

Usage:
  python scripts/test_pg_jsonl.py <output_dir>

  where <output_dir> is the directory containing nodes.jsonl and
  relationships.jsonl, e.g.:

    # Single-dataset repo
    python scripts/test_pg_jsonl.py distributions

    # Multi-dataset repo (run once per dataset)
    python scripts/test_pg_jsonl.py distributions/natcurric-2014
    python scripts/test_pg_jsonl.py distributions/natcurric-2028

Exit codes:
  0  All checks passed
  1  One or more checks failed, or required files not found
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load_nodes(path: Path) -> tuple[dict[str, list[str]], int]:
    """Return (id -> labels, total_count) from nodes.jsonl."""
    nodes: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        nodes[obj["id"]] = obj.get("labels", [])
    return nodes, len(nodes)


def load_relationships(path: Path) -> tuple[list[dict], int]:
    """Return (list of relationship dicts, total_count) from relationships.jsonl."""
    rels = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rels.append(json.loads(line))
    return rels, len(rels)


def _check_non_empty(node_count: int, rel_count: int) -> list[str]:
    failures = []
    if node_count == 0:
        failures.append("nodes.jsonl is empty")
    if rel_count == 0:
        failures.append("relationships.jsonl is empty")
    return failures


def _check_dangling(nodes: dict, rels: list[dict]) -> list[str]:
    dangling = {
        r[key]
        for r in rels
        for key in ("startNodeId", "endNodeId")
        if r[key] not in nodes
    }
    if dangling:
        return [
            f"{len(dangling):,} dangling relationship endpoint(s) — "
            f"first: {next(iter(dangling))}"
        ]
    return []


def _check_type_diversity(label_counts: Counter) -> tuple[list[str], list[str]]:
    """Return (failures, non_stub_types)."""
    non_stub_types = [t for t in label_counts if t != "ExternalReference"]
    if len(non_stub_types) < 2:
        return (
            [f"Only {len(non_stub_types)} non-ExternalReference node type(s) found "
             f"— possible namespace detection failure"],
            non_stub_types,
        )
    return [], non_stub_types


def _check_stub_ratio(label_counts: Counter, node_count: int) -> tuple[list[str], int, float]:
    """Return (failures, stub_count, stub_ratio)."""
    stub_count = label_counts.get("ExternalReference", 0)
    stub_ratio = stub_count / node_count if node_count else 0
    if stub_ratio >= 0.10:
        return (
            [f"ExternalReference stubs are {stub_ratio:.0%} of nodes "
             f"({stub_count:,}/{node_count:,}) — expected < 10%"],
            stub_count,
            stub_ratio,
        )
    return [], stub_count, stub_ratio


def _check_sample_traversal(
    nodes: dict,
    outgoing_index: dict,
    non_stub_types: list[str],
    label_counts: Counter,
) -> tuple[list[str], str | None, str | None]:
    """Return (failures, sample_node_uri, sample_type)."""
    sample_node = None
    sample_type = None
    for label_type in sorted(non_stub_types, key=lambda t: -label_counts[t]):
        candidate = next(
            (uri for uri, labels in nodes.items()
             if labels and labels[0] == label_type and uri in outgoing_index),
            None,
        )
        if candidate:
            sample_node = candidate
            sample_type = label_type
            break

    if sample_node is None:
        return ["No non-stub node with outgoing relationships found"], None, None

    missing = [r["endNodeId"] for r in outgoing_index[sample_node] if r["endNodeId"] not in nodes]
    if missing:
        return [f"Sample traversal: {len(missing)} endpoint(s) missing from nodes"], sample_node, sample_type

    return [], sample_node, sample_type


def _print_report(
    node_count: int,
    rel_count: int,
    stub_count: int,
    stub_ratio: float,
    label_counts: Counter,
    rels: list[dict],
    nodes: dict,
    outgoing_index: dict,
    sample_node: str | None,
    sample_type: str | None,
) -> None:
    print(f"  Nodes:         {node_count:,}")
    print(f"  Relationships: {rel_count:,}")
    print(f"  Stubs:         {stub_count:,} ({stub_ratio:.1%})")
    print()
    print("  Node types:")
    for label, count in label_counts.most_common():
        print(f"    {label:<35} {count:>6,}")
    print()
    print("  Relationship types:")
    rel_type_counts = Counter(r["type"] for r in rels)
    for rel_type, count in rel_type_counts.most_common():
        print(f"    {rel_type:<35} {count:>6,}")
    print()
    if sample_node:
        outgoing = outgoing_index[sample_node]
        print(f"  Sample traversal ({sample_type}):")
        print(f"    {sample_node.split('/')[-1]}")
        for r in outgoing[:5]:
            endpoint_labels = nodes.get(r["endNodeId"], ["?"])
            print(f"      --[{r['type']}]--> "
                  f"{r['endNodeId'].split('/')[-1]}  {endpoint_labels}")
        if len(outgoing) > 5:
            print(f"      ... and {len(outgoing) - 5} more")


def run_checks(output_dir: Path) -> bool:
    nodes_path = output_dir / "nodes.jsonl"
    rels_path = output_dir / "relationships.jsonl"

    for p in (nodes_path, rels_path):
        if not p.exists():
            print(f"  ERROR: {p} not found", file=sys.stderr)
            return False

    nodes, node_count = load_nodes(nodes_path)
    rels, rel_count = load_relationships(rels_path)

    failures = _check_non_empty(node_count, rel_count)
    if failures:
        for f in failures:
            print(f"  FAIL: {f}")
        return False

    failures += _check_dangling(nodes, rels)

    label_counts = Counter(labels[0] for labels in nodes.values() if labels)
    diversity_failures, non_stub_types = _check_type_diversity(label_counts)
    failures += diversity_failures

    stub_failures, stub_count, stub_ratio = _check_stub_ratio(label_counts, node_count)
    failures += stub_failures

    outgoing_index: dict[str, list[dict]] = defaultdict(list)
    for r in rels:
        outgoing_index[r["startNodeId"]].append(r)

    traversal_failures, sample_node, sample_type = _check_sample_traversal(
        nodes, outgoing_index, non_stub_types, label_counts
    )
    failures += traversal_failures

    if failures:
        for f in failures:
            print(f"  FAIL: {f}")
        return False

    _print_report(node_count, rel_count, stub_count, stub_ratio,
                  label_counts, rels, nodes, outgoing_index, sample_node, sample_type)
    return True


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <output_dir>", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(sys.argv[1])

    if not output_dir.is_dir():
        print(f"Error: {output_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    print(f"Smoke testing Property Graph JSONL in {output_dir} ...")
    print()

    ok = run_checks(output_dir)

    print()
    if ok:
        print("✅ All checks passed")
    else:
        print("❌ One or more checks failed")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
