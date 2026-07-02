"""Mock network generator CLI."""

from __future__ import annotations

import argparse
import json
import random
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .network_templates import NODES
from .scenarios import SCENARIOS, get_scenario


DEFAULT_OUTPUT_DIR = Path("mock_network")
SIMULATOR_CONTROL_DIR = Path("simulator_control")
SCENARIO_FILE = SIMULATOR_CONTROL_DIR / "scenario.json"
RUNTIME_STATE_FILE = SIMULATOR_CONTROL_DIR / "runtime_state.json"
BASE_TIME = datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc)


def _timestamp(minutes: int) -> str:
    return (BASE_TIME + timedelta(minutes=minutes)).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _node_observations(node_id: str, scenario_id: str, stage: str) -> dict[str, Any]:
    rng = random.Random(f"{scenario_id}:{node_id}:{stage}")
    base = {
        "node_id": node_id,
        "status": "healthy",
        "cpu_percent": round(20 + rng.random() * 10, 1),
        "memory_percent": round(25 + rng.random() * 10, 1),
        "disk_percent": round(30 + rng.random() * 10, 1),
        "service_status": "running",
        "queue_depth": 0,
        "latency_ms": int(20 + rng.random() * 20),
        "error_messages": [],
    }

    if scenario_id == "archive_storage_cleanup_retry_success":
        if stage == "initial":
            if node_id == "archive_storage":
                base.update(
                    {
                        "status": "critical",
                        "disk_percent": 97.2,
                        "service_status": "degraded",
                        "error_messages": ["Archive storage above safe capacity"],
                    }
                )
            elif node_id == "oracle_database":
                base["error_messages"] = ["ORA-19809: limit exceeded for recovery files"]
                base["latency_ms"] = 140
        elif stage == "remediation_attempt_1":
            if node_id == "archive_storage":
                base.update(
                    {
                        "status": "critical",
                        "disk_percent": 96.8,
                        "service_status": "degraded",
                        "error_messages": ["Cleanup incomplete", "Archive storage still above safe capacity"],
                    }
                )
            elif node_id == "oracle_database":
                base["error_messages"] = [
                    "ORA-19809: limit exceeded for recovery files",
                    "Verification failed",
                ]
                base["latency_ms"] = 132
        elif stage == "remediation_attempt_2":
            if node_id == "archive_storage":
                base.update(
                    {
                        "status": "healthy",
                        "disk_percent": 82.4,
                        "service_status": "running",
                        "error_messages": [],
                    }
                )
            elif node_id == "oracle_database":
                base["error_messages"] = []
                base["latency_ms"] = 28

    elif scenario_id == "archive_storage_cleanup_fail":
        if node_id == "archive_storage":
            base.update(
                {
                    "status": "degraded",
                    "disk_percent": 97.8,
                    "service_status": "degraded",
                    "error_messages": ["Cleanup did not reclaim enough space"],
                }
            )
        elif node_id == "oracle_database":
            base["error_messages"] = ["ORA-19809: limit exceeded for recovery files"]

    elif scenario_id == "archive_storage_cleanup_success":
        if node_id == "archive_storage":
            base.update({"disk_percent": 84.0, "error_messages": []})
        elif node_id == "oracle_database":
            base["error_messages"] = ["ORA-19809: limit exceeded for recovery files"]

    elif scenario_id == "archive_storage_cleanup_escalation":
        if node_id == "archive_storage":
            base.update(
                {
                    "status": "critical",
                    "disk_percent": 98.1,
                    "service_status": "critical",
                    "error_messages": ["Repeated cleanup attempts require escalation"],
                }
            )
        elif node_id == "oracle_database":
            base["error_messages"] = ["ORA-19809: limit exceeded for recovery files"]

    elif scenario_id == "partial_recovery_dependency_issue":
        if node_id == "archive_storage":
            base.update({"status": "warning", "disk_percent": 91.5, "error_messages": ["Storage pressure reduced"]})
        elif node_id == "oracle_database":
            base.update({"status": "warning", "latency_ms": 120, "error_messages": ["Dependency lag observed"]})
        elif node_id == "mediation_server":
            base.update({"status": "warning", "queue_depth": 18, "error_messages": ["Backlog reduced but not cleared"]})

    elif scenario_id == "multiple_parallel_issues":
        if node_id == "archive_storage":
            base.update({"status": "degraded", "disk_percent": 97.7, "error_messages": ["Archive pressure persists"]})
        elif node_id == "sms_gateway":
            base.update({"status": "degraded", "queue_depth": 88, "error_messages": ["SMS queue backlog exceeded"]})
        elif node_id == "api_gateway":
            base.update({"status": "degraded", "latency_ms": 140, "error_messages": ["Routing latency increased"]})

    elif scenario_id == "guardrail_rejection":
        if node_id == "archive_storage":
            base.update({"status": "warning", "disk_percent": 96.5, "error_messages": ["Unsafe cleanup request rejected"]})

    return base


