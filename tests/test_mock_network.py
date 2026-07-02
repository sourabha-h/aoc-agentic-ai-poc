from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
from pathlib import Path
import unittest

from backend.generator import DEFAULT_OUTPUT_DIR, RUNTIME_STATE_FILE, SCENARIO_FILE, generate_network, main as generator_main
from backend.simulator import main as simulator_main


class MockNetworkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.workdir = Path(self.temp_dir.name)
        self.original_cwd = Path.cwd()
        os.chdir(self.workdir)
        self.addCleanup(os.chdir, self.original_cwd)

    def _generate(self, scenario_id: str) -> Path:
        output_dir = self.workdir / "mock_network"
        summary = generate_network(scenario_id)
        self.assertEqual(summary["scenario_id"], scenario_id)
        return output_dir

    def test_simplified_structure(self) -> None:
        output_dir = self._generate("healthy_network")

        self.assertTrue((output_dir / "topology.json").exists())
        self.assertTrue((output_dir / "nodes").is_dir())
        self.assertFalse((output_dir / "health_policies").exists())
        self.assertFalse((output_dir / "summary.json").exists())

        expected_nodes = {
            "billing_server",
            "oracle_database",
            "archive_storage",
            "order_platform",
            "subscriber_platform",
            "sms_gateway",
            "api_gateway",
        }

        actual_nodes = {path.name for path in (output_dir / "nodes").iterdir() if path.is_dir()}
        self.assertEqual(actual_nodes, expected_nodes)

        for node_id in expected_nodes:
            node_dir = output_dir / "nodes" / node_id
            self.assertTrue((node_dir / "configuration.json").exists())
            self.assertTrue((node_dir / "observations.json").exists())
            self.assertTrue((node_dir / "healthy_node_policy.json").exists())
            self.assertTrue((node_dir / "application.log").exists())

    def test_topology_direction(self) -> None:
        output_dir = self._generate("healthy_network")
        topology = json.loads((output_dir / "topology.json").read_text(encoding="utf-8"))
        edges = {(edge["from"], edge["to"]) for edge in topology["dependencies"]}
        self.assertIn(("oracle_database", "archive_storage"), edges)
        self.assertIn(("api_gateway", "order_platform"), edges)

    def test_retry_scenario_initial_state_is_observable_only(self) -> None:
        output_dir = self._generate("archive_storage_cleanup_retry_success")
        archive_obs = json.loads((output_dir / "nodes" / "archive_storage" / "observations.json").read_text(encoding="utf-8"))
        archive_log = (output_dir / "nodes" / "archive_storage" / "application.log").read_text(encoding="utf-8")
        oracle_log = (output_dir / "nodes" / "oracle_database" / "application.log").read_text(encoding="utf-8")

        self.assertGreater(archive_obs["disk_percent"], 95)
        self.assertIn(archive_obs["status"], {"critical", "degraded"})
        self.assertIn("ORA-19809", oracle_log)
        self.assertNotIn("success", archive_log.lower())
        self.assertNotIn("retry", archive_log.lower())

    def test_retry_flow_two_attempts(self) -> None:
        self._generate("archive_storage_cleanup_retry_success")

        first = simulator_main(["apply-remediation", "--action", "cleanup_archive_storage"])
        self.assertEqual(first, 0)
        state_after_first = json.loads(RUNTIME_STATE_FILE.read_text(encoding="utf-8"))
        self.assertEqual(state_after_first["remediation_attempts"], 1)
        self.assertEqual(state_after_first["stage"], "remediation_attempt_1")

        archive_obs_first = json.loads((DEFAULT_OUTPUT_DIR / "nodes" / "archive_storage" / "observations.json").read_text(encoding="utf-8"))
        archive_log_first = (DEFAULT_OUTPUT_DIR / "nodes" / "archive_storage" / "application.log").read_text(encoding="utf-8")
        self.assertGreater(archive_obs_first["disk_percent"], 95)
        self.assertIn("cleanup incomplete", archive_log_first.lower())
        self.assertNotIn("success", archive_log_first.lower())

        second = simulator_main(["apply-remediation", "--action", "cleanup_archive_storage"])
        self.assertEqual(second, 0)
        state_after_second = json.loads(RUNTIME_STATE_FILE.read_text(encoding="utf-8"))
        self.assertEqual(state_after_second["remediation_attempts"], 2)
        self.assertEqual(state_after_second["stage"], "remediation_attempt_2")

        archive_obs_second = json.loads((DEFAULT_OUTPUT_DIR / "nodes" / "archive_storage" / "observations.json").read_text(encoding="utf-8"))
        archive_log_second = (DEFAULT_OUTPUT_DIR / "nodes" / "archive_storage" / "application.log").read_text(encoding="utf-8")
        self.assertLess(archive_obs_second["disk_percent"], 95)
        self.assertIn("cleanup completed", archive_log_second.lower())
        self.assertIn("storage usage returned to normal", archive_log_second.lower())

    def test_cli_commands_work(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = generator_main(["--scenario", "healthy_network"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["scenario_id"], "healthy_network")

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = simulator_main(["status"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertIn(payload["status"], {"idle", "active"})

    def test_private_control_files_exist_outside_public_tree(self) -> None:
        self._generate("healthy_network")
        self.assertTrue(SCENARIO_FILE.exists())
        self.assertTrue(RUNTIME_STATE_FILE.exists())
        self.assertTrue(SCENARIO_FILE.parent.name == "simulator_control")
        self.assertFalse((DEFAULT_OUTPUT_DIR / "scenario.json").exists())
        self.assertFalse((DEFAULT_OUTPUT_DIR / "runtime_state.json").exists())


if __name__ == "__main__":
    unittest.main()

