"""Unit tests for vLLM HTTP Client - kritisch für GPU-Runs."""

import sys
from pathlib import Path

# Ensure backend package is importable
REPO_ROOT = Path(__file__).resolve().parents[5]
SRC_ROOT = REPO_ROOT / "apps" / "backend" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import json
import time
from concurrent.futures import TimeoutError as FuturesTimeoutError
from unittest.mock import MagicMock, Mock, patch

import pytest

from backend.domain.benchmarking.ports import PromptSpec
from backend.domain.benchmarking.ports_bench import BenchPromptSpec, BenchWorkItem
from backend.infrastructure.llm.clients_vllm import LlmClientVLLM, LlmClientVLLMBench


class TestVLLMClientInitialization:
    """Test client initialization and configuration."""

    def test_base_url_normalization(self):
        """Base URL should be normalized correctly."""
        client = LlmClientVLLM(base_url="http://localhost:8000/v1", model="test-model")
        assert client.cfg.base_url == "http://localhost:8000"
        assert not client.cfg.base_url.endswith("/v1")

    def test_trailing_slash_removed(self):
        """Trailing slashes should be removed from base URL."""
        client = LlmClientVLLM(base_url="http://localhost:8000/", model="test-model")
        assert client.cfg.base_url == "http://localhost:8000"

    def test_default_values(self):
        """Client should use sensible defaults."""
        client = LlmClientVLLM(base_url="http://localhost:8000", model="test-model")
        assert client.concurrency >= 1
        assert client.cfg.timeout_s > 0
        assert client.cfg.temperature == 0.0  # Deterministic
        assert client.cfg.max_new_tokens_cap > 0


class TestVLLMClientErrorHandling:
    """Test error handling for various failure scenarios."""

    def test_http_error_response(self):
        """Client should handle non-200 HTTP responses gracefully."""
        client = LlmClientVLLM(base_url="http://localhost:8000", model="test-model")

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch.object(client, "_get_session") as mock_session:
            session = Mock()
            session.post.return_value = mock_response
            mock_session.return_value = session

            text, gen_time = client._post_completion("test prompt", 128)

            assert "[error http 500]" in text
            assert gen_time >= 0

    def test_connection_error(self):
        """Client should handle connection errors gracefully."""
        client = LlmClientVLLM(base_url="http://localhost:8000", model="test-model")

        with patch.object(client, "_get_session") as mock_session:
            session = Mock()
            import requests

            session.post.side_effect = requests.ConnectionError("Connection refused")
            mock_session.return_value = session

            text, gen_time = client._post_completion("test prompt", 128)

            # Should catch and convert to error message
            assert "[error request]" in text
            assert "Connection refused" in text
            assert gen_time >= 0

    def test_timeout_error(self):
        """Client should handle timeout errors."""
        client = LlmClientVLLM(
            base_url="http://localhost:8000", model="test-model", timeout_s=0.1
        )

        with patch.object(client, "_get_session") as mock_session:
            session = Mock()
            # Simulate timeout by sleeping longer than timeout_s
            import requests

            session.post.side_effect = requests.Timeout("Request timeout")
            mock_session.return_value = session

            text, gen_time = client._post_completion("test prompt", 128)

            assert "[error request]" in text
            assert gen_time >= 0


