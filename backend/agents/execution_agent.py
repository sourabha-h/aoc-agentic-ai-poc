from __future__ import annotations

from typing import Any

from ..agent_state import AgentState, append_timeline, now
from ..simulator import apply_remediation


def run(state: AgentState) -> dict[str, Any]:
    if state.get("approval_status") != "approved":
        return {"agent_timeline": append_timeline(state, "execution_agent", "Skipped; not approved")}

    action = state.get("remediation_plan", {}).get("action", "cleanup_archive_storage")
    runtime_state = apply_remediation(action)
    return {
        "remediation_attempts": runtime_state.get("remediation_attempts", 0),
        "agent_timeline": append_timeline(
            state,
            "execution_agent",
            f"Applied {action} using simulator flow; attempts={runtime_state.get('remediation_attempts', 0)}",
        )
        + [
            {
                "agent": "execution_agent",
                "purpose": "execution_result",
                "action": action,
                "remediation_attempts": runtime_state.get("remediation_attempts", 0),
                "timestamp": now(),
                "status": "ok",
            }
        ],
    }
