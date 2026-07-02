# Autonomous Operation Center - Agentic AI POC

One-line summary: A mocked Autonomous Operation Center demonstrating agentic AI workflows for telecom OSS/BSS scenarios.

## Problem Statement
Real-world telecom operations require coordinated discovery, triage, remediation, and verification across many systems; building and testing autonomous agents safely is difficult and risky on production infrastructure.

## Solution Overview
This repository provides a Proof-of-Concept that simulates network nodes, runbooks, and agent workflows to demonstrate Agentic AI behavior, coordination, and decision-making without any real infrastructure access.

## Architecture Flow
- Mock network and node state are stored under `mock_network/` and `nodes/`.
- The backend agents live in `backend/` and coordinate via the `agent_workflow` and agent modules.
- RAG and vector-store artifacts are simulated in `vector_store/` (local SQLite snapshot for demos).
- The frontend (in `frontend/`) visualizes audit trails, topology, and timelines.

## Agent Roles
- `discovery_agent`: Inspects topology and collects observations.
- `inspection_agent` / `verification_agent`: Runs checks and verifies remediation.
- `execution_agent`: Performs (mocked) remediation steps.
- `supervisor_agent`: Oversees workflows and escalates when needed.
- `approval_agent`: Handles human-in-the-loop approvals (simulated).
- `reporting_agent`: Generates reports and audit trails.
- `guardrail_agent`: Enforces safety policies and constraints.

## LangGraph Concepts Demonstrated
- Multi-agent orchestration and message passing.
- RAG-style retrieval of runbooks and remediation steps.
- Agent workflows for discovery, planning, execution, verification, and escalation.

## Key Features
- Mocked infrastructure and safe simulated remediation.
- Pluggable backend agents under `backend/agents/`.
- RAG ingestion and retrieval utilities for runbooks (`backend/rag_ingest.py`, `backend/rag_retriever.py`).
- Frontend dashboard for visualization and playback of agent decisions.

## Tech Stack
- Python 3.x for backend agents and simulation.
- Frontend: Vite + React (sources in `frontend/`).
- Local vector store (Chroma SQLite) for demo retrievals.

## How to run
Prerequisites: Python 3.10+, Node 18+ (or compatible). Create a virtual environment and install backend dependencies if provided.

Backend (example):

1. Create and activate venv (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt  # if present
```

2. Copy `.env.example` to `.env` and update placeholders (do NOT add real secrets):

```powershell
copy .env.example .env
```

3. Start the backend simulator (example entrypoint):

```powershell
python -m backend.simulator
```

Frontend (example):

```bash
cd frontend
npm install
npm run dev
```

Note: Exact commands may vary depending on your local environment and whether a `requirements.txt` or a framework-specific start script exists.

## Demo notes
All infrastructure, remediation actions, and integrations in this repo are mocked or simulated for safety. This project is intended to showcase Agentic AI behavior, workflows, and orchestration patterns—not to operate real systems.

---