class TestVLLMClientResponseParsing:
    """Test response parsing for different formats."""

    def test_completions_response_parsing(self):
        """Client should parse standard completions response."""
        client = LlmClientVLLM(base_url="http://localhost:8000", model="test-model")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"text": "This is the generated text"}]
        }

        with patch.object(client, "_get_session") as mock_session:
            session = Mock()
            session.post.return_value = mock_response
            mock_session.return_value = session

            text, gen_time = client._post_completion("test prompt", 128)

            assert text == "This is the generated text"
            assert gen_time >= 0

    def test_chat_format_fallback(self):
        """Client should fallback to chat format if text is empty."""
        client = LlmClientVLLM(base_url="http://localhost:8000", model="test-model")

        # First call returns empty text, triggers chat fallback
        completions_response = Mock()
        completions_response.status_code = 200
        completions_response.json.return_value = {
            "choices": [{"text": ""}]  # Empty text triggers fallback
        }

        chat_response = Mock()
        chat_response.status_code = 200
        chat_response.json.return_value = {
            "choices": [{"message": {"content": "Chat response text"}}]
        }

        with patch.object(client, "_get_session") as mock_session:
            session = Mock()
            session.post.side_effect = [completions_response, chat_response]
            mock_session.return_value = session

            text, gen_time = client._post_completion("test prompt", 128)

            assert text == "Chat response text"

    def test_empty_choices_fallback(self):
        """Client should handle empty choices array."""
        client = LlmClientVLLM(base_url="http://localhost:8000", model="test-model")

        completions_response = Mock()
        completions_response.status_code = 200
        completions_response.json.return_value = {"choices": []}

        chat_response = Mock()
        chat_response.status_code = 200
        chat_response.json.return_value = {
            "choices": [{"message": {"content": "Fallback text"}}]
        }

        with patch.object(client, "_get_session") as mock_session:
            session = Mock()
            session.post.side_effect = [completions_response, chat_response]
            mock_session.return_value = session

            text, gen_time = client._post_completion("test prompt", 128)

            assert text == "Fallback text"


class TestVLLMClientConcurrency:
    """Test concurrent request handling."""

    def test_concurrent_requests_complete(self):
        """Multiple concurrent requests should all complete."""
        client = LlmClientVLLMBench(
            base_url="http://localhost:8000",
            model="test-model",
            batch_size=4,  # LlmClientVLLMBench uses batch_size, not concurrency
        )

        # Create sample specs
        specs = []
        for i in range(10):
            work = BenchWorkItem(
                dataset_id=1,
                persona_uuid=f"uuid-{i}",
                persona_context={"name": f"Person {i}"},
                case_id=f"case-{i}",
                adjective="friendly",
                case_template="Test",
                scale_reversed=False,
            )
            spec = BenchPromptSpec(
                work=work,
                prompt_text=f"Prompt {i}",
                max_new_tokens=128,
                attempt=1,
                model_name="test-model",
                template_version="v1",
                benchmark_run_id=1,
            )
            specs.append(spec)

        # Mock successful responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"text": '{"rating": 3, "rationale": "ok"}'}]
        }

        with patch.object(client, "_get_session") as mock_session:
            session = Mock()
            session.post.return_value = mock_response
            mock_session.return_value = session

            results = list(client.run_stream(iter(specs)))

            assert len(results) == 10
            for res in results:
                assert res.raw_text == '{"rating": 3, "rationale": "ok"}'
                assert res.gen_time_ms >= 0

    def test_session_reuse(self):
        """Client should reuse sessions for efficiency."""
        client = LlmClientVLLM(base_url="http://localhost:8000", model="test-model")

        # Call _get_session multiple times
        session1 = client._get_session()
        session2 = client._get_session()

        # Should be the same instance (thread-local caching)
        assert session1 is session2


class TestVLLMClientMaxTokensCap:
    """Test max_new_tokens capping behavior."""

    def test_max_tokens_capped(self):
        """max_new_tokens should be capped at configured limit."""
        client = LlmClientVLLM(
            base_url="http://localhost:8000", model="test-model", max_new_tokens_cap=100
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"text": "response"}]}

        with patch.object(client, "_get_session") as mock_session:
            session = Mock()
            session.post.return_value = mock_response
            mock_session.return_value = session

            # Request 500 tokens, should be capped at 100
            client._post_completion("test", max_new_tokens=500)

            # Check the payload sent
            call_args = session.post.call_args
            payload = call_args[1]["json"]
            assert payload["max_tokens"] == 100  # Capped

    def test_max_tokens_under_cap(self):
        """max_new_tokens under cap should be respected."""
        client = LlmClientVLLM(
            base_url="http://localhost:8000", model="test-model", max_new_tokens_cap=100
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"text": "response"}]}

        with patch.object(client, "_get_session") as mock_session:
            session = Mock()
            session.post.return_value = mock_response
            mock_session.return_value = session

            # Request 50 tokens, under cap
            client._post_completion("test", max_new_tokens=50)

            call_args = session.post.call_args
            payload = call_args[1]["json"]
            assert payload["max_tokens"] == 50  # Not capped
