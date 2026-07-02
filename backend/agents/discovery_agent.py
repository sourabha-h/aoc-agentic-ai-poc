from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..agent_state import (
    AgentState,
    build_rag_query,
    fallback_commands,
    filter_rag_results,
    health_check_query,
    parse_command_findings,
    now,
)
from ..inspection_tools import get_topology
from ..llm_client import llm_audit_event, llm_generate
from ..mock_shell import execute_command
from ..rag_ingest import VECTOR_STORE_DIR, ingest_runbooks
from ..rag_retriever import search_runbooks


def _choose_commands(node_id: str, display_name: str, guidance: dict[str, Any]) -> tuple[str, list[str], dict[str, Any]]:
    allowed = ["df -kh", "top", "ps -ef", "tail -100 application.log", "service --status-all", "sqlplus archive-status-check"]
    guidance_text = json.dumps(guidance, sort_keys=True)
    source, content, settings, success, error_type, error_message = llm_generate(
        (
            "Choose a small set of shell commands for telecom node discovery. Return valid JSON only. No Markdown fences. "
            "No explanation. One JSON object only. Maximum 3 commands. Use only allowed commands. "
            "Example:\n{\n  \"commands\": [\n    \"df -kh\",\n    \"tail -100 application.log\"\n  ]\n}"
        ),
        (
            f"Node: {node_id}\n"
            f"Display name: {display_name}\n"
            f"Allowed commands: {allowed}\n"
            f"Health-check guidance: {guidance_text}\n"
            "Return only JSON like {\"commands\": [..]}."
        ),
        response_format={"type": "json_object"},
        temperature=0,
    )
    if source == "llm":
        try:
            parsed = json.loads(content)
            commands = [cmd for cmd in parsed.get("commands", []) if cmd in allowed]
            if commands:
                return source, commands[:3], llm_audit_event("command_selection", settings, source, success, error_type, error_message)
        except Exception:
            pass
    if source == "llm" and success:
        return (
            "fallback",
            fallback_commands(node_id)[:3],
            llm_audit_event(
                "command_selection",
                settings,
                "llm",
                False,
                "invalid_json_response",
                "LLM response could not be parsed as JSON.",
            ),
        )
    return "fallback", fallback_commands(node_id)[:3], llm_audit_event("command_selection", settings, source, success, error_type, error_message)


def run(state: AgentState) -> dict[str, Any]:
    topology = get_topology()
    node_map = {node["node_id"]: node for node in topology.get("nodes", []) if node["node_id"] in {
        "billing_server",
        "oracle_database",
        "archive_storage",
        "order_platform",
        "subscriber_platform",
        "sms_gateway",
        "api_gateway",
    }}
    inspected_nodes: dict[str, dict[str, Any]] = {}
    initial_findings: list[dict[str, Any]] = []
    rag_guidance: dict[str, Any] = {}
    timeline_entries: list[dict[str, Any]] = []
    job_specs: dict[str, dict[str, Any]] = {}

    if not VECTOR_STORE_DIR.exists():
        ingest_runbooks()

    for node_id, node in node_map.items():
        guidance_query = health_check_query(node_id, node["display_name"])
        guidance = search_runbooks(guidance_query, top_k=8)
        guidance = filter_rag_results(guidance, {"symptoms", "health_checks"})
        guidance["results"] = guidance.get("results", [])[:3]
        source, commands, llm_event = _choose_commands(node_id, node["display_name"], guidance)
        job_specs[node_id] = {
            "display_name": node["display_name"],
            "guidance": guidance,
            "command_source": source,
            "commands": commands,
        }
        timeline_entries.append(
            {
                "agent": "discovery_agent",
                "purpose": "health_check_guidance",
                "node_id": node_id,
                "query": guidance_query,
                "rag_results": guidance.get("results", []),
                "timestamp": now(),
                "status": "ok",
            }
        )
        timeline_entries.append(llm_event)

    def inspect_one(node_id: str) -> tuple[str, dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
        node = node_map[node_id]
        job = job_specs[node_id]
        commands = job["commands"]
        outputs = {command: execute_command(node_id, command) for command in commands}
        findings_local = parse_command_findings(node_id, outputs)
        inspected = {
            "node_id": node_id,
            "display_name": node["display_name"],
            "selected_commands": commands,
            "command_outputs": outputs,
        }
        timeline_entry = {
            "agent": "discovery_agent",
            "node_id": node_id,
            "command_selection": {"source": job["command_source"], "commands": commands},
            "command_outputs": outputs,
            "rag_guidance": job["guidance"].get("results", [])[:2],
            "timestamp": now(),
            "status": "ok",
        }
        return node_id, inspected, findings_local, timeline_entry

    with ThreadPoolExecutor(max_workers=min(4, max(1, len(node_map)))) as pool:
        for node_id, inspected, node_findings, timeline_entry in pool.map(inspect_one, node_map):
            inspected_nodes[node_id] = inspected
            initial_findings.extend(node_findings)
            rag_guidance[node_id] = timeline_entry["rag_guidance"]
            timeline_entries.append(timeline_entry)

    resolution_guidance: dict[str, Any] = {}
    if initial_findings:
        resolution_query = build_rag_query(initial_findings) or "archive storage oracle error remediation"
        resolution_guidance = search_runbooks(resolution_query, top_k=8)
        if resolution_guidance.get("status") == "vector_store_missing":
            ingest_runbooks()
            resolution_guidance = search_runbooks(resolution_query, top_k=8)
        resolution_guidance = filter_rag_results(resolution_guidance, {"recommended_actions", "risk_level", "verification_steps"})
        resolution_guidance["results"] = resolution_guidance.get("results", [])[:3]
        timeline_entries.append(
            {
                "agent": "discovery_agent",
                "purpose": "resolution_guidance",
                "query": resolution_query,
                "rag_results": resolution_guidance.get("results", []),
                "timestamp": now(),
                "status": "ok",
            }
        )

    timeline_entries.append(
        {
            "agent": "discovery_agent",
            "purpose": "findings",
            "findings": initial_findings,
            "timestamp": now(),
            "status": "ok",
        }
    )

    return {
        "topology": topology,
        "inspected_nodes": inspected_nodes,
        "initial_findings": initial_findings,
        "active_findings": list(initial_findings),
        "rag_results": {"health_check_guidance": rag_guidance, "resolution_guidance": resolution_guidance},
        "agent_timeline": timeline_entries
        + [
            {
                "agent": "discovery_agent",
                "status": "ok",
                "message": f"Inspected {len(inspected_nodes)} nodes with mocked commands and found {len(initial_findings)} findings",
                "timestamp": now(),
            }
        ],
    }
