Social Bias Benchmark — Developer Guide

Overview
- End-to-end pipeline to generate personas, build datasets, enrich attributes, run a Likert benchmark, and analyze results.
- Local development now centers on Docker + the Web UI with hot reload.
- vLLM is the recommended LLM serving backend; HF is supported for legacy usage.

Quick Start (Docker + UI)
- Requirements: Docker and Docker Compose (v2).
- Start stack with hot reload for API and UI:
  - `docker compose up`
- Open UI: http://localhost:5173
- API base URL: http://localhost:8765 (the UI uses this via `VITE_API_BASE_URL`).
- Data persists under `./data/benchmark.db` (bind-mounted into the container). No manual DB init needed.

Common tasks in the UI
- Datasets: create/browse datasets (pool, balanced, counterfactuals, reality).
- Attribute generation: trigger attr-gen per dataset and track progress.
- Benchmark runs: start Likert runs per dataset and per model.
- Results/compare: inspect metrics and compare runs.

Hot Reload behavior
- API: `uvicorn --reload` watches `apps/api/src`, `apps/shared/src`, `apps/analysis/src`, `apps/benchmark/src`, `apps/persona_generator/src`.
- UI: Vite dev server with HMR on save.
- Source is bind-mounted; changes are applied instantly without rebuilding containers.

Dependency changes
- Python (API): after editing `apps/api/requirements.txt`, rebuild API only:
  - `docker compose build api && docker compose up -d`
- Node (UI): `npm ci` runs on container start. After changing `apps/ui/package.json`, restart the UI:
  - `docker compose restart ui`

LLM backend (vLLM)
- Start a vLLM server separately (example):
  - `python -m vllm.entrypoints.openai.api_server --model "Qwen/Qwen2.5-1.5B-Instruct" --host 0.0.0.0 --port 8000`
- The API uses env vars to reach vLLM (configure in your shell or via `docker compose` overrides):
  - `VLLM_BASE_URL` (e.g., `http://localhost:8000`)
  - `VLLM_API_KEY` (optional)

Configuration
- Database:
  - Default is SQLite at `data/benchmark.db` (created automatically).
  - Override with `DB_URL` (e.g., `postgres://user:pass@host/db`).
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

Advanced: CLI (optional)
- All functionality is also accessible via Python CLIs for batch/automation. The UI is recommended for interactive workflows.
- Database initialization (only needed for CLI-only usage):
  - `PYTHONPATH=apps python apps/shared/src/shared/storage/migrate.py`
- Dataset building, attr-gen, benchmark and analysis CLIs are under `apps/benchmark/src/benchmark/cli` and `apps/analysis/src/analysis`.
- Examples (dataset-based runs):
  - Attr-gen: `PYTHONPATH=apps python apps/benchmark/src/benchmark/cli/run_attr_generation.py --dataset-id <ID> --llm vllm --vllm-model "..." --vllm-base-url http://localhost:8000`
  - Benchmark: `PYTHONPATH=apps python apps/benchmark/src/benchmark/cli/run_core_benchmark.py --dataset-id <ID> --llm vllm --vllm-model "..." --vllm-base-url http://localhost:8000`

Notes
- Reproducibility: datasets store seed/config; balanced/reality reference their pool `gen_id`.
- Performance: prefer dataset-scoped attr-gen/benchmark. Keep batch sizes modest on small GPUs.
