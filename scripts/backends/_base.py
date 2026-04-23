"""Creators Studio — Provider backend abstraction.

Defines the canonical types and abstract base class every provider backend
must implement. This is the contract layer between skill orchestrators and
concrete providers (Replicate, Kie.ai, HF Inference Providers, Gemini
direct, ElevenLabs, ...).

See docs/superpowers/specs/2026-04-23-provider-abstraction-design.md.

Runtime dependencies: stdlib only (abc, dataclasses, decimal, pathlib,
typing). Never import google-genai, requests, replicate, or any pip package.

Python floor: 3.12+ (v4.2.0). Uses PEP 604 unions, built-in generics,
and dataclass(slots=True).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any


# ─── Canonical dataclasses ──────────────────────────────────────────────


@dataclass(slots=True)
class JobRef:
    """Opaque handle to an in-flight async generation job.

    Backends return this from submit(). Callers treat it as opaque and pass
    it to poll() and parse_result() without introspecting fields.
    """
    provider: str
    external_id: str
    poll_url: str
    raw: dict[str, Any]


@dataclass(slots=True)
class JobStatus:
    """Canonical job state, unified across provider-specific enums.

    Canonical states (5 values):
      pending   — submitted but not yet started (e.g., queued)
      running   — actively generating
      succeeded — finished, output is available
      failed    — finished with an error (including timeouts, content filter)
      canceled  — explicitly canceled by the caller or the platform

    Provider-specific states map to one of these. Example: Replicate's
    6-value enum (starting | processing | succeeded | failed | canceled |
    aborted) maps 'aborted' to 'failed' since both signal terminal failure
    with no output.
    """
    state: str
    output: dict[str, Any] | None
    error: str | None
    raw: dict[str, Any]


@dataclass(slots=True)
class TaskResult:
    """Canonical result returned to orchestrator / caller code.

    output_paths are the downloaded local file paths.
    output_urls are the provider-hosted URLs (may expire).
    metadata holds canonical keys (duration_s, resolution, aspect, seed_used).
    provider_metadata holds the raw provider response for debugging/audit.
    cost may be None if the backend can't compute it cheaply.
    """
    output_paths: list[Path]
    output_urls: list[str]
    metadata: dict[str, Any]
    provider_metadata: dict[str, Any]
    cost: Decimal | None
    task_id: str


@dataclass(slots=True)
class AuthStatus:
    """Result of a provider's auth_check ping."""
    ok: bool
    message: str
    provider: str


# Canonical image param: any of four forms. Backends normalize internally.
# - Path    : local file
# - str     : URL ('http://', 'https://') or data URI ('data:')
# - bytes   : raw image bytes
type CanonicalImage = Path | str | bytes


# ─── Exception hierarchy ─────────────────────────────────────────────────


class ProviderError(Exception):
    """Base class for all provider backend errors."""


class ProviderValidationError(ProviderError):
    """Canonical params failed validation before any HTTP call. No budget burned."""


class ProviderHTTPError(ProviderError):
    """HTTP-level failure (5xx, timeout, malformed response). Retryable in some cases."""


class ProviderAuthError(ProviderError):
    """401/403 — the configured API key is missing, invalid, or lacks permission."""


# ─── Provider backend ABC ────────────────────────────────────────────────


class ProviderBackend(ABC):
    """Contract every provider backend must satisfy.

    Backends are pure data-translation layers with HTTP plumbing. They have
    no global state, no sleeps, no blocking polls. Callers manage the poll
    loop and the download destination.
    """

    # Concrete subclasses override these class-level attributes.
    name: str = ""                          # e.g., "replicate"
    supported_tasks: set[str] = set()       # e.g., {"text-to-image", "image-to-video"}

    @abstractmethod
    def auth_check(self, config: dict[str, Any]) -> AuthStatus:
        """Ping the provider's cheapest read endpoint (e.g., /account) to
        verify the API key works. Must not burn billable generation budget.
        """

    @abstractmethod
    def submit(
        self,
        *,
        task: str,
        model_slug: str,
        canonical_params: dict[str, Any],
        provider_opts: dict[str, Any],
        config: dict[str, Any],
    ) -> JobRef:
        """Translate canonical_params to provider-specific shape, merge
        provider_opts (caller's escape-hatch overrides), POST to the
        provider's submit endpoint, return a JobRef.

        Raises:
            ProviderValidationError — canonical_params fail validation
                BEFORE any HTTP call. No budget burned.
            ProviderAuthError — 401/403 from provider.
            ProviderHTTPError — other HTTP-level failures.
        """

    @abstractmethod
    def poll(self, job_ref: JobRef, config: dict[str, Any]) -> JobStatus:
        """GET the provider's status endpoint. Returns canonical JobStatus.

        Does not block, sleep, or loop. Caller is responsible for polling
        cadence.
        """

    @abstractmethod
    def parse_result(self, job_status: JobStatus, *, download_to: Path) -> TaskResult:
        """When job_status.state == 'succeeded', download output files to
        download_to, compute or look up cost, return canonical TaskResult.

        Raises:
            ProviderError — if called with a non-succeeded job_status.
            ProviderHTTPError — if download fails.
        """
