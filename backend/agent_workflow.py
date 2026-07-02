"""Minimal LangGraph workflow for the mock network."""

from __future__ import annotations

import argparse
import json
from typing import Any

from langgraph.graph import END, StateGraph

from .agent_state import AgentState
from .agents.approval_agent import run as approval_gate
from .agents.discovery_agent import run as discovery_agent
from .agents.escalation_agent import run as escalation_agent
from .agents.execution_agent import run as execution_agent
from .agents.guardrail_agent import run as guardrail_agent
from .agents.planning_agent import run as planning_agent
from .agents.reporting_agent import run as reporting_agent
from .agents.supervisor_agent import run as supervisor_start
from .agents.verification_agent import run as verification_agent
from .llm_client import llm_audit_event as _llm_audit_event
from .llm_client import llm_generate as _llm_generate
from .llm_client import llm_settings as _llm_settings


def build_workflow():
    graph = StateGraph(AgentState)
    graph.add_node("supervisor_start", supervisor_start)
    graph.add_node("discovery_agent", discovery_agent)
    graph.add_node("planning_agent", planning_agent)
    graph.add_node("guardrail_agent", guardrail_agent)
    graph.add_node("approval_gate", approval_gate)
    graph.add_node("execution_agent", execution_agent)
    graph.add_node("verification_agent", verification_agent)
    graph.add_node("escalation_agent", escalation_agent)
    graph.add_node("reporting_agent", reporting_agent)

    graph.add_edge("supervisor_start", "discovery_agent")
    graph.add_conditional_edges(
        "discovery_agent",
        lambda state: "planning_agent" if state.get("active_findings") else "reporting_agent",
        {"planning_agent": "planning_agent", "reporting_agent": "reporting_agent"},
    )
    graph.add_edge("planning_agent", "guardrail_agent")
    graph.add_conditional_edges(
        "guardrail_agent",
        lambda state: "reporting_agent" if state.get("approval_status") == "rejected" else "approval_gate",
        {"approval_gate": "approval_gate", "reporting_agent": "reporting_agent"},
    )
    graph.add_conditional_edges(
        "approval_gate",
        lambda state: "reporting_agent" if state.get("approval_status") == "WAITING_FOR_APPROVAL" else "execution_agent",
        {"execution_agent": "execution_agent", "reporting_agent": "reporting_agent"},
    )
    graph.add_edge("execution_agent", "verification_agent")
    graph.add_conditional_edges(
        "verification_agent",
        lambda state: (
            "reporting_agent"
            if state.get("verification_status") == "healthy"
            else "planning_agent"
            if int(state.get("remediation_attempts", 0)) < 2
            else "escalation_agent"
        ),
        {"planning_agent": "planning_agent", "escalation_agent": "escalation_agent", "reporting_agent": "reporting_agent"},
    )
    graph.add_edge("escalation_agent", "reporting_agent")
    graph.add_edge("reporting_agent", END)
    graph.set_entry_point("supervisor_start")
    return graph.compile()


def run_workflow(auto_approve: bool = False) -> dict[str, Any]:
    workflow = build_workflow()
    result = workflow.invoke({"agent_timeline": [], "auto_approve": auto_approve})
    return {
        "scan_id": result.get("scan_id"),
        "topology": result.get("topology", {}),
        "inspected_nodes": result.get("inspected_nodes", {}),
        "initial_findings": result.get("initial_findings", []),
        "active_findings": result.get("active_findings", []),
        "rag_results": result.get("rag_results", {}),
        "remediation_plan": result.get("remediation_plan", {}),
        "approval_status": result.get("approval_status"),
        "verification_status": result.get("verification_status"),
        "remediation_attempts": result.get("remediation_attempts", 0),
        "final_report": result.get("final_report", {}),
        "agent_timeline": result.get("agent_timeline", []),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the minimal LangGraph agent workflow.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="Run the workflow.")
    run_parser.add_argument("--auto-approve", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "run":
        print(json.dumps(run_workflow(auto_approve=getattr(args, "auto_approve", False)), indent=2, sort_keys=True))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
