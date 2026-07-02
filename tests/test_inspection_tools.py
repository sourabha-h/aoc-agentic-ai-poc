from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
from pathlib import Path
import unittest

from backend.generator import generate_network
from backend.inspection_tools import get_topology, inspect_all_nodes, inspect_node, main as inspection_main


class InspectionToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.workdir = Path(self.temp_dir.name)
        self.original_cwd = Path.cwd()
        os.chdir(self.workdir)
        self.addCleanup(os.chdir, self.original_cwd)

    def _generate(self, scenario_id: str) -> None:
        generate_network(scenario_id)

    def test_healthy_network_scan(self) -> None:
        self._generate("healthy_network")

        topology = get_topology()
        self.assertIn("dependencies", topology)

        network = inspect_all_nodes()
        self.assertEqual(len(network["nodes"]), 7)
        statuses = {node["observations"]["status"] for node in network["nodes"]}
        self.assertEqual(statuses, {"healthy"})

    def test_critical_archive_storage_scan(self) -> None:
        self._generate("archive_storage_cleanup_retry_success")

        node = inspect_node("archive_storage")
        self.assertGreater(node["observations"]["disk_percent"], 95)
        self.assertIn(node["observations"]["status"], {"critical", "degraded"})

    def test_oracle_archive_error_evidence(self) -> None:
        self._generate("archive_storage_cleanup_retry_success")

        node = inspect_node("oracle_database")
        log_text = "\n".join(node["application_log"])
        self.assertIn("ORA-19809", log_text)

    def test_multiple_parallel_issues(self) -> None:
        self._generate("multiple_parallel_issues")

        network = inspect_all_nodes()
        status_by_node = {node["node_id"]: node["observations"]["status"] for node in network["nodes"]}
        self.assertEqual(status_by_node["archive_storage"], "degraded")
        self.assertEqual(status_by_node["sms_gateway"], "degraded")
        self.assertEqual(status_by_node["api_gateway"], "degraded")

    def test_no_access_to_simulator_control(self) -> None:
        self._generate("healthy_network")
        shutil.rmtree(self.workdir / "simulator_control")

        node = inspect_node("billing_server")
        self.assertEqual(node["node_id"], "billing_server")

    def test_cli_outputs_json(self) -> None:
        self._generate("healthy_network")

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = inspection_main(["scan-node", "--node", "archive_storage"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["node_id"], "archive_storage")

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = inspection_main(["scan-all"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(len(payload["nodes"]), 7)


if __name__ == "__main__":
    unittest.main()
