"""vLLM connection utilities for model serving."""

from __future__ import annotations

import os
from typing import Any, Dict
from urllib.parse import urlparse, urlunparse

import requests


def normalize_base_url(url: str | None) -> str:
    """Normalize a vLLM base URL for Docker container access.

    When running in a container, localhost/127.0.0.1 are replaced with
    host.docker.internal to access the host machine.

    Args:
        url: Base URL to normalize, or None to use env var VLLM_BASE_URL

    Returns:
        Normalized base URL
    """
    base = (url or os.getenv("VLLM_BASE_URL") or "http://localhost:8000").strip()
    try:
        parsed = urlparse(base)
        host = (parsed.hostname or "").lower()
        if host in {"localhost", "127.0.0.1"}:
            # Inside a container, talk to the host via host.docker.internal
            # Keep port/protocol as provided
            parsed = parsed._replace(netloc=f"host.docker.internal:{parsed.port or 80}")
            return urlunparse(parsed)
    except Exception:
        pass
    return base


def probe_vllm_models(base_url: str, timeout: float = 2.5) -> Dict[str, Any]:
    """Probe vLLM server to verify availability and list models.

    Calls the /v1/models endpoint to check if the server is running.

    Args:
        base_url: vLLM server base URL
        timeout: Request timeout in seconds

    Returns:
        JSON response from /v1/models endpoint

    Raises:
        requests.RequestException: If the server is unreachable or returns an error
        ValueError: If the response is not valid JSON
    """
    url = base_url.rstrip("/") + "/v1/models"
    response = requests.get(
        url, timeout=timeout, headers={"accept": "application/json"}
    )
    response.raise_for_status()
    try:
        return response.json()
    except Exception as e:
        raise ValueError(f"Ungültige vLLM-Antwort von {url}: {e}")


def select_vllm_base_for_model(
    model_name: str, preferred_base_url: str | None = None
) -> str:
    """Find a working vLLM base URL that serves the requested model.

    Tries multiple candidate URLs in order:
    1. preferred_base_url (as provided)
    2. normalized(preferred_base_url)
    3. VLLM_BASE_URL env var
    4. normalized(VLLM_BASE_URL)
    5. http://host.docker.internal:8000
    6. http://localhost:8000

    For each candidate, probes the /v1/models endpoint. If models are listed,
    checks if the requested model is available. Otherwise accepts the URL if
    it responds successfully.

    Args:
        model_name: Name of the model to find
        preferred_base_url: Optional preferred base URL to try first

    Returns:
        Working base URL that serves the model

    Raises:
        RuntimeError: If no working URL is found
    """
    tried: list[tuple[str, str]] = []
    candidates = []

    # Build candidate list
    if preferred_base_url:
        candidates.append(preferred_base_url)
        candidates.append(normalize_base_url(preferred_base_url))

    env_base = os.getenv("VLLM_BASE_URL")
    if env_base:
        candidates.append(env_base)
        candidates.append(normalize_base_url(env_base))

    candidates.append("http://host.docker.internal:8000")
    candidates.append("http://localhost:8000")

    # Try each candidate, avoiding duplicates
    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)

        try:
            data = probe_vllm_models(candidate)
            # If models are listed, verify the requested model exists
            model_ids = [
                str(m.get("id"))
                for m in (data.get("data") or [])
                if isinstance(m, dict)
            ]
            if not model_ids or model_name in model_ids:
                return candidate
            tried.append((candidate, f"Modell '{model_name}' nicht gelistet"))
        except Exception as e:
            tried.append((candidate, str(e)))

    # Nothing worked
    detail = "; ".join([f"{u}: {err}" for u, err in tried]) or "keine Kandidaten"
    raise RuntimeError(f"vLLM nicht erreichbar oder Modell fehlt – versucht: {detail}")
