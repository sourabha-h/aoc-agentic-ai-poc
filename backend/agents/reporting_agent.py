from __future__ import annotations

import json
from typing import Any

from ..agent_state import AgentState, append_timeline
from ..llm_client import llm_audit_event, llm_generate


def run(state: AgentState) -> dict[str, Any]:
    if state.get("final_report", {}).get("status") == "escalated":
        return {
            "agent_timeline": append_timeline(state, "reporting_agent", "Preserved escalation report"),
        }

    active_findings = list(state.get("active_findings", []))
    findings_json = json.dumps(active_findings, indent=2, sort_keys=True)
    rag_json = json.dumps(state.get("rag_results", {}), indent=2, sort_keys=True)
    plan_json = json.dumps(state.get("remediation_plan", {}), indent=2, sort_keys=True)
    source, content, settings, success, error_type, error_message = llm_generate(
        "You write concise operational status reports.",
        f"Scan ID: {state.get('scan_id')}\nFindings:\n{findings_json}\n\nRunbooks:\n{rag_json}\n\nPlan:\n{plan_json}\n\nReturn a short status report.",
    )

    if source == "llm" and success:
        report = {"source": source, "summary": content}
    else:
        if state.get("approval_status") == "WAITING_FOR_APPROVAL":
            summary = "Waiting for approval."
        elif state.get("approval_status") == "rejected":
            summary = "Guardrail rejected the proposed remediation."
        elif state.get("verification_status") == "healthy":
            summary = "Verification passed and the network is healthy."
        elif active_findings:
            summary = f"{len(active_findings)} findings detected across {len(state.get('inspected_nodes', {}))} nodes."
        else:
            summary = "No findings detected. Network is healthy."
        report = {"source": source, "summary": summary}

    return {
        "final_report": report,
        "agent_timeline": append_timeline(state, "reporting_agent", f"Generated final report using {source}") + [
            llm_audit_event("reporting", settings, source, success, error_type, error_message)
        ],
    }
