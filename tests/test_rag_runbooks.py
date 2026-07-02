from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
from pathlib import Path
import unittest

from backend.rag_ingest import VECTOR_STORE_DIR, ingest_runbooks
from backend.rag_retriever import main as rag_main, search_runbooks


class RAGRunbookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workdir = Path(tempfile.mkdtemp(prefix="rag-tests-"))
        self.original_cwd = Path.cwd()
        os.chdir(self.workdir)
        self.addCleanup(os.chdir, self.original_cwd)

    def test_ingestion_creates_vector_store(self) -> None:
        payload = ingest_runbooks()
        self.assertTrue(VECTOR_STORE_DIR.exists())
        self.assertGreater(payload["chunks"], 0)
        reused = ingest_runbooks()
        self.assertTrue(reused["reused"])

    def test_archive_query_returns_archive_runbook(self) -> None:
        ingest_runbooks()
        payload = search_runbooks("archive storage disk usage capacity threshold cleanup health check", top_k=8)
        self.assertGreaterEqual(len(payload["results"]), 1)
        sources = {item["source_file"] for item in payload["results"]}
        self.assertIn("archive_storage_issue.md", sources)

    def test_cpu_query_returns_high_cpu_runbook(self) -> None:
        ingest_runbooks()
        payload = search_runbooks("cpu 95 percent high load", top_k=3)
        sources = {item["source_file"] for item in payload["results"]}
        self.assertIn("high_cpu.md", sources)

    def test_oracle_database_query_returns_oracle_archive_error(self) -> None:
        ingest_runbooks()
        payload = search_runbooks("Oracle database archive destination health check ORA-19809 archive writer status", top_k=8)
        sources = {item["source_file"] for item in payload["results"]}
        self.assertIn("oracle_archive_error.md", sources)

    def test_api_gateway_query_returns_routing_timeout(self) -> None:
        ingest_runbooks()
        payload = search_runbooks("API gateway routing timeout latency health check", top_k=8)
        sources = {item["source_file"] for item in payload["results"]}
        self.assertIn("routing_timeout.md", sources)

    def test_empty_query_is_safe(self) -> None:
        ingest_runbooks()
        payload = search_runbooks("", top_k=3)
        self.assertEqual(payload["status"], "empty_query")
        self.assertEqual(payload["results"], [])

    def test_cli_outputs_json(self) -> None:
        ingest_runbooks()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = rag_main(["--query", "archive storage 97 percent ORA-00257"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertIn("results", payload)


if __name__ == "__main__":
    unittest.main()
