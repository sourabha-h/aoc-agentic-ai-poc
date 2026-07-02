from __future__ import annotations

import json
from typing import Any

from ..agent_state import AgentState, append_timeline, now


def run(state: AgentState) -> dict[str, Any]:
    plan_text = json.dumps(state.get("remediation_plan", {}), sort_keys=True).lower()
    finding_text = json.dumps(state.get("active_findings", []), sort_keys=True).lower()
    rejected = any(token in plan_text or token in finding_text for token in ["rejected", "unsafe", "guardrail"])
    status = "rejected" if rejected else "approved"
    return {
        "approval_status": status,
        "agent_timeline": append_timeline(state, "guardrail_agent", f"Guardrail {status}") + [
            {
                "agent": "guardrail_agent",
                "purpose": "guardrail_result",
                "result": status,
                "timestamp": now(),
                "status": "ok",
            }
        ],
    }
