from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
import threading
import time
import unittest

from fastapi.testclient import TestClient

from backend.generator import generate_network
from backend.network_templates import NODES


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.workdir = Path(self.temp_dir.name)
        self.original_cwd = Path.cwd()
        os.chdir(self.workdir)
        self.addCleanup(os.chdir, self.original_cwd)
        generate_network("archive_storage_cleanup_retry_success")
        from backend import api

        api._WORKFLOW_STATE = {
            "workflow_status": "ready",
            "scan_id": None,
            "result": None,
        }

    def test_status_is_idle_before_first_scan(self) -> None:
        from backend import api

        api._LATEST_WORKFLOW_RESULT = None
        client = TestClient(api.app)

        response = client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "idle")
        self.assertEqual(payload["workflow_status"], "ready")
        self.assertEqual(len(payload["topology"]["nodes"]), 7)
        self.assertTrue(all(node["status"] == "not_scanned" for node in payload["topology"]["nodes"]))
        self.assertEqual(payload["active_findings"], [])
        self.assertEqual(payload["verification_status"], "idle")
        self.assertEqual(payload["approval_status"], "idle")
        self.assertEqual(payload["final_report"], {})
        self.assertEqual(payload["final_status"], "")
        self.assertEqual(payload["consolidated_issues"], [])
        self.assertEqual(payload["agent_timeline"], [])

    def test_post_scan_sets_running_then_completes(self) -> None:
        from backend import api

        start_event = threading.Event()
        finish_event = threading.Event()
        original_run_workflow = api.run_workflow

        def fake_run_workflow(auto_approve: bool = False) -> dict:
            start_event.set()
            finish_event.wait(timeout=2)
            return {
                "scan_id": "scan_test",
                "topology": {
                    "nodes": [
                        {
                            "node_id": node["node_id"],
                            "display_name": node["display_name"],
                            "dependencies": list(node.get("dependencies", [])),
                            "status": "healthy",
                            "current_activity": "Monitoring",
                        }
                        for node in NODES
                    ],
                    "dependencies": [
                        {"from": node["node_id"], "to": dependency}
                        for node in NODES
                        for dependency in node.get("dependencies", [])
                    ],
                },
                "inspected_nodes": {
                    node["node_id"]: {
                        "node_id": node["node_id"],
                        "display_name": node["display_name"],
                        "selected_commands": [],
                        "command_outputs": {},
                    }
                    for node in NODES
                },
                "initial_findings": [],
                "active_findings": [],
                "rag_results": {},
                "remediation_plan": {},
                "approval_status": "approved",
                "verification_status": "healthy",
                "remediation_attempts": 0,
                "final_report": {"status": "healthy"},
                "agent_timeline": [],
            }

        api.run_workflow = fake_run_workflow
        self.addCleanup(setattr, api, "run_workflow", original_run_workflow)

        client = TestClient(api.app)
        response = client.post("/api/scan", json={"auto_approve": True})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow_status"], "running")
        self.assertEqual(payload["topology"]["nodes"][0]["status"], "scanning")

        self.assertTrue(start_event.wait(timeout=2))

        status = client.get("/api/status")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["workflow_status"], "running")
        self.assertEqual(status.json()["topology"]["nodes"][0]["status"], "scanning")

        finish_event.set()
        for _ in range(20):
            status = client.get("/api/status")
            if status.json()["workflow_status"] == "completed":
                break
            time.sleep(0.1)
        self.assertEqual(status.json()["workflow_status"], "completed")
        self.assertEqual(status.json()["topology"]["nodes"][0]["status"], "healthy")

    def test_completed_status_persists_after_completion(self) -> None:
        from backend import api

        completed_result = {
            "scan_id": "scan_persist",
            "topology": {
                "nodes": [
                    {
                        "node_id": node["node_id"],
                        "display_name": node["display_name"],
                        "dependencies": list(node.get("dependencies", [])),
                        "status": "healthy",
                        "current_activity": "Monitoring",
                    }
                    for node in NODES
                ],
                "dependencies": [
                    {"from": node["node_id"], "to": dependency}
                    for node in NODES
                    for dependency in node.get("dependencies", [])
                ],
            },
            "inspected_nodes": {
                node["node_id"]: {
                    "node_id": node["node_id"],
                    "display_name": node["display_name"],
                    "selected_commands": [],
                    "command_outputs": {},
                    "rag_guidance": {"health_check_guidance": [], "resolution_guidance": []},
                    "evidence_findings": [],
                }
                for node in NODES
            },
            "initial_findings": [],
            "active_findings": [],
            "rag_results": {},
            "remediation_plan": {},
            "approval_status": "approved",
            "verification_status": "healthy",
            "remediation_attempts": 0,
            "final_report": {"status": "healthy"},
            "agent_timeline": [],
        }
        api._WORKFLOW_STATE = {
            "workflow_status": "completed",
            "scan_id": "scan_persist",
            "result": completed_result,
        }

        client = TestClient(api.app)
        first = client.get("/api/status")
        second = client.get("/api/status")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["workflow_status"], "completed")
        self.assertEqual(second.json()["workflow_status"], "completed")
        self.assertEqual(first.json()["scan_id"], "scan_persist")
        self.assertEqual(second.json()["scan_id"], "scan_persist")
        self.assertEqual(first.json()["final_status"], "Verified Healthy")

    def test_audit_events_expose_rag_query_details(self) -> None:
        from backend import api

        completed_result = {
            "scan_id": "scan_audit",
            "topology": {
                "nodes": [
                    {
                        "node_id": node["node_id"],
                        "display_name": node["display_name"],
                        "dependencies": list(node.get("dependencies", [])),
                        "status": "healthy",
                        "current_activity": "Health check completed",
                    }
                    for node in NODES
                ],
                "dependencies": [
                    {"from": node["node_id"], "to": dependency}
                    for node in NODES
                    for dependency in node.get("dependencies", [])
                ],
            },
            "inspected_nodes": {},
            "initial_findings": [],
            "active_findings": [],
            "rag_results": {},
            "remediation_plan": {},
            "approval_status": "approved",
            "verification_status": "healthy",
            "remediation_attempts": 0,
            "final_report": {"status": "healthy"},
            "agent_timeline": [
                {
                    "agent": "discovery_agent",
                    "purpose": "health_check_guidance",
                    "node_id": "archive_storage",
                    "query": "Archive Storage health-check guidance thresholds",
                    "rag_results": [
                        {
                            "source_file": "archive_storage_issue.md",
                            "section": "health_checks",
                            "score": 0.91,
                            "content": "Check archive storage usage and cleanup status.",
                        }
                    ],
                    "timestamp": "2026-06-01T08:10:00+00:00",
                },
                {
                    "agent": "discovery_agent",
                    "command_selection": {"source": "fallback", "commands": ["df -kh"]},
                    "command_outputs": {"df -kh": "Use% 97%"},
                    "timestamp": "2026-06-01T08:11:00+00:00",
                },
            ],
        }
        api._WORKFLOW_STATE = {
            "workflow_status": "completed",
            "scan_id": "scan_audit",
            "result": completed_result,
        }

        client = TestClient(api.app)
        payload = client.get("/api/status").json()

        self.assertIn("audit_events", payload)
        self.assertGreater(len(payload["audit_events"]), 0)
        rag_event = next(event for event in payload["audit_events"] if event["event_type"] == "RAG_QUERY")
        self.assertEqual(rag_event["vector_store"], "ChromaDB")
        self.assertEqual(rag_event["source_file"], "archive_storage_issue.md")
        self.assertEqual(rag_event["section"], "health_checks")
        self.assertEqual(rag_event["score"], 0.91)
        self.assertIn("retrieved_content", rag_event)

    def test_scan_waits_for_approval_then_resumes(self) -> None:
        from backend import api

        original_run_workflow = api.run_workflow

        def fake_run_workflow(auto_approve: bool = False) -> dict:
            status = "approved" if auto_approve else "WAITING_FOR_APPROVAL"
            topology_status = "healthy" if auto_approve else "warning"
            return {
                "scan_id": "scan_approval",
                "topology": {
                    "nodes": [
                        {
                            "node_id": node["node_id"],
                            "display_name": node["display_name"],
                            "dependencies": list(node.get("dependencies", [])),
                            "status": topology_status,
                            "current_activity": "Monitoring" if auto_approve else "Waiting for approval",
                        }
                        for node in NODES
                    ],
                    "dependencies": [
                        {"from": node["node_id"], "to": dependency}
                        for node in NODES
                        for dependency in node.get("dependencies", [])
                    ],
                },
                "inspected_nodes": {
                    node["node_id"]: {
                        "node_id": node["node_id"],
                        "display_name": node["display_name"],
                        "selected_commands": [],
                        "command_outputs": {},
                        "rag_guidance": {"health_check_guidance": [], "resolution_guidance": []},
                        "evidence_findings": [],
                    }
                    for node in NODES
                },
                "initial_findings": [
                    {
                        "node_id": "archive_storage",
                        "severity": "critical",
                        "summary": "Archive storage pressure requires cleanup.",
                        "evidence": ["disk usage is above threshold"],
                    }
                ],
                "active_findings": [
                    {
                        "node_id": "archive_storage",
                        "severity": "critical",
                        "summary": "Archive storage pressure requires cleanup.",
                        "evidence": ["disk usage is above threshold"],
                    }
                ],
                "rag_results": {},
                "remediation_plan": {},
                "approval_status": status,
                "verification_status": "healthy" if auto_approve else "waiting",
                "remediation_attempts": 0,
                "final_report": {"status": "healthy"} if auto_approve else {},
                "agent_timeline": [],
            }

        api.run_workflow = fake_run_workflow
        self.addCleanup(setattr, api, "run_workflow", original_run_workflow)

        client = TestClient(api.app)
        start = client.post("/api/scan", json={"auto_approve": False})
        self.assertEqual(start.status_code, 200)
        self.assertEqual(start.json()["workflow_status"], "running")

        for _ in range(20):
            status = client.get("/api/status")
            if status.json()["workflow_status"] == "waiting_approval":
                break
            time.sleep(0.05)
        self.assertEqual(status.json()["workflow_status"], "waiting_approval")
        self.assertEqual(status.json()["approval_status"], "WAITING_FOR_APPROVAL")
        self.assertEqual(len(status.json()["consolidated_issues"]), 1)
        self.assertEqual(status.json()["consolidated_issues"][0]["issue_id"], "archive_storage_cleanup")

        approve = client.post("/api/approve")
        self.assertEqual(approve.status_code, 200)

        for _ in range(20):
            status = client.get("/api/status")
            if status.json()["workflow_status"] == "completed":
                break
            time.sleep(0.05)
        self.assertEqual(status.json()["workflow_status"], "completed")
        self.assertEqual(status.json()["approval_status"], "approved")
        self.assertEqual(status.json()["verification_status"], "healthy")
        self.assertEqual(status.json()["final_status"], "Verified Healthy")

    def test_cors_allows_vite_origin(self) -> None:
        from backend.api import app

        client = TestClient(app)
        response = client.get("/api/status", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://localhost:5173")

    def test_reset_demo_returns_to_idle_state(self) -> None:
        from backend import api

        api._WORKFLOW_STATE = {
            "workflow_status": "completed",
            "scan_id": "scan_reset",
            "result": {
                "scan_id": "scan_reset",
                "topology": {"nodes": [], "dependencies": []},
                "inspected_nodes": {},
                "initial_findings": [{"node_id": "archive_storage"}],
                "active_findings": [{"node_id": "archive_storage"}],
                "rag_results": {},
                "remediation_plan": {},
                "approval_status": "approved",
                "verification_status": "healthy",
                "remediation_attempts": 0,
                "final_report": {"status": "healthy"},
                "agent_timeline": [],
            },
        }

        client = TestClient(api.app)
        response = client.post("/api/reset")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow_status"], "ready")
        self.assertEqual(payload["status"], "idle")
        self.assertEqual(payload["scan_id"], None)
        self.assertEqual(payload["topology"]["nodes"][0]["status"], "not_scanned")
        self.assertEqual(payload["active_findings"], [])
        self.assertEqual(payload["approval_status"], "idle")
        self.assertEqual(payload["verification_status"], "idle")
        self.assertEqual(payload["final_report"], {})
        self.assertEqual(payload["agent_timeline"], [])

    def test_scan_preserves_existing_retry_scenario_before_approval(self) -> None:
        from backend import api

        original_run_workflow = api.run_workflow

        def fake_run_workflow(auto_approve: bool = False) -> dict:
            return {
                "scan_id": "scan_retry",
                "topology": {
                    "nodes": [
                        {
                            "node_id": node["node_id"],
                            "display_name": node["display_name"],
                            "dependencies": list(node.get("dependencies", [])),
                            "status": "warning",
                            "current_activity": "Waiting for approval",
                        }
                        for node in NODES
                    ],
                    "dependencies": [
                        {"from": node["node_id"], "to": dependency}
                        for node in NODES
                        for dependency in node.get("dependencies", [])
                    ],
                },
                "inspected_nodes": {},
                "initial_findings": [],
                "active_findings": [],
                "rag_results": {},
                "remediation_plan": {},
                "approval_status": "WAITING_FOR_APPROVAL",
                "verification_status": "waiting",
                "remediation_attempts": 0,
                "final_report": {},
                "agent_timeline": [],
            }

        api.run_workflow = fake_run_workflow
        self.addCleanup(setattr, api, "run_workflow", original_run_workflow)

        from backend.generator import generate_network

        generate_network("archive_storage_cleanup_retry_success")
        client = TestClient(api.app)

        before_scan = json.loads(
            (self.workdir / "mock_network" / "nodes" / "archive_storage" / "observations.json").read_text(encoding="utf-8")
        )
        self.assertEqual(before_scan["status"], "critical")
        self.assertGreater(before_scan["disk_percent"], 95)

        response = client.post("/api/scan", json={"auto_approve": False})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["workflow_status"], "running")

        after_scan = json.loads(
            (self.workdir / "mock_network" / "nodes" / "archive_storage" / "observations.json").read_text(encoding="utf-8")
        )
        self.assertEqual(after_scan["status"], "critical")
        self.assertGreater(after_scan["disk_percent"], 95)


if __name__ == "__main__":
    unittest.main()
