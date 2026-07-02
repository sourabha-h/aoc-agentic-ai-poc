from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch
import unittest

from backend import agent_workflow
from backend.agent_workflow import main as agent_main, run_workflow
from backend.agents import discovery_agent as discovery_agent_module
from backend.generator import generate_network
from backend.mock_shell import execute_command


class AgentWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workdir = Path(tempfile.mkdtemp(prefix="agent-workflow-"))
        self.original_cwd = Path.cwd()
        os.chdir(self.workdir)
        self.addCleanup(os.chdir, self.original_cwd)
        self.addCleanup(lambda: shutil.rmtree(self.workdir, ignore_errors=True))

    def test_healthy_network_reports_no_findings(self) -> None:
        generate_network("healthy_network")
        payload = run_workflow()

        self.assertIsInstance(payload["scan_id"], str)
        self.assertEqual(payload["initial_findings"], [])
        self.assertEqual(payload["active_findings"], [])
        self.assertIn("health_check_guidance", payload["rag_results"])
        self.assertEqual(payload["rag_results"]["resolution_guidance"], {})
        health_sections = {
            result["section"]
            for node_results in payload["rag_results"]["health_check_guidance"].values()
            for result in node_results
        }
        self.assertIn("reporting_agent", [item["agent"] for item in payload["agent_timeline"]])
        self.assertNotIn("planning_agent", [item["agent"] for item in payload["agent_timeline"]])
        self.assertIn("health_check_guidance", [item.get("purpose") for item in payload["agent_timeline"] if item["agent"] == "discovery_agent"])
        self.assertIn("findings", [item.get("purpose") for item in payload["agent_timeline"] if item["agent"] == "discovery_agent"])
        self.assertTrue(health_sections <= {"symptoms", "health_checks"})

    def test_llm_settings_prefers_azure_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT": "https://example.azure.openai",
                "AZURE_OPENAI_API_KEY": "azure-key",
                "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o-mini",
                "AZURE_OPENAI_API_VERSION": "2024-02-15-preview",
                "OPENAI_API_KEY": "openai-key",
                "OPENAI_MODEL": "gpt-4o",
                "OPENAI_BASE_URL": "https://api.openai.com/v1",
            },
            clear=False,
        ):
            settings = agent_workflow._llm_settings()

        self.assertEqual(settings["provider"], "azure")
        self.assertEqual(settings["base_url"], "https://example.azure.openai")
        self.assertEqual(settings["model"], "gpt-4o-mini")

    def test_llm_audit_entries_are_recorded(self) -> None:
        generate_network("healthy_network")
        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT": "",
                "AZURE_OPENAI_API_KEY": "",
                "AZURE_OPENAI_DEPLOYMENT_NAME": "",
                "AZURE_OPENAI_API_VERSION": "",
                "OPENAI_API_KEY": "",
                "OPENAI_MODEL": "",
                "OPENAI_BASE_URL": "",
            },
            clear=False,
        ):
            payload = run_workflow()

        llm_events = [item for item in payload["agent_timeline"] if item.get("agent") == "llm"]
        self.assertGreater(len(llm_events), 0)
        self.assertTrue(all(item.get("event_type") == "LLM_CALL" for item in llm_events))
        self.assertTrue(all("purpose" in item and "request_purpose" in item and "source" in item and "status" in item and "model" in item for item in llm_events))
        self.assertTrue(all("error_type" in item and "error_message" in item and "parameter_names" in item for item in llm_events))

    def test_mock_shell_reports_current_state(self) -> None:
        generate_network("archive_storage_cleanup_retry_success")

        df_output = execute_command("archive_storage", "df -kh")
        sql_output = execute_command("oracle_database", "sqlplus archive-status-check")

        self.assertIn("Use%", df_output)
        self.assertIn("97", df_output)
        self.assertIn("ORA-", sql_output)

    def test_retry_flow_uses_remediation_loop(self) -> None:
        generate_network("archive_storage_cleanup_retry_success")
        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT": "",
                "AZURE_OPENAI_API_KEY": "",
                "AZURE_OPENAI_DEPLOYMENT_NAME": "",
                "AZURE_OPENAI_API_VERSION": "",
            },
            clear=False,
        ):
            payload = run_workflow(auto_approve=True)

        timeline = payload["agent_timeline"]
        self.assertTrue(any(item.get("purpose") == "plan" for item in timeline))
        self.assertTrue(any(item.get("purpose") == "guardrail_result" for item in timeline))
        self.assertTrue(any(item.get("purpose") == "approval_status" for item in timeline))
        self.assertTrue(any(item.get("purpose") == "execution_result" for item in timeline))
        self.assertTrue(any(item.get("purpose") == "verification_result" for item in timeline))
        self.assertGreater(len(payload["initial_findings"]), 0)
        self.assertEqual(payload["active_findings"], [])
        self.assertEqual(payload["approval_status"], "approved")
        self.assertEqual(payload["verification_status"], "healthy")
        self.assertEqual(payload["remediation_attempts"], 2)
        self.assertTrue(payload["final_report"])
        self.assertIn("health_check_guidance", payload["rag_results"])
        self.assertIn("resolution_guidance", payload["rag_results"])
        resolution_sections = {item["section"] for item in payload["rag_results"]["resolution_guidance"].get("results", [])}
        self.assertTrue(resolution_sections <= {"recommended_actions", "risk_level", "verification_steps"})

    def test_approval_waiting_without_flag(self) -> None:
        generate_network("archive_storage_cleanup_retry_success")
        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT": "",
                "AZURE_OPENAI_API_KEY": "",
                "AZURE_OPENAI_DEPLOYMENT_NAME": "",
                "AZURE_OPENAI_API_VERSION": "",
            },
            clear=False,
        ):
            payload = run_workflow(auto_approve=False)

        self.assertEqual(payload["approval_status"], "WAITING_FOR_APPROVAL")
        self.assertEqual(payload["final_report"]["summary"], "Waiting for approval.")

    def test_guardrail_rejection_routes_to_reporting(self) -> None:
        generate_network("guardrail_rejection")
        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT": "",
                "AZURE_OPENAI_API_KEY": "",
                "AZURE_OPENAI_DEPLOYMENT_NAME": "",
                "AZURE_OPENAI_API_VERSION": "",
            },
            clear=False,
        ):
            payload = run_workflow(auto_approve=True)

        self.assertEqual(payload["approval_status"], "rejected")
        self.assertEqual(payload["final_report"]["summary"], "Guardrail rejected the proposed remediation.")

    def test_cli_outputs_json(self) -> None:
        generate_network("healthy_network")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = agent_main(["run", "--auto-approve"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertIn("agent_timeline", payload)

    def test_invalid_json_command_selection_uses_fallback_commands(self) -> None:
        generate_network("healthy_network")

        original_llm_generate = discovery_agent_module.llm_generate

        def fake_llm_generate(*args, **kwargs):
            return "llm", "{not-json", {"model": "test-model"}, True, "", ""

        discovery_agent_module.llm_generate = fake_llm_generate
        self.addCleanup(setattr, discovery_agent_module, "llm_generate", original_llm_generate)

        payload = run_workflow()
        llm_events = [
            item
            for item in payload["agent_timeline"]
            if item.get("agent") == "llm" and item.get("purpose") == "command_selection"
        ]
        self.assertTrue(llm_events)
        self.assertTrue(any(item.get("error_type") == "invalid_json_response" for item in llm_events))
        self.assertTrue(payload["inspected_nodes"]["archive_storage"]["selected_commands"])

    def test_bad_request_error_logs_safe_message(self) -> None:
        from backend import llm_client
        from unittest.mock import MagicMock, patch

        class FakeBadRequestError(Exception):
            pass

        FakeBadRequestError.__name__ = "BadRequestError"

        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = FakeBadRequestError("invalid request body")

        with patch("openai.OpenAI", return_value=fake_client), patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT": "https://example.azure.openai",
                "AZURE_OPENAI_API_KEY": "azure-key",
                "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o-mini",
                "AZURE_OPENAI_API_VERSION": "2024-02-15-preview",
            },
            clear=False,
        ):
            source, content, settings, success, error_type, error_message = llm_client.llm_generate("system", "user")

        self.assertEqual(source, "llm")
        self.assertFalse(success)
        self.assertEqual(error_type, "api_call_failed")
        self.assertEqual(error_message, "invalid request body")
        audit = llm_client.llm_audit_event("reporting", settings, source, success, error_type, error_message)
        self.assertEqual(audit["request_purpose"], "reporting")
        self.assertIn("api_key", audit["parameter_names"])


if __name__ == "__main__":
    unittest.main()
