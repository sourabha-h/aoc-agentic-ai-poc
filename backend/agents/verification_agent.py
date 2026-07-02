from __future__ import annotations

from typing import Any

from ..agent_state import AgentState, append_timeline, now, parse_command_findings, verification_commands, verification_findings
from ..mock_shell import execute_command


def run(state: AgentState) -> dict[str, Any]:
    target_nodes = sorted({"archive_storage", "oracle_database"} | {finding["node_id"] for finding in state.get("active_findings", [])})
    outputs_by_node: dict[str, dict[str, str]] = {}
    for node_id in target_nodes:
        commands = verification_commands(node_id)
        outputs_by_node[node_id] = {command: execute_command(node_id, command) for command in commands}

    healthy = not verification_findings(outputs_by_node)
    status = "healthy" if healthy else "unhealthy"
    active_findings = [] if healthy else [
        finding for node_id, outputs in outputs_by_node.items() for finding in parse_command_findings(node_id, outputs)
    ]
    return {
        "verification_status": status,
        "active_findings": active_findings,
        "agent_timeline": append_timeline(
            state,
            "verification_agent",
            f"Verification {status} after re-running mock shell checks",
        )
        + [
            {
                "agent": "verification_agent",
                "purpose": "verification_result",
                "verification_status": status,
                "next_step": "reporting" if healthy else "planning_retry" if int(state.get("remediation_attempts", 0)) < 2 else "escalation",
                "timestamp": now(),
                "status": "ok",
            }
        ],
    }
