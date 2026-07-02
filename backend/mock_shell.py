"""Mock shell command execution for discovery."""

from __future__ import annotations

from pathlib import Path


OUTPUT_DIR = Path("mock_network")


def _read_json(path: Path) -> dict:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _node_dir(node_id: str) -> Path:
    return OUTPUT_DIR / "nodes" / node_id


def _log_lines(node_id: str) -> list[str]:
    return _read_text(_node_dir(node_id) / "application.log").splitlines()


def _tail_log(node_id: str, limit: int = 100) -> str:
    lines = _log_lines(node_id)[-limit:]
    return "\n".join(lines)


def execute_command(node_id: str, command: str) -> str:
    config = _read_json(_node_dir(node_id) / "configuration.json")
    observations = _read_json(_node_dir(node_id) / "observations.json")
    lines = _log_lines(node_id)
    service_status = observations.get("service_status", "unknown")
    cpu = float(observations.get("cpu_percent", 0))
    memory = float(observations.get("memory_percent", 0))
    disk = float(observations.get("disk_percent", 0))
    latency = int(observations.get("latency_ms", 0))

    if command == "df -kh":
        return (
            "Filesystem      Size  Used Avail Use% Mounted on\n"
            f"/dev/{node_id:<10} 100G  {disk:>4.1f}G  {max(0.0, 100.0 - disk):>4.1f}G  {disk:>3.0f}% /var/{node_id}"
        )

    if command == "top":
        return (
            f"top - {config['display_name']}\n"
            f"%Cpu(s): {cpu:>4.1f} us, {max(0.0, 100.0 - cpu):>4.1f} id\n"
            f"MiB Mem : {memory:>4.1f} used\n"
            f"load average: {max(0.1, latency / 100):.2f}, 0.10, 0.05"
        )

    if command == "ps -ef":
        process_map = {
            "billing_server": ["brm_billingd", "billing-worker"],
            "oracle_database": ["ora_pmon", "ora_lgwr", "ora_smon"],
            "archive_storage": ["archiverd", "backup-sync"],
            "order_platform": ["order-api", "workflow-engine"],
            "subscriber_platform": ["subscriber-sync", "cache-watcher"],
            "sms_gateway": ["sms-relay", "delivery-worker"],
            "api_gateway": ["api-router", "edge-proxy"],
        }
        state_flag = "running" if service_status == "running" else "degraded"
        rows = [f"mock     1001  1  0 08:00 ?        00:00:01 /usr/bin/{name}" for name in process_map.get(node_id, ["service"])]
        rows.append(f"mock     1009  1  0 08:00 ?        00:00:00 node status={state_flag}")
        return "\n".join(rows)

    if command == "tail -100 application.log":
        return "\n".join(lines[-100:])

    if command == "service --status-all":
        service_names = {
            "billing_server": ["billing-service"],
            "oracle_database": ["oracle-db", "archive-writer"],
            "archive_storage": ["archive-cleanup", "backup-store"],
            "order_platform": ["order-service"],
            "subscriber_platform": ["subscriber-sync"],
            "sms_gateway": ["sms-delivery"],
            "api_gateway": ["api-routing"],
        }
        prefix = "[ + ]" if service_status == "running" else "[ - ]"
        return "\n".join(f"{prefix} {name}" for name in service_names.get(node_id, ["service"]))

    if command == "sqlplus archive-status-check":
        joined_logs = "\n".join(lines).lower()
        if "ora-19809" in joined_logs or disk >= 95:
            return "ORA-19809: limit exceeded for recovery files\nArchive status: DEGRADED"
        if "ora-00257" in joined_logs:
            return "ORA-00257: archiver error. Connect internal only, until freed.\nArchive status: DEGRADED"
        return "Archive status: OK\nNo archive errors detected."

    return f"Command not supported: {command}"