def _node_log(node_id: str, scenario_id: str, stage: str) -> str:
    lines = [
        f"{_timestamp(0)} INFO {node_id} startup completed",
        f"{_timestamp(1)} INFO services initialized",
    ]

    if scenario_id == "archive_storage_cleanup_retry_success":
        if stage == "initial":
            if node_id == "archive_storage":
                lines += [
                    f"{_timestamp(10)} WARN archive storage above safe capacity",
                    f"{_timestamp(11)} ERROR archive cleanup required",
                ]
            elif node_id == "oracle_database":
                lines += [
                    f"{_timestamp(10)} ERROR ORA-19809: limit exceeded for recovery files",
                    f"{_timestamp(11)} WARN Oracle archive destination unavailable",
                ]
        elif stage == "remediation_attempt_1":
            if node_id == "archive_storage":
                lines += [
                    f"{_timestamp(10)} WARN cleanup in progress",
                    f"{_timestamp(11)} ERROR cleanup incomplete",
                ]
            elif node_id == "oracle_database":
                lines += [
                    f"{_timestamp(10)} ERROR ORA-19809: limit exceeded for recovery files",
                    f"{_timestamp(11)} ERROR verification failed",
                ]
        elif stage == "remediation_attempt_2":
            if node_id == "archive_storage":
                lines += [
                    f"{_timestamp(10)} INFO cleanup completed",
                    f"{_timestamp(11)} INFO storage usage returned to normal",
                ]
            elif node_id == "oracle_database":
                lines += [
                    f"{_timestamp(10)} INFO Oracle archive destination recovered",
                    f"{_timestamp(11)} INFO verification passed",
                ]

    elif scenario_id == "archive_storage_cleanup_success":
        if node_id == "archive_storage":
            lines += [
                f"{_timestamp(10)} WARN archive storage above safe capacity",
                f"{_timestamp(11)} INFO cleanup completed",
            ]
        elif node_id == "oracle_database":
            lines += [
                f"{_timestamp(10)} ERROR ORA-19809: limit exceeded for recovery files",
                f"{_timestamp(11)} INFO Oracle archive destination recovered",
            ]

    elif scenario_id == "archive_storage_cleanup_fail":
        if node_id == "archive_storage":
            lines += [
                f"{_timestamp(10)} WARN archive storage above safe capacity",
                f"{_timestamp(11)} ERROR cleanup incomplete",
            ]
        elif node_id == "oracle_database":
            lines += [
                f"{_timestamp(10)} ERROR ORA-19809: limit exceeded for recovery files",
                f"{_timestamp(11)} ERROR archive destination remains blocked",
            ]

    elif scenario_id == "archive_storage_cleanup_escalation":
        if node_id == "archive_storage":
            lines += [
                f"{_timestamp(10)} WARN archive storage above safe capacity",
                f"{_timestamp(11)} WARN escalation required",
            ]
        elif node_id == "oracle_database":
            lines += [
                f"{_timestamp(10)} ERROR ORA-19809: limit exceeded for recovery files",
                f"{_timestamp(11)} WARN escalation requested",
            ]

    elif scenario_id == "partial_recovery_dependency_issue":
        if node_id == "archive_storage":
            lines += [
                f"{_timestamp(10)} INFO storage pressure reduced",
                f"{_timestamp(11)} WARN verification pending",
            ]
        elif node_id == "oracle_database":
            lines += [
                f"{_timestamp(10)} WARN dependency lag observed",
                f"{_timestamp(11)} INFO partial recovery noted",
            ]
        elif node_id == "mediation_server":
            lines += [
                f"{_timestamp(10)} WARN backlog reduced but not cleared",
            ]

    elif scenario_id == "multiple_parallel_issues":
        if node_id == "archive_storage":
            lines += [
                f"{_timestamp(10)} WARN archive storage pressure persists",
            ]
        elif node_id == "sms_gateway":
            lines += [
                f"{_timestamp(10)} WARN SMS queue backlog exceeded",
            ]
        elif node_id == "api_gateway":
            lines += [
                f"{_timestamp(10)} WARN routing latency increased",
            ]

    elif scenario_id == "guardrail_rejection":
        if node_id == "archive_storage":
            lines += [
                f"{_timestamp(10)} WARN cleanup request rejected by guardrail",
            ]

    return "\n".join(lines) + "\n"


