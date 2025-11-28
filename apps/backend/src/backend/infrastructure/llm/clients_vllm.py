from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError, as_completed
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator

import requests

from backend.domain.benchmarking.ports import (  # preprocessing pipeline
    LLMClient,
    LLMResult,
    PromptSpec,
)
from backend.domain.benchmarking.ports_bench import BenchPromptSpec
from backend.domain.benchmarking.ports_bench import LLMClient as BenchLLMClient
from backend.domain.benchmarking.ports_bench import LLMResult as BenchLLMResult

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class _VllmConfig:
    base_url: str
    model: str
    api_key: str | None
    timeout_s: float
    max_new_tokens_cap: int
    temperature: float


class _BaseVLLMClient:
    """
    OpenAI-compatible HTTP client targeting a vLLM server.

    Efficiency goals:
    - Reuse a single requests.Session for connection pooling (keep-alive)
    - Issue up to `concurrency` requests in-flight using a ThreadPoolExecutor
    to saturate server-side batching and reduce wall time.
    - Use /v1/completions with deterministic decoding (temperature=0.0).
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        concurrency: int = 8,
        timeout_s: float = 120.0,
        max_new_tokens_cap: int = 256,
        temperature: float = 0.0,
    ) -> None:
        # Normalize base_url as the server root (without trailing slash and without /v1)
        base_url = base_url.rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]
        self.cfg = _VllmConfig(
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout_s=timeout_s,
            max_new_tokens_cap=max_new_tokens_cap,
            temperature=temperature,
        )
        self.concurrency = max(1, concurrency)

        # Use thread-local sessions to avoid cross-thread contention.
        # Requests sessions are not guaranteed thread-safe.
        self._tls: threading.local = threading.local()

    def _get_session(self) -> requests.Session:
        sess = getattr(self._tls, "session", None)
        if sess is None:
            sess = requests.Session()
            # Increase pool size relative to expected concurrency per thread
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=16, pool_maxsize=16
            )
            sess.mount("http://", adapter)
            sess.mount("https://", adapter)
            self._tls.session = sess
        return sess

    # --- HTTP helpers -----------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.cfg.api_key:
            h["Authorization"] = f"Bearer {self.cfg.api_key}"
        return h

    def _post_completion(
        self, prompt: str, max_new_tokens: int
    ) -> tuple[str, int, dict]:
        """Call /v1/completions and return (text, gen_time_ms, usage_dict)."""
        url = f"{self.cfg.base_url}/v1/completions"
        payload: Dict[str, Any] = {
            "model": self.cfg.model,
            "prompt": prompt,
            "max_tokens": min(max_new_tokens, self.cfg.max_new_tokens_cap),
            "temperature": self.cfg.temperature,
        }
        t0 = time.perf_counter()
        try:
            sess = self._get_session()
            resp = sess.post(
                url, json=payload, headers=self._headers(), timeout=self.cfg.timeout_s
            )
            dt = int((time.perf_counter() - t0) * 1000)
            if resp.status_code != 200:
                # If the completions endpoint isn't available, try chat fallback
                if resp.status_code in (404, 405):
                    return self._post_chat_completion(prompt, max_new_tokens)
                return (f"[error http {resp.status_code}] {resp.text[:300]}", dt, {})
            data = resp.json()
            # Extract usage information if available
            usage = data.get("usage", {})
            # OpenAI completions format: choices[0].text
            choices = data.get("choices") or []
            if not choices:
                # No choices; try chat fallback
                return self._post_chat_completion(prompt, max_new_tokens)
            first = choices[0] or {}
            text = first.get("text")
            if not text:
                # Some servers return chat-like objects even on /completions
                msg = first.get("message") or {}
                text = msg.get("content", "")
            if not text:
                # Last resort: chat fallback
                return self._post_chat_completion(prompt, max_new_tokens)
            return (text, dt, usage)
        except requests.RequestException as e:
            dt = int((time.perf_counter() - t0) * 1000)
            return (f"[error request] {e}", dt, {})

    def _post_chat_completion(
        self, prompt: str, max_new_tokens: int
    ) -> tuple[str, int, dict]:
        """Call /v1/chat/completions and return (text, gen_time_ms, usage_dict)."""
        url = f"{self.cfg.base_url}/v1/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.cfg.model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "max_tokens": min(max_new_tokens, self.cfg.max_new_tokens_cap),
            "temperature": self.cfg.temperature,
        }
        t0 = time.perf_counter()
        try:
            sess = self._get_session()
            resp = sess.post(
                url, json=payload, headers=self._headers(), timeout=self.cfg.timeout_s
            )
            dt = int((time.perf_counter() - t0) * 1000)
            if resp.status_code != 200:
                return (f"[error http {resp.status_code}] {resp.text[:300]}", dt, {})
            data = resp.json()
            # Extract usage information if available
            usage = data.get("usage", {})
            choices = data.get("choices") or []
            if not choices:
                return ("", dt, usage)
            first = choices[0] or {}
            msg = first.get("message") or {}
            content = msg.get("content")
            # Some servers may still return 'text'
            if not content:
                content = first.get("text", "")
            return (content or "", dt, usage)
        except requests.RequestException as e:
            dt = int((time.perf_counter() - t0) * 1000)
            return (f"[error request] {e}", dt, {})

    # --- concurrency driver ----------------------------------------------
    def _run_stream_generic(self, specs: Iterable, result_ctor) -> Iterator:
        pending: Dict[Future, Any] = {}
        start_times: Dict[Future, float] = {}

        def submit(executor: ThreadPoolExecutor, spec) -> None:
            fut = executor.submit(
                self._post_completion, spec.prompt_text, spec.max_new_tokens
            )
            pending[fut] = spec
            start_times[fut] = time.time()

        with ThreadPoolExecutor(max_workers=self.concurrency) as ex:
            # fill pipeline up to concurrency then drain as we go
            it = iter(specs)
            # Prime initial window
            try:
                for _ in range(self.concurrency):
                    s = next(it)
                    submit(ex, s)
            except StopIteration:
                pass

            last_log_time = 0.0

            while pending:
                # Check for stuck requests
                now = time.time()
                if start_times:
                    oldest = min(start_times.values())
                    duration = now - oldest
                    if duration > 60.0 and (now - last_log_time > 30.0):
                        _LOG.warning(
                            f"[LLM Client] Pipeline stalled? Oldest request pending for {duration:.1f}s. Pending: {len(pending)}"
                        )
                        last_log_time = now

                try:
                    # Use timeout to keep the loop alive and logging even if vLLM hangs
                    # Wait up to 5 seconds for a result
                    for fut in as_completed(list(pending.keys()), timeout=5.0):
                        spec = pending.pop(fut)
                        start_times.pop(fut, None)
                        text, dt, usage = fut.result()
                        yield result_ctor(
                            spec=spec,
                            raw_text=text,
                            gen_time_ms=dt,
                            prompt_tokens=usage.get("prompt_tokens"),
                            completion_tokens=usage.get("completion_tokens"),
                            total_tokens=usage.get("total_tokens"),
                        )

                        # Try to keep the window full by submitting the next task
                        try:
                            t_next = time.time()
                            s = next(it)
                            if time.time() - t_next > 1.0:
                                _LOG.info(
                                    f"[LLM Client] Fetching next item took {time.time() - t_next:.2f}s"
                                )
                            submit(ex, s)
                        except StopIteration:
                            # Exhausted input; continue draining
                            pass
                        except Exception as e:
                            _LOG.error(
                                f"[LLM Client] Error fetching next item from generator: {e}"
                            )
                            # Stop submitting but continue draining pending

                        # Break to re-enter as_completed with a fresh snapshot of keys
                        break
                except TimeoutError:
                    # No request finished in 5s - loop continues to check timeouts/logging
                    continue
                except Exception as e:
                    _LOG.error(f"[LLM Client] Unexpected error in loop: {e}")
                    if not pending:
                        break


# --- Attr-Gen vLLM client ----------------------------------------------------
class LlmClientVLLM(_BaseVLLMClient, LLMClient):
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        batch_size: int = 8,
        timeout_s: float = 120.0,
        max_new_tokens_cap: int = 256,
        temperature: float = 0.0,
    ) -> None:
        super().__init__(
            base_url=base_url,
            model=model,
            api_key=api_key,
            concurrency=batch_size,
            timeout_s=timeout_s,
            max_new_tokens_cap=max_new_tokens_cap,
            temperature=temperature,
        )

    def run_stream(self, specs: Iterable[PromptSpec]) -> Iterable[LLMResult]:
        yield from self._run_stream_generic(specs, LLMResult)


# --- Benchmark vLLM client ---------------------------------------------------
class LlmClientVLLMBench(_BaseVLLMClient, BenchLLMClient):
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        batch_size: int = 8,
        timeout_s: float = 120.0,
        max_new_tokens_cap: int = 256,
        temperature: float = 0.0,
    ) -> None:
        super().__init__(
            base_url=base_url,
            model=model,
            api_key=api_key,
            concurrency=batch_size,
            timeout_s=timeout_s,
            max_new_tokens_cap=max_new_tokens_cap,
            temperature=temperature,
        )

    def run_stream(self, specs: Iterable[BenchPromptSpec]) -> Iterable[BenchLLMResult]:
        yield from self._run_stream_generic(specs, BenchLLMResult)
