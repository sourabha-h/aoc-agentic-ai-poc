"""Minimal FastAPI surface for the mock agent workflow."""

from __future__ import annotations

import threading
from copy import deepcopy
import uuid
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agent_workflow import run_workflow
from .network_templates import NODES


class ScanRequest(BaseModel):
    scenario_id: str = "healthy_network"
    auto_approve: bool = False


app = FastAPI(title="AOC POC API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATE_LOCK = threading.Lock()
_WORKFLOW_STATE: dict[str, Any] = {
    "workflow_status": "ready",
    "scan_id": None,
    "result": None,
}


def _issue_affected_nodes(result: dict[str, Any]) -> list[dict[str, Any]]:
    node_map = {node["node_id"]: node["display_name"] for node in NODES}
    affected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for finding in result.get("active_findings", []) or result.get("initial_findings", []):
        node_id = finding.get("node_id")
        if node_id in {"archive_storage", "oracle_database"} and node_id not in seen:
            seen.add(node_id)
            affected.append(
                {
                    "node_id": node_id,
                    "display_name": node_map.get(node_id, node_id),
                }
            )
    return affected


def _build_consolidated_issues(result: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not result:
        return []

    findings = list(result.get("active_findings", []))
    archive_findings = [finding for finding in findings if finding.get("node_id") in {"archive_storage", "oracle_database"}]
    if not archive_findings:
        return []

    severity = "critical" if any(finding.get("severity") == "critical" for finding in archive_findings) else "warning"
    affected_nodes = _issue_affected_nodes(result)
    risk = "High" if severity == "critical" else "Medium"
    return [
        {
            "issue_id": "archive_storage_cleanup",
            "title": "Archive storage cleanup required",
            "summary": "Archive storage pressure is affecting the Oracle archive flow.",
            "affected_nodes": affected_nodes,
            "severity": severity,
            "recommended_action": "Approve cleanup_archive_storage remediation",
            "risk": risk,
            "action": "cleanup_archive_storage",
        }
    ]


def _final_status(result: dict[str, Any] | None) -> str:
    if not result:
        return ""
    if result.get("verification_status") == "healthy":
        return "Verified Healthy"
    return "Manual Review Required"


def _idle_topology() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "node_id": node["node_id"],
                "display_name": node["display_name"],
                "dependencies": list(node.get("dependencies", [])),
                "status": "not_scanned",
                "current_activity": "Waiting for scan",
            }
            for node in NODES
        ],
        "dependencies": [
            {"from": node["node_id"], "to": dependency}
            for node in NODES
            for dependency in node.get("dependencies", [])
        ],
    }


def _running_topology() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "node_id": node["node_id"],
                "display_name": node["display_name"],
                "dependencies": list(node.get("dependencies", [])),
                "status": "scanning",
                "current_activity": "Scanning...",
            }
            for node in NODES
        ],
        "dependencies": [
            {"from": node["node_id"], "to": dependency}
            for node in NODES
            for dependency in node.get("dependencies", [])
        ],
    }


def _build_node_guidance(result: dict[str, Any], node_id: str) -> dict[str, list[dict[str, Any]]]:
    timeline = result.get("agent_timeline", [])
    health_guidance = [
        item
        for item in timeline
        if item.get("purpose") == "health_check_guidance" and item.get("node_id") == node_id
    ]
    resolution_guidance = [
        item
        for item in timeline
        if item.get("purpose") == "resolution_guidance"
    ]
    return {
        "health_check_guidance": health_guidance[-1].get("rag_results", []) if health_guidance else [],
        "resolution_guidance": resolution_guidance[-1].get("rag_results", []) if resolution_guidance else [],
    }


