"""Read-only inspection helpers for the mock network."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .network_templates import NODES


OUTPUT_DIR = Path("mock_network")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def get_topology() -> dict:
    """Return the current public topology."""

    return _read_json(OUTPUT_DIR / "topology.json")


def inspect_node(node_id: str) -> dict:
    """Return the current public files for one node."""

    node_dir = OUTPUT_DIR / "nodes" / node_id
    return {
        "node_id": node_id,
        "configuration": _read_json(node_dir / "configuration.json"),
        "observations": _read_json(node_dir / "observations.json"),
        "healthy_node_policy": _read_json(node_dir / "healthy_node_policy.json"),
        "application_log": _read_text(node_dir / "application.log").splitlines(),
    }


def inspect_all_nodes() -> dict:
    """Return topology and all node inspections."""

    return {
        "topology": get_topology(),
        "nodes": [inspect_node(node["node_id"]) for node in NODES],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only inspection tools for the mock network.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scan-all", help="Inspect the full mock network.")

    node_parser = subparsers.add_parser("scan-node", help="Inspect one node.")
    node_parser.add_argument("--node", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan-all":
        print(json.dumps(inspect_all_nodes(), indent=2, sort_keys=True))
        return 0

    if args.command == "scan-node":
        print(json.dumps(inspect_node(args.node), indent=2, sort_keys=True))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
