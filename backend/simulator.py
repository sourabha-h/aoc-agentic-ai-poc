"""Private simulator control for the mock network."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .generator import (
    DEFAULT_OUTPUT_DIR,
    RUNTIME_STATE_FILE,
    SCENARIO_FILE,
    render_network,
)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_runtime_state() -> dict[str, Any] | None:
    return _read_json(RUNTIME_STATE_FILE)


def _save_runtime_state(state: dict[str, Any]) -> None:
    _write_json(RUNTIME_STATE_FILE, state)


def _status_payload(state: dict[str, Any] | None) -> dict[str, Any]:
    if not state:
        return {"status": "idle"}
    return {
        "status": "active",
        "scenario_id": state["scenario_id"],
        "stage": state["stage"],
        "remediation_attempts": state["remediation_attempts"],
    }


def _apply_cleanup_archive_storage() -> dict[str, Any]:
    state = _load_runtime_state()
    if not state:
        raise SystemExit("No active runtime state. Run the generator first.")

    attempts = int(state["remediation_attempts"])
    if attempts == 0:
        state = {"scenario_id": state["scenario_id"], "stage": "remediation_attempt_1", "remediation_attempts": 1}
        render_network(state["scenario_id"], state["stage"])
        _save_runtime_state(state)
        return state

    if attempts == 1:
        state = {"scenario_id": state["scenario_id"], "stage": "remediation_attempt_2", "remediation_attempts": 2}
        render_network(state["scenario_id"], state["stage"])
        _save_runtime_state(state)
        return state

    return state


def apply_remediation(action: str) -> dict[str, Any]:
    if action != "cleanup_archive_storage":
        raise ValueError(f"Unsupported action: {action}")
    return _apply_cleanup_archive_storage()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Private simulator control.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    apply_parser = subparsers.add_parser("apply-remediation", help="Apply a remediation action.")
    apply_parser.add_argument("--action", required=True, choices=["cleanup_archive_storage"])

    subparsers.add_parser("status", help="Show runtime state.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "status":
        print(json.dumps(_status_payload(_load_runtime_state()), indent=2, sort_keys=True))
        return 0

    if args.command == "apply-remediation":
        state = _apply_cleanup_archive_storage()
        print(json.dumps(_status_payload(state), indent=2, sort_keys=True))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