def _build_audit_events(result: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for item in result.get("agent_timeline", []):
        timestamp = item.get("timestamp")
        agent = item.get("agent", "unknown")
        purpose = item.get("purpose", "")

        if item.get("event_type") == "LLM_CALL" or agent == "llm":
            events.append(
                {
                    "event_type": "LLM_CALL",
                    "timestamp": timestamp,
                    "agent": agent,
                    "summary": f"{purpose or 'llm'} via {item.get('source', 'fallback')}",
                    "details": {
                        "purpose": purpose,
                        "request_purpose": item.get("request_purpose", purpose),
                        "model": item.get("model", ""),
                        "source": item.get("source", "fallback"),
                        "status": item.get("status", "unknown"),
                        "error_type": item.get("error_type", ""),
                        "error_message": item.get("error_message", ""),
                        "parameter_names": item.get("parameter_names", []),
                    },
                }
            )
            continue

        if purpose in {"health_check_guidance", "resolution_guidance"}:
            rag_results = list(item.get("rag_results", []))
            if not rag_results:
                events.append(
                    {
                        "event_type": "RAG_QUERY",
                        "timestamp": timestamp,
                        "agent": agent,
                        "purpose": purpose,
                        "query": item.get("query", ""),
                        "vector_store": "ChromaDB",
                        "source_file": None,
                        "section": None,
                        "score": None,
                        "retrieved_content": "",
                        "summary": "No matching guidance found",
                        "details": {
                            "purpose": purpose,
                            "query": item.get("query", ""),
                            "vector_store": "ChromaDB",
                            "matches_found": 0,
                            "sources": [],
                        },
                    }
                )
                continue

            for match in rag_results:
                events.append(
                    {
                        "event_type": "RAG_QUERY",
                        "timestamp": timestamp,
                        "agent": agent,
                        "purpose": purpose,
                        "query": item.get("query", ""),
                        "vector_store": "ChromaDB",
                        "source_file": match.get("source_file"),
                        "section": match.get("section"),
                        "score": match.get("score"),
                        "retrieved_content": match.get("content", ""),
                        "summary": f"{match.get('source_file', 'runbook')} matched",
                        "details": {
                            "purpose": purpose,
                            "query": item.get("query", ""),
                            "vector_store": "ChromaDB",
                            "source_file": match.get("source_file"),
                            "section": match.get("section"),
                            "score": match.get("score"),
                            "retrieved_content": match.get("content", ""),
                        },
                    }
                )
            continue

        if purpose == "findings":
            for finding in item.get("findings", []):
                events.append(
                    {
                        "event_type": "FINDING_CREATED",
                        "timestamp": timestamp,
                        "agent": agent,
                        "summary": finding.get("summary", "Finding created"),
                        "details": finding,
                    }
                )
            continue

        if purpose == "plan":
            plan = item.get("plan", {})
            events.append(
                {
                    "event_type": "PLAN_CREATED",
                    "timestamp": timestamp,
                    "agent": agent,
                    "summary": plan.get("action", "Remediation plan created"),
                    "details": plan,
                }
            )
            continue

        if purpose == "guardrail_result":
            events.append(
                {
                    "event_type": "GUARDRAIL_RESULT",
                    "timestamp": timestamp,
                    "agent": agent,
                    "summary": item.get("result", "unknown"),
                    "details": item,
                }
            )
            continue

        if purpose == "approval_status":
            events.append(
                {
                    "event_type": "APPROVAL_STATUS",
                    "timestamp": timestamp,
                    "agent": agent,
                    "summary": item.get("approval_status", "unknown"),
                    "details": item,
                }
            )
            continue

        if purpose == "execution_result":
            events.append(
                {
                    "event_type": "REMEDIATION_EXECUTED",
                    "timestamp": timestamp,
                    "agent": agent,
                    "summary": f"{item.get('action', 'remediation')} attempt {item.get('remediation_attempts', 0)}",
                    "details": item,
                }
            )
            continue

        if purpose == "verification_result":
            events.append(
                {
                    "event_type": "VERIFICATION_RESULT",
                    "timestamp": timestamp,
                    "agent": agent,
                    "summary": item.get("verification_status", "unknown"),
                    "details": item,
                }
            )
            next_step = item.get("next_step")
            if next_step == "planning_retry":
                events.append(
                    {
                        "event_type": "RETRY_ROUTED",
                        "timestamp": timestamp,
                        "agent": agent,
                        "summary": "Retry routed back to planning",
                        "details": item,
                    }
                )
            elif next_step == "escalation":
                events.append(
                    {
                        "event_type": "ESCALATION",
                        "timestamp": timestamp,
                        "agent": agent,
                        "summary": "Escalation required",
                        "details": item,
                    }
                )
            continue

        if purpose == "retry_or_escalation":
            event_type = "ESCALATION" if item.get("result") == "escalation" else "RETRY_ROUTED"
            events.append(
                {
                    "event_type": event_type,
                    "timestamp": timestamp,
                    "agent": agent,
                    "summary": item.get("result", "unknown"),
                    "details": item,
                }
            )
            continue

        if purpose == "health_check_guidance" or purpose == "resolution_guidance":
            continue

        if item.get("command_selection"):
            selection = item.get("command_selection", {})
            events.append(
                {
                    "event_type": "COMMAND_SELECTED",
                    "timestamp": timestamp,
                    "agent": agent,
                    "summary": f"{item.get('node_id', 'node')} commands selected",
                    "details": selection,
                }
            )
        if item.get("command_outputs"):
            for command, output in item.get("command_outputs", {}).items():
                events.append(
                    {
                        "event_type": "COMMAND_EXECUTED",
                        "timestamp": timestamp,
                        "agent": agent,
                        "summary": command,
                        "details": {"command": command, "output": output},
                    }
                )

    return events


def _build_node_evidence(result: dict[str, Any], node_id: str) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for finding in result.get("initial_findings", []):
        if finding.get("node_id") == node_id:
            evidence.append(finding)
    for finding in result.get("active_findings", []):
        if finding.get("node_id") == node_id and finding not in evidence:
            evidence.append(finding)
    return evidence


def _enrich_inspected_nodes(result: dict[str, Any]) -> dict[str, Any]:
    inspected = deepcopy(result.get("inspected_nodes", {}))
    topology_nodes = {node["node_id"]: node for node in result.get("topology", {}).get("nodes", [])}
    for node_id, node in inspected.items():
        topology_node = topology_nodes.get(node_id, {})
        node["status"] = topology_node.get("status", "not_scanned")
        node["current_activity"] = topology_node.get("current_activity", "Waiting for scan")
        node["selected_commands"] = list(node.get("selected_commands", []))
        node["command_outputs"] = dict(node.get("command_outputs", {}))
        node["rag_guidance"] = _build_node_guidance(result, node_id)
        node["evidence_findings"] = _build_node_evidence(result, node_id)
    return inspected


def _topology_from_result(result: dict[str, Any] | None) -> dict[str, Any]:
    if not result:
        return _idle_topology()

    status = _WORKFLOW_STATE.get("workflow_status", "ready")
    if status == "running":
        return {
            "nodes": [
                {
                    "node_id": node["node_id"],
                    "display_name": node["display_name"],
                    "dependencies": list(node.get("dependencies", [])),
                    "status": "scanning",
                    "current_activity": "Scanning...",
                }
                for node in NODES
            ],
            "dependencies": [
                {"from": node["node_id"], "to": dependency}
                for node in NODES
                for dependency in node.get("dependencies", [])
            ],
        }

    inspected = result.get("inspected_nodes", {})
    active_findings = {finding.get("node_id"): finding for finding in result.get("active_findings", [])}
    verification_healthy = result.get("verification_status") == "healthy"
    nodes = []
    for node in NODES:
        node_id = node["node_id"]
        if node_id in active_findings:
            status_name = "critical" if active_findings[node_id].get("severity") == "critical" else "warning"
            current_activity = "Investigation complete"
        elif verification_healthy and any(finding.get("node_id") == node_id for finding in result.get("initial_findings", [])):
            status_name = "verified_healthy"
            current_activity = "Verified healthy"
        elif node_id in inspected:
            status_name = "healthy"
            current_activity = "Health check completed"
        else:
            status_name = "not_scanned"
            current_activity = "Waiting for scan"

        nodes.append(
            {
                "node_id": node_id,
                "display_name": node["display_name"],
                "dependencies": list(node.get("dependencies", [])),
                "status": status_name,
                "current_activity": current_activity,
            }
        )

    return {
        "nodes": nodes,
        "dependencies": [
            {"from": node["node_id"], "to": dependency}
            for node in NODES
            for dependency in node.get("dependencies", [])
        ],
    }


def _status_payload(state: dict[str, Any]) -> dict[str, Any]:
    workflow_status = state.get("workflow_status", "ready")
    result = state.get("result")

    if workflow_status == "running":
        return {
            "status": "ok",
            "workflow_status": "running",
            "scan_id": state.get("scan_id"),
            "topology": _running_topology(),
            "inspected_nodes": {},
            "initial_findings": [],
            "active_findings": [],
            "verification_status": "running",
            "approval_status": "running",
            "final_report": {},
            "final_status": "",
            "consolidated_issues": _build_consolidated_issues(result),
            "agent_timeline": [],
            "audit_events": [],
        }

    if workflow_status == "ready" or not result:
        return {
            "status": "idle",
            "workflow_status": "ready",
            "scan_id": state.get("scan_id"),
            "topology": _idle_topology(),
            "inspected_nodes": {},
            "initial_findings": [],
            "active_findings": [],
            "verification_status": "idle",
            "approval_status": "idle",
            "final_report": {},
            "final_status": "",
            "consolidated_issues": [],
            "agent_timeline": [],
            "audit_events": [],
        }

    if workflow_status == "waiting_approval":
        return {
            "status": "ok",
            "workflow_status": "waiting_approval",
            "scan_id": result.get("scan_id"),
            "topology": _topology_from_result(result),
            "inspected_nodes": _enrich_inspected_nodes(result),
            "initial_findings": deepcopy(result.get("initial_findings", [])),
            "active_findings": deepcopy(result.get("active_findings", [])),
            "verification_status": result.get("verification_status", "waiting"),
            "approval_status": "WAITING_FOR_APPROVAL",
            "final_report": deepcopy(result.get("final_report", {})),
            "final_status": "",
            "consolidated_issues": _build_consolidated_issues(result),
            "agent_timeline": deepcopy(result.get("agent_timeline", [])),
            "remediation_plan": deepcopy(result.get("remediation_plan", {})),
            "audit_events": _build_audit_events(result),
        }

    return {
        "status": "ok",
        "workflow_status": "completed",
        "scan_id": result.get("scan_id"),
        "topology": _topology_from_result(result),
        "inspected_nodes": _enrich_inspected_nodes(result),
        "initial_findings": deepcopy(result.get("initial_findings", [])),
        "active_findings": deepcopy(result.get("active_findings", [])),
        "verification_status": result.get("verification_status"),
        "approval_status": result.get("approval_status"),
        "final_report": deepcopy(result.get("final_report", {})),
        "final_status": _final_status(result),
        "consolidated_issues": _build_consolidated_issues(result),
        "agent_timeline": deepcopy(result.get("agent_timeline", [])),
        "remediation_plan": deepcopy(result.get("remediation_plan", {})),
        "audit_events": _build_audit_events(result),
    }


def _run_workflow_background(scan_id: str, auto_approve: bool) -> None:
    result = run_workflow(auto_approve=auto_approve)
    result["scan_id"] = scan_id
    with _STATE_LOCK:
        _WORKFLOW_STATE["result"] = result
        if result.get("approval_status") == "WAITING_FOR_APPROVAL" and not auto_approve:
            _WORKFLOW_STATE["workflow_status"] = "waiting_approval"
        else:
            _WORKFLOW_STATE["workflow_status"] = "completed"


def _start_background_scan(scenario_id: str, auto_approve: bool) -> dict[str, Any]:
    with _STATE_LOCK:
        if _WORKFLOW_STATE["workflow_status"] == "running":
            return _status_payload(_WORKFLOW_STATE)

        scan_id = f"scan_{uuid.uuid4().hex[:8]}"
        _WORKFLOW_STATE["workflow_status"] = "running"
        _WORKFLOW_STATE["scan_id"] = scan_id
        _WORKFLOW_STATE["result"] = None

    response = _status_payload({"workflow_status": "running", "scan_id": scan_id, "result": None})
    worker = threading.Thread(target=_run_workflow_background, args=(scan_id, auto_approve), daemon=True)
    worker.start()
    return response


def _reset_workflow_state() -> dict[str, Any]:
    with _STATE_LOCK:
        _WORKFLOW_STATE["workflow_status"] = "ready"
        _WORKFLOW_STATE["scan_id"] = None
        _WORKFLOW_STATE["result"] = None
        return _status_payload(dict(_WORKFLOW_STATE))


def _resume_after_approval() -> dict[str, Any]:
    with _STATE_LOCK:
        if _WORKFLOW_STATE["workflow_status"] != "waiting_approval" or not _WORKFLOW_STATE.get("scan_id"):
            raise ValueError("No workflow is waiting for approval.")
        scan_id = _WORKFLOW_STATE["scan_id"]
        _WORKFLOW_STATE["workflow_status"] = "running"

    response = _status_payload({"workflow_status": "running", "scan_id": scan_id, "result": None})
    worker = threading.Thread(target=_run_workflow_background, args=(scan_id, True), daemon=True)
    worker.start()
    return response


def get_latest_workflow_result() -> dict[str, Any] | None:
    with _STATE_LOCK:
        if _WORKFLOW_STATE.get("workflow_status") in {"completed", "waiting_approval"}:
            return _WORKFLOW_STATE.get("result")
        return None


@app.post("/api/scan")
def start_scan(payload: ScanRequest) -> dict[str, Any]:
    return _start_background_scan(payload.scenario_id, payload.auto_approve)


@app.post("/api/approve")
def approve_scan() -> dict[str, Any]:
    try:
        return _resume_after_approval()
    except ValueError as exc:
        return {
            "status": "error",
            "message": str(exc),
        }


@app.post("/api/reset")
def reset_demo() -> dict[str, Any]:
    return _reset_workflow_state()


@app.get("/api/status")
def get_status() -> dict[str, Any]:
    with _STATE_LOCK:
        return _status_payload(dict(_WORKFLOW_STATE))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.api:app", host="0.0.0.0", port=8000, reload=False)