def _policy(node_id: str) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "healthy_thresholds": {
            "cpu_percent": 75,
            "memory_percent": 80,
            "disk_percent": 85,
            "latency_ms": 100,
        },
    }


def _topology() -> dict[str, Any]:
    deps = []
    for node in NODES:
        for dependency in node["dependencies"]:
            deps.append({"from": node["node_id"], "to": dependency})
    return {
        "generated_at": BASE_TIME.isoformat(),
        "nodes": [
            {
                "node_id": node["node_id"],
                "display_name": node["display_name"],
                "dependencies": node["dependencies"],
            }
            for node in NODES
        ],
        "dependencies": deps,
    }


def _write_private_control(scenario_id: str, stage: str, attempts: int) -> None:
    control = {
        "scenario": get_scenario(scenario_id),
        "runtime_state": {
            "scenario_id": scenario_id,
            "stage": stage,
            "remediation_attempts": attempts,
        },
    }
    _write_json(SCENARIO_FILE, control["scenario"])
    _write_json(RUNTIME_STATE_FILE, control["runtime_state"])


def render_network(scenario_id: str, stage: str = "initial") -> dict[str, Any]:
    _reset_dir(DEFAULT_OUTPUT_DIR)
    _write_json(DEFAULT_OUTPUT_DIR / "topology.json", _topology())

    for node in NODES:
        node_dir = DEFAULT_OUTPUT_DIR / "nodes" / node["node_id"]
        _write_json(
            node_dir / "configuration.json",
            {
                "node_id": node["node_id"],
                "display_name": node["display_name"],
                "dependencies": node["dependencies"],
            },
        )
        _write_json(node_dir / "observations.json", _node_observations(node["node_id"], scenario_id, stage))
        _write_json(node_dir / "healthy_node_policy.json", _policy(node["node_id"]))
        _write_text(node_dir / "application.log", _node_log(node["node_id"], scenario_id, stage))

    return {"scenario_id": scenario_id, "stage": stage}


def generate_network(scenario_id: str) -> dict[str, Any]:
    scenario = get_scenario(scenario_id)
    render_network(scenario_id, "initial")
    _write_private_control(scenario_id, "initial", 0)
    return {"scenario_id": scenario["scenario_id"], "stage": "initial"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the mock telecom OSS/BSS network.")
    parser.add_argument("--scenario", required=True, choices=sorted(SCENARIOS))
    args = parser.parse_args(argv)
    generate_network(args.scenario)
    print(json.dumps({"status": "ok", "scenario_id": args.scenario}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
