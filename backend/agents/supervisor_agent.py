from __future__ import annotations

import uuid
from typing import Any

from ..agent_state import AgentState, append_timeline


def run(state: AgentState) -> dict[str, Any]:
    scan_id = state.get("scan_id") or f"scan_{uuid.uuid4().hex[:8]}"
    return {
        "scan_id": scan_id,
        "agent_timeline": append_timeline(state, "supervisor_start", f"Started scan {scan_id}"),
    }
