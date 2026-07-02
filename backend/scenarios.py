"""Small scenario catalog for the mock network generator."""

from __future__ import annotations


SCENARIOS = {
    "healthy_network": {
        "scenario_id": "healthy_network",
        "description": "Healthy baseline network.",
        "attempts": 0,
        "retry_flow": False,
        "final_status": "healthy",
    },
    "archive_storage_cleanup_success": {
        "scenario_id": "archive_storage_cleanup_success",
        "description": "Archive storage cleanup succeeds immediately.",
        "attempts": 1,
        "retry_flow": False,
        "final_status": "healthy",
    },
    "archive_storage_cleanup_fail": {
        "scenario_id": "archive_storage_cleanup_fail",
        "description": "Archive storage cleanup fails.",
        "attempts": 1,
        "retry_flow": False,
        "final_status": "degraded",
    },
    "archive_storage_cleanup_retry_success": {
        "scenario_id": "archive_storage_cleanup_retry_success",
        "description": "Archive storage cleanup succeeds after one failed attempt.",
        "attempts": 2,
        "retry_flow": True,
        "final_status": "healthy",
    },
    "archive_storage_cleanup_escalation": {
        "scenario_id": "archive_storage_cleanup_escalation",
        "description": "Archive storage cleanup escalates.",
        "attempts": 2,
        "retry_flow": False,
        "final_status": "critical",
    },
    "partial_recovery_dependency_issue": {
        "scenario_id": "partial_recovery_dependency_issue",
        "description": "Partial recovery with dependency lag.",
        "attempts": 2,
        "retry_flow": False,
        "final_status": "partial_recovery",
    },
    "multiple_parallel_issues": {
        "scenario_id": "multiple_parallel_issues",
        "description": "Multiple independent issues are present at once.",
        "attempts": 1,
        "retry_flow": False,
        "final_status": "degraded",
    },
    "guardrail_rejection": {
        "scenario_id": "guardrail_rejection",
        "description": "Unsafe action is rejected by a guardrail.",
        "attempts": 0,
        "retry_flow": False,
        "final_status": "rejected",
    },
}


def get_scenario(scenario_id: str) -> dict:
    try:
        return dict(SCENARIOS[scenario_id])
    except KeyError as exc:
        available = ", ".join(sorted(SCENARIOS))
        raise ValueError(f"Unknown scenario '{scenario_id}'. Available: {available}") from exc

