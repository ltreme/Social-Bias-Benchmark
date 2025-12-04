Social Bias Benchmark — Developer Guide

Overview
- End-to-end pipeline to generate personas, build datasets, enrich attributes, run a Likert benchmark, and analyze results.
- Local development now centers on Docker + the Web UI with hot reload.
- vLLM is the recommended LLM serving backend; HF is supported for legacy usage.
- Backend code is structured as a layered `backend` package (`apps/backend/src/backend`) with the sub-packages:
  - `backend.application`: FastAPI routers, DTOs and future CLI entry points.
  - `backend.domain`: persona generation, attr-gen/benchmark pipelines, analytics.
  - `backend.infrastructure`: database models, repositories, LLM adapters, translators, notifications.

Quick Start (Docker + UI)
- Requirements: Docker and Docker Compose
- Start the stack with hot reload for API and UI:
  - `docker-compose up` (or `docker compose up`)
- Open UI: http://localhost:5173
- API base URL: http://localhost:8765 (the UI uses this via `VITE_API_BASE_URL`).
- Data persists in PostgreSQL (Docker volume `pg_data`).

Common tasks in the UI
- Datasets: create/browse datasets (pool, balanced, counterfactuals, reality).
- Attribute generation: trigger attr-gen per dataset and track progress.
- Benchmark runs: start Likert runs per dataset and per model.
- Results/compare: inspect metrics and compare runs.

Hot Reload behavior
- API: `uvicorn --reload` watches `apps/backend/src` (application, domain, infrastructure).
- UI: Vite dev server with HMR on save.
- Source is bind-mounted; changes are applied instantly without rebuilding containers.

Dependency changes
- Python (API): after editing `apps/backend/requirements.txt`, rebuild API only:
  - `docker compose build api && docker compose up -d`
- Node (UI): `npm ci` runs on container start. After changing `apps/ui/package.json`, restart the UI:
  - `docker compose restart ui`

LLM backend (vLLM – required for AttrGen & Benchmark)
- Attribute generation and benchmark runs require a running vLLM server (local or remote).
- Local start (see quickstart): https://docs.vllm.ai/en/stable/getting_started/quickstart.html
  - Example:
    - `python -m vllm.entrypoints.openai.api_server --model "Qwen/Qwen2.5-1.5B-Instruct" --host 0.0.0.0 --port 8000`
- Remote via SSH tunnel (forwards remote port 8000 to local 8000):
  - `ssh -N -L 8000:127.0.0.1:8000 user@remote-host`
  - While the SSH session is active, vLLM is reachable at `http://localhost:8000` locally.
- Docker Compose defaults:
  - The API uses `VLLM_BASE_URL=http://host.docker.internal:8000` (see `docker-compose.yml`).
  - If vLLM runs locally (or via SSH tunnel) on port 8000, AttrGen/Benchmark work out-of-the-box.
  - If you use a different host/port, adjust `VLLM_BASE_URL` in `docker-compose.yml` or via a compose override.
  - Optional: set `VLLM_API_KEY` if your server requires one.

Configuration
- Database:
  - The provided docker-compose uses PostgreSQL by default (see `DB_URL` in `docker-compose.yml`).
  - To use SQLite inside the API container, set `DB_URL=sqlite:////app/data/benchmark.db` (the path will be created automatically).
- UI → API:
  - `VITE_API_BASE_URL` is set to `http://localhost:8765` in `docker-compose.yml`.

Useful Docker commands
- Start in foreground: `docker compose up`
- Start in background: `docker compose up -d`
- Stop: `docker compose down`
- Rebuild API image: `docker compose build api`
- Tail logs: `docker compose logs -f api ui`

Troubleshooting
- Import/Module errors right after `docker compose up` typically indicate missing Python deps — rebuild the API image.
- Port already in use: stop conflicting local servers or change published ports in `docker-compose.yml`.
- Node modules mismatch: the UI container keeps its own `node_modules` volume.
- **Slow API responses**:
  - First request after restart is slower due to module imports (~300ms) — this is normal
  - On macOS: Docker volume mounts can be slow. The `:cached` flag is already set for better performance
  - Connection pool is set to 20 connections (reduced from 80) to avoid overhead
  - For production use (no hot reload needed), remove `--reload` flag from uvicorn command for 10x faster startup
  - Python bytecode caching is enabled (`PYTHONDONTWRITEBYTECODE=0`) and stored in a Docker volume for faster imports

Advanced: CLI (optional)
- All functionality is also accessible via Python CLIs for batch/automation. The UI is recommended for interactive workflows.
- Database initialization (only needed for CLI-only usage):
  - `PYTHONPATH=apps/backend/src python apps/backend/src/backend/infrastructure/storage/migrate.py`
- Dataset building, attr-gen, benchmark and analysis CLIs live under `apps/backend/src/backend/application/cli` and `apps/backend/src/backend/domain/analytics`.
- Examples (dataset-based runs):
  - Attr-gen: `PYTHONPATH=apps/backend/src python apps/backend/src/backend/application/cli/run_attr_generation.py --dataset-id <ID> --llm vllm --vllm-model "..." --vllm-base-url http://localhost:8000`
  - Benchmark: `PYTHONPATH=apps/backend/src python apps/backend/src/backend/application/cli/run_core_benchmark.py --dataset-id <ID> --llm vllm --vllm-model "..." --vllm-base-url http://localhost:8000`

Tests
- Docker-basierte Tests (empfohlen):
  - Vor GPU-Runs: `./scripts/run_tests.sh critical`
  - Alle Tests: `./scripts/run_tests.sh all`
  - Unit-Tests: `./scripts/run_tests.sh unit`
  - Integration-Tests: `./scripts/run_tests.sh integration`
  - Mit Coverage: `./scripts/run_tests.sh cov`
  - Shell für Debugging: `./scripts/run_tests.sh shell`
- Vollständige Teststrategie & Planung: siehe `TESTING_STRATEGY.md`

Notes
- Reproducibility: datasets store seed/config; balanced/reality reference their pool `gen_id`.
- Performance: prefer dataset-scoped attr-gen/benchmark. Keep batch sizes modest on small GPUs.
