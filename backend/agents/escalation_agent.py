from __future__ import annotations

import json
from typing import Any

from ..agent_state import AgentState, append_timeline, now
from ..llm_client import llm_audit_event, llm_generate


def run(state: AgentState) -> dict[str, Any]:
    source, content, settings, success, error_type, error_message = llm_generate(
        "You write short escalation notes for operations.",
        json.dumps({"findings": state.get("active_findings", []), "attempts": state.get("remediation_attempts", 0)}, indent=2, sort_keys=True),
    )
    note = content if source == "llm" and success else "Escalate to human operations due to repeated remediation failure."
    return {
        "final_report": {"source": source, "summary": note, "status": "escalated"},
        "agent_timeline": append_timeline(state, "escalation_agent", f"Escalated using {source}") + [
            llm_audit_event("remediation_planning", settings, source, success, error_type, error_message),
            {
                "agent": "escalation_agent",
                "purpose": "retry_or_escalation",
                "result": "escalation",
                "timestamp": now(),
                "status": "ok",
            },
        ],
    }
