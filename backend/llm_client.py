"""Local LLM client helpers with dotenv and Azure OpenAI support."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def llm_settings() -> dict[str, str]:
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "").strip()
    azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "").strip()
    return {
        "provider": "azure",
        "api_key": azure_api_key,
        "model": azure_deployment,
        "base_url": azure_endpoint,
        "api_version": azure_api_version,
    }


def llm_audit_event(
    purpose: str,
    settings: dict[str, str],
    source: str,
    success: bool,
    error_type: str = "",
    error_message: str = "",
    parameter_names: list[str] | None = None,
) -> dict[str, Any]:
    from .agent_state import now

    if parameter_names is None:
        parameter_names = ["api_key", "azure_endpoint", "api_version", "model", "messages", "temperature"]

    return {
        "event_type": "LLM_CALL",
        "agent": "llm",
        "purpose": purpose,
        "request_purpose": purpose,
        "model": settings.get("model", ""),
        "source": source,
        "status": "success" if success else "failure",
        "error_type": error_type,
        "error_message": error_message,
        "parameter_names": parameter_names,
        "timestamp": now(),
    }


def llm_generate(
    system_prompt: str,
    user_prompt: str,
    *,
    response_format: dict[str, Any] | None = None,
    temperature: float = 0.2,
) -> tuple[str, str, dict[str, str], bool, str, str]:
    settings = llm_settings()
    if not settings["api_key"] or not settings["model"] or not settings["base_url"]:
        return (
            "fallback",
            "LLM unavailable. Using deterministic fallback output.",
            settings,
            False,
            "missing_environment_variable",
            "Missing Azure OpenAI environment variables.",
        )

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=settings["api_key"],
            base_url=settings["base_url"],
        )

        response = client.chat.completions.create(
            model=settings["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            response_format=response_format,
        )
        content = response.choices[0].message.content or ""
        stripped = content.strip()
        if not stripped:
            return (
                "llm",
                "LLM unavailable. Using deterministic fallback output.",
                settings,
                False,
                "empty_response",
                "Azure OpenAI returned an empty response.",
            )
        return "llm", stripped, settings, True, "", ""
    except Exception as exc:
        error_type = "api_call_failed"
        error_message = str(exc)
        return (
            "llm",
            "LLM unavailable. Using deterministic fallback output.",
            settings,
            False,
            error_type,
            error_message,
        )
