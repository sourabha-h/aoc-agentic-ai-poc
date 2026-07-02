from __future__ import annotations

from typing import Any

from ..agent_state import AgentState, append_timeline, now


def run(state: AgentState) -> dict[str, Any]:
    if state.get("approval_status") == "rejected":
        return {
            "approval_status": "rejected",
            "agent_timeline": append_timeline(state, "approval_gate", "Guardrail rejected; skipping approval")
            + [{"agent": "approval_gate", "purpose": "approval_status", "approval_status": "rejected", "timestamp": now(), "status": "ok"}],
        }
    if state.get("auto_approve"):
        return {
            "approval_status": "approved",
            "agent_timeline": append_timeline(state, "approval_gate", "Auto-approved for test execution")
            + [{"agent": "approval_gate", "purpose": "approval_status", "approval_status": "approved", "timestamp": now(), "status": "ok"}],
        }
    return {
        "approval_status": "WAITING_FOR_APPROVAL",
        "agent_timeline": append_timeline(state, "approval_gate", "Waiting for approval", status="waiting")
        + [{"agent": "approval_gate", "purpose": "approval_status", "approval_status": "WAITING_FOR_APPROVAL", "timestamp": now(), "status": "waiting"}],
    }
