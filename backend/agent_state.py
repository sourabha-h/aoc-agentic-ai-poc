"""Shared workflow state and small helper functions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TypedDict


NODE_IDS = [
    "billing_server",
    "oracle_database",
    "archive_storage",
    "order_platform",
    "subscriber_platform",
    "sms_gateway",
    "api_gateway",
]


class AgentState(TypedDict, total=False):
    scan_id: str
    auto_approve: bool
    topology: dict[str, Any]
    inspected_nodes: dict[str, dict[str, Any]]
    initial_findings: list[dict[str, Any]]
    active_findings: list[dict[str, Any]]
    rag_results: dict[str, Any]
    remediation_plan: dict[str, Any]
    approval_status: str
    verification_status: str
    remediation_attempts: int
    final_report: dict[str, Any]
    agent_timeline: list[dict[str, Any]]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_timeline(state: AgentState, agent: str, message: str, status: str = "ok") -> list[dict[str, Any]]:
    timeline = list(state.get("agent_timeline", []))
    timeline.append({"agent": agent, "status": status, "message": message, "timestamp": now()})
    return timeline


def filter_rag_results(results: dict[str, Any], allowed_sections: set[str]) -> dict[str, Any]:
    filtered = dict(results)
    filtered["results"] = [item for item in results.get("results", []) if item.get("section") in allowed_sections]
    return filtered


def health_check_query(node_id: str, display_name: str) -> str:
    queries = {
        "oracle_database": "Oracle database archive destination health check ORA-19809 archive writer status",
        "archive_storage": "archive storage disk usage capacity threshold cleanup health check",
        "api_gateway": "API gateway routing timeout latency health check",
    }
    return queries.get(node_id, f"{display_name} health check symptoms checks thresholds")


def fallback_commands(node_id: str) -> list[str]:
    return {
        "archive_storage": ["df -kh", "tail -100 application.log", "service --status-all"],
        "oracle_database": ["sqlplus archive-status-check", "tail -100 application.log", "service --status-all"],
        "billing_server": ["service --status-all", "top", "ps -ef"],
        "order_platform": ["service --status-all", "top", "ps -ef"],
        "subscriber_platform": ["service --status-all", "top", "ps -ef"],
        "sms_gateway": ["service --status-all", "top", "tail -100 application.log"],
        "api_gateway": ["service --status-all", "top", "tail -100 application.log"],
    }.get(node_id, ["service --status-all", "top"])


def verification_commands(node_id: str) -> list[str]:
    return {
        "archive_storage": ["df -kh", "tail -100 application.log", "service --status-all"],
        "oracle_database": ["sqlplus archive-status-check", "tail -100 application.log", "service --status-all"],
    }.get(node_id, ["service --status-all", "top", "tail -100 application.log"])


def _dedupe_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen = set()
    for finding in findings:
        key = (finding["node_id"], finding["summary"])
        if key not in seen:
            seen.add(key)
            deduped.append(finding)
    return deduped


def parse_command_findings(node_id: str, outputs: dict[str, str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    df_output = outputs.get("df -kh", "")
    if "%" in df_output:
        for line in df_output.splitlines():
            if f"/var/{node_id}" in line:
                parts = line.split()
                try:
                    use_percent = float(parts[4].rstrip("%"))
                    if use_percent > 95:
                        findings.append(
                            {
                                "node_id": node_id,
                                "severity": "critical",
                                "summary": "Storage usage is above the critical threshold.",
                                "evidence": [line],
                            }
                        )
                except Exception:
                    pass

    top_output = outputs.get("top", "")
    if "%Cpu(s):" in top_output:
        for line in top_output.splitlines():
            if "%Cpu(s):" in line:
                try:
                    cpu_percent = float(line.split()[1])
                    if cpu_percent > 75:
                        findings.append(
                            {
                                "node_id": node_id,
                                "severity": "warning",
                                "summary": "CPU usage is above the warning threshold.",
                                "evidence": [line],
                            }
                        )
                except Exception:
                    pass

    service_output = outputs.get("service --status-all", "")
    if "[ - ]" in service_output:
        findings.append(
            {
                "node_id": node_id,
                "severity": "warning",
                "summary": "At least one service is not fully healthy.",
                "evidence": service_output.splitlines()[:3],
            }
        )

    log_output = outputs.get("tail -100 application.log", "")
    log_evidence = [line for line in log_output.splitlines() if any(token in line.lower() for token in ["warn", "error", "ora-"])]
    if log_evidence:
        severity = "critical" if any("ora-" in line.lower() or "error" in line.lower() for line in log_evidence) else "warning"
        findings.append(
            {
                "node_id": node_id,
                "severity": severity,
                "summary": "Application log contains operational evidence.",
                "evidence": log_evidence[:5],
            }
        )

    sqlplus_output = outputs.get("sqlplus archive-status-check", "")
    if "DEGRADED" in sqlplus_output or "ORA-" in sqlplus_output:
        findings.append(
            {
                "node_id": node_id,
                "severity": "critical",
                "summary": "Archive status check reports a problem.",
                "evidence": sqlplus_output.splitlines()[:3],
            }
        )

    return _dedupe_findings(findings)


def verification_findings(outputs_by_node: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for node_id, outputs in outputs_by_node.items():
        findings.extend(parse_command_findings(node_id, outputs))
    return findings


def build_rag_query(findings: list[dict[str, Any]]) -> str:
    pieces = []
    for finding in findings[:3]:
        pieces.append(finding["node_id"])
        pieces.extend(finding.get("evidence", [])[:2])
    return " ".join(pieces).strip()
