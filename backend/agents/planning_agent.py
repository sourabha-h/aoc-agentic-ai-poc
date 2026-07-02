from __future__ import annotations

import json
from typing import Any

from ..agent_state import AgentState, append_timeline, now
from ..llm_client import llm_audit_event, llm_generate


def run(state: AgentState) -> dict[str, Any]:
    active_findings = list(state.get("active_findings", []))
    if not active_findings:
        return {
            "remediation_plan": {
                "mode": "not_needed",
                "source": "fallback",
                "steps": [],
                "message": "No remediation required.",
            },
            "agent_timeline": append_timeline(state, "planning_agent", "Skipped; no findings"),
        }

    findings_json = json.dumps(active_findings, indent=2, sort_keys=True)
    rag_json = json.dumps(state.get("rag_results", {}).get("resolution_guidance", {}), indent=2, sort_keys=True)
    source, content, settings, success, error_type, error_message = llm_generate(
        "You create short telecom remediation plans.",
        f"Findings:\n{findings_json}\n\nRunbook matches:\n{rag_json}\n\nReturn a concise remediation plan.",
    )
    if source == "llm" and success:
        plan = {"mode": "planned", "source": source, "summary": content, "action": "cleanup_archive_storage", "risk_level": "medium"}
    else:
        plan = {
            "mode": "planned",
            "source": source,
            "summary": "Review the affected node, validate archive storage usage, and confirm the Oracle archive error clears after cleanup.",
            "action": "cleanup_archive_storage",
            "risk_level": "medium",
        }

    return {
        "remediation_plan": plan,
        "agent_timeline": append_timeline(state, "planning_agent", f"Created remediation plan using {source}") + [
            llm_audit_event("remediation_planning", settings, source, success, error_type, error_message),
            {
                "agent": "planning_agent",
                "purpose": "plan",
                "plan": plan,
                "timestamp": now(),
                "status": "ok",
            },
        ],
    }
