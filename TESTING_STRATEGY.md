# Testing Strategy für Social Bias Benchmark

## Überblick

Dieses Dokument beschreibt eine umfassende Teststrategie für den Social Bias Benchmark, um sicherzustellen, dass teure GPU-Server-Runs fehlerfrei ablaufen.

## Kritische Komponenten (nach Risiko sortiert)

### 🔴 KRITISCH - Hohe Priorität

#### 1. **LLM-Integration & Prompt-Generierung**
- **Komponenten:**
  - `LlmClientVLLMBench`, `LlmClientVLLM` (vLLM HTTP-Client)
  - `LikertPromptFactory`, `AttributePromptFactory`
  - Prompt-Template-Generierung mit Persona-Context
  
- **Risiken:**
  - Falsche Prompts führen zu invaliden Antworten
  - Timeout bei langsamen Modellen
  - Connection-Pooling-Probleme bei hoher Concurrency
  - Scale-Reversal (in-order vs. reversed) inkorrekt implementiert
  - Rationale-Leakage (rationale erscheint wenn sie nicht sollte)
  
- **Test-Coverage:**
  - ✅ Unit: Prompt-Generierung für verschiedene Persona-Typen
  - ✅ Unit: Scale-Reversal-Logik (random50, in, rev modes)
  - ✅ Unit: Dual-Direction-Logic (dual_fraction)
  - ✅ Integration: Mock-vLLM-Server mit verschiedenen Response-Formaten
  - ✅ Integration: Timeout-Handling
  - ✅ Integration: Concurrent Request Handling

#### 2. **Output-Parsing & Validierung**
- **Komponenten:**
  - `LikertPostProcessor`, `AttributePostProcessor`
  - `AbstractPostProcessor` (JSON-Parsing, Sanitization)
  
- **Risiken:**
  - Modelle produzieren ungültiges JSON
  - Rating außerhalb 1-5 Range
  - Fehlende Required-Keys (name, appearance, biography)
  - Unerwartete Rationale bei `include_rationale=False`
  - Retry-Logic schlägt endlos fehl
  
- **Test-Coverage:**
  - ✅ Unit: Gültige JSON-Responses parsen
  - ✅ Unit: Ungültige Formate (Markdown, Prosa, broken JSON)
  - ✅ Unit: Edge-Cases (Rating=0, Rating=6, Float-Ratings, String-Ratings)
  - ✅ Unit: Llama-Sanitization (<think>-Tags, doppelte Backticks)
  - ✅ Unit: Retry vs. Fail Decision-Logic
  - ✅ Unit: Rationale-Leak-Detection

#### 3. **Benchmark-Pipeline Orchestration**
- **Komponenten:**
  - `run_benchmark_pipeline()` in `benchmark.py`
  - `run_attr_gen_pipeline()` in `attr_gen.py`
  - Work-Item-Generierung (Persona × Cases Cross-Join)
  - Completion-Tracking & Resume-Logic
  
- **Risiken:**
  - Duplicate Work-Items bei Resume
  - Falsche Persona-Count-Estimation
  - Memory-Overflow bei großen Datasets
  - Cancel-Signal wird nicht propagiert
  - Progress-Reporting inkorrekt
  
- **Test-Coverage:**
  - ✅ Unit: Work-Item-Generierung für kleines Dataset
  - ✅ Integration: Resume-Run überspringt existierende Results
  - ✅ Integration: Cancel während Pipeline-Execution
  - ✅ Integration: Progress-Updates sind akkurat
  - ✅ Integration: Dual-Direction erstellt korrekte Anzahl Items

#### 4. **Queue-System & Task-Dependencies**
- **Komponenten:**
  - `QueueExecutor` in `executor.py`
  - Task-Dependency-Resolution
  - Background-Worker-Thread
  
- **Risiken:**
  - Deadlocks bei zirkulären Dependencies
  - Task bleibt in "running" nach Crash
  - Orphaned Tasks nach Restart
  - Race-Conditions bei Parallel-Execution
  - Status-Updates gehen verloren
  
- **Test-Coverage:**
  - ✅ Unit: Dependency-Graph-Resolution
  - ✅ Integration: Task-Chain-Execution (AttrGen → Benchmark)
  - ✅ Integration: Orphan-Cleanup nach Restart
  - ✅ Integration: Pause/Resume während Task-Execution
  - ✅ Integration: Concurrent Task-Submission

### 🟡 WICHTIG - Mittlere Priorität

#### 5. **Persona-Repositories & Data-Loading**
- **Komponenten:**
  - `FullPersonaRepository`, `FullPersonaRepositoryByDataset`
  - `PersonaRepository`, `PersonaRepositoryByDataset`
  - Attribute-Enrichment aus AttrGenerationRun
  
- **Risiken:**
  - Fehlende Personas bei Dataset-Switch
  - Attribute-Joins produzieren NULL-Werte
  - Count-Estimation vs. Actual-Count-Mismatch
  - Memory-Leak bei großen Datasets (kein Streaming)
  
- **Test-Coverage:**
  - ✅ Unit: Count-Estimation korrekt
  - ✅ Integration: Persona-Loading mit/ohne AttrGen-Filter
  - ✅ Integration: Dataset-Filtering funktioniert
  - ✅ Integration: Attribute-Enrichment korrekt gemappt

#### 6. **Analytics & Metrics-Berechnung**
- **Komponenten:**
  - `deltas_with_significance()` (Permutation-Tests)
  - `compute_order_effect_metrics()` (RMA, OBE)
  - `plot_fixed_effects_forest()` (Meta-Analysis)
  - Warm-Cache-System für Run-Detail-Page
  
- **Risiken:**
  - Statistische Berechnungen inkorrekt
  - NaN/Inf-Werte bei kleinen Samples
  - FDR-Korrektur (q-values) fehlerhaft
  - Warm-Cache schlägt bei Missing-Data fehl
  - Order-Metrics bei fehlenden Dual-Directions
  
- **Test-Coverage:**
  - ✅ Unit: Delta-Berechnung mit bekannten Werten
  - ✅ Unit: Cliff's Delta berechnen
  - ✅ Unit: FDR-Korrektur (Benjamini-Hochberg)
  - ✅ Integration: Metrics mit realem Benchmark-Run
  - ✅ Integration: Warm-Cache-Pre-Computation

#### 7. **Database-Persistierung**
- **Komponenten:**
  - `BenchPersisterPeewee`, `PersisterPeewee`
  - Batch-Insert-Logic
  - Failure-Tracking
  
- **Risiken:**
  - Constraint-Violations (Unique-Constraints)
  - Transaction-Rollback verliert Daten
  - Batch-Insert schlägt bei einem Item fehl → ganze Batch verloren
  - Foreign-Key-Violations bei parallelen Deletes
  
- **Test-Coverage:**
  - ✅ Unit: Batch-Insert mit Duplicates
  - ✅ Integration: Concurrent Writes
  - ✅ Integration: Rollback-Behavior bei Errors
  - ✅ Integration: Failure-Tracking funktioniert

### 🟢 WÜNSCHENSWERT - Niedrige Priorität

#### 8. **API-Endpunkte**
- **Komponenten:**
  - `/benchmarks/start`, `/attrgen/start`
  - `/runs/{id}/metrics`, `/runs/{id}/deltas`
  - Resume-Logic über API
  
- **Test-Coverage:**
  - ✅ Integration: API-Start triggert Background-Task
  - ✅ Integration: Status-Polling während Run
  - ✅ Integration: Error-Responses bei Invalid-Params

#### 9. **Validatoren & Business-Rules**
- **Komponenten:**
  - `AttrGenValidator`, `DatasetValidator`
  
- **Test-Coverage:**
  - ✅ Unit: Deletion-Rules (running jobs, dependencies)
  - ✅ Unit: Resume-Validation

---

## Test-Architektur

### Unit-Tests
```
apps/backend/tests/
├── unit/
│   ├── benchmarking/
│   │   ├── test_prompt_factory.py          # Prompt-Generierung
│   │   ├── test_postprocessor_likert.py    # Output-Parsing
│   │   ├── test_postprocessor_attr.py
│   │   ├── test_scale_reversal.py          # Scale-Modes
│   │   └── test_dual_direction.py
│   ├── analytics/
│   │   ├── test_deltas.py                  # Statistik-Berechnungen
│   │   ├── test_order_metrics.py
│   │   └── test_fdr_correction.py
│   ├── repositories/
│   │   ├── test_persona_repository.py
│   │   └── test_count_estimation.py
│   └── validators/
│       ├── test_attrgen_validator.py
│       └── test_dataset_validator.py
```

### Integration-Tests
```
apps/backend/tests/
├── integration/
│   ├── test_benchmark_pipeline_full.py     # ✅ Bereits vorhanden
│   ├── test_attrgen_pipeline_full.py
│   ├── test_queue_executor.py              # Task-Dependencies
│   ├── test_resume_logic.py                # Resume-Runs
│   ├── test_vllm_client.py                 # Mit Mock-vLLM-Server
│   ├── test_warm_cache.py                  # Run-Detail-Seite
│   └── test_concurrent_writes.py           # DB-Race-Conditions
```

### End-to-End-Tests
```
apps/backend/tests/
├── e2e/
│   ├── test_full_workflow.py               # Dataset → AttrGen → Benchmark → Analyse
│   ├── test_api_workflow.py                # Via API-Endpunkte
│   └── test_cancel_resume.py               # Cancel + Resume-Szenarios
```

---

## Test-Fixtures & Mocking

### Mock-LLM-Client
```python
# tests/fixtures/mock_llm.py
class MockVLLMClient:
    """Simuliert vLLM-Responses ohne echte API-Calls."""
    
    def __init__(self, response_mode='valid'):
        self.response_mode = response_mode
        self.call_count = 0
        
    def run_stream(self, specs):
        for spec in specs:
            self.call_count += 1
            if self.response_mode == 'valid':
                yield self._valid_response(spec)
            elif self.response_mode == 'invalid_json':
                yield self._invalid_json(spec)
            elif self.response_mode == 'timeout':
                raise TimeoutError()
```

### Test-Datasets
```python
# tests/fixtures/test_data.py
def create_minimal_dataset():
    """2 Personas × 3 Cases = 6 Items."""
    return {
        'personas': [...],
        'cases': [...]
    }

def create_large_dataset():
    """100 Personas × 30 Cases = 3000 Items."""
    pass
```

### Mock-vLLM-Server
```python
# tests/fixtures/mock_vllm_server.py
import flask
app = Flask(__name__)

@app.route('/v1/completions', methods=['POST'])
def completions():
    """Fake vLLM /v1/completions endpoint."""
    prompt = request.json['prompt']
    if 'rating' in prompt.lower():
        return {'choices': [{'text': '{"rating": 3, "rationale": "ok"}'}]}
    else:
        return {'choices': [{'text': '{"name":"Max","appearance":"short","biography":"short"}'}]}
```

---

## Test-Daten-Management

### Isolation
- Jeder Test nutzt eigene SQLite-DB (`/tmp/test_benchmark_{test_id}.db`)
- Cleanup in `tearDown()` oder `pytest.fixture(scope='function')`

### Realistische Test-Daten
- **Small**: 2 Personas × 3 Cases (Smoke-Tests)
- **Medium**: 10 Personas × 10 Cases (Typical-Use-Case)
- **Large**: 100 Personas × 30 Cases (Performance-Tests)

---

## Performance-Tests

### Benchmarks
```python
# tests/performance/test_benchmark_throughput.py
def test_benchmark_pipeline_throughput():
    """100 Personas × 30 Cases in <5min mit fake-LLM."""
    pass

def test_vllm_concurrent_requests():
    """8 concurrent requests sättigen vLLM-Server."""
    pass
```

### Memory-Profile
```python
# tests/performance/test_memory_usage.py
@pytest.mark.memory
def test_large_dataset_memory():
    """1000 Personas sollten <500MB RAM nutzen."""
    pass
```

---

## CI/CD-Integration

### GitHub Actions Workflow
```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: pytest apps/backend/tests/unit/ -v
      
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: docker compose -f docker-compose.test.yml up -d
      - run: pytest apps/backend/tests/integration/ -v
      
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: pytest apps/backend/tests/e2e/ -v --slow
```

### Pre-Commit Hook
```bash
#!/bin/bash
# .git/hooks/pre-commit
pytest apps/backend/tests/unit/ --maxfail=1 -q
```

---

## Test-Coverage-Ziele

| Komponente | Ziel | Aktuell |
|------------|------|---------|
| Prompt-Factories | 95% | - |
| PostProcessors | 95% | - |
| Benchmark-Pipeline | 90% | ~40% |
| AttrGen-Pipeline | 90% | - |
| Queue-Executor | 85% | - |
| Analytics | 80% | - |
| Repositories | 75% | - |
| API-Endpunkte | 70% | - |

**Gesamt-Ziel: 85% Coverage**

---

## Implementierungs-Reihenfolge

### Phase 1: Kritische Komponenten (Woche 1-2)
1. ✅ `test_prompt_factory.py` - Prompt-Generierung
2. ✅ `test_postprocessor_likert.py` - Output-Parsing
3. ✅ `test_scale_reversal.py` - Scale-Modes
4. ✅ `test_vllm_client.py` - LLM-Integration
5. ✅ `test_resume_logic.py` - Resume-Runs

### Phase 2: Pipeline & Queue (Woche 3)
6. ✅ `test_benchmark_pipeline_full.py` erweitern
7. ✅ `test_attrgen_pipeline_full.py`
8. ✅ `test_queue_executor.py`
9. ✅ `test_cancel_resume.py`

### Phase 3: Analytics & Performance (Woche 4)
10. ✅ `test_deltas.py` - Statistik
11. ✅ `test_warm_cache.py`
12. ✅ `test_benchmark_throughput.py`

### Phase 4: E2E & CI (Woche 5)
13. ✅ `test_full_workflow.py`
14. ✅ GitHub Actions Setup
15. ✅ Coverage-Reports

---

## Tools & Dependencies

```toml
# pyproject.toml oder requirements-test.txt
[tool.pytest.ini_options]
testpaths = ["apps/backend/tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: integration tests requiring DB",
    "e2e: end-to-end tests",
    "performance: performance benchmarks",
]

[tool.coverage.run]
source = ["apps/backend/src"]
omit = ["*/tests/*", "*/migrations/*"]

[tool.coverage.report]
precision = 2
show_missing = true
skip_covered = false
```

```bash
# requirements-test.txt
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-mock>=3.11.1
pytest-timeout>=2.1.0
pytest-xdist>=3.3.1  # Parallel test execution
faker>=19.0.0        # Test data generation
factory-boy>=3.3.0   # Model factories
responses>=0.23.1    # Mock HTTP requests
flask>=2.3.0         # Mock vLLM server
```

---

## Monitoring & Alerts

### Test-Metriken
- **Duration**: Jeder Test sollte <5s dauern (außer marked als `@pytest.mark.slow`)
- **Flakiness**: Max 1% Flaky-Rate
- **Coverage**: Mind. 85% maintained

### Pre-Production-Checks
```bash
# scripts/pre_production_checks.sh
#!/bin/bash
set -e

echo "Running full test suite..."
pytest apps/backend/tests/ -v --cov --cov-report=html

echo "Running static analysis..."
ruff check apps/backend/src/

echo "Running type checks..."
mypy apps/backend/src/

echo "✅ All checks passed!"
```

---

## Zusammenfassung

**Kritischste Tests (Must-Have vor GPU-Run):**
1. ✅ Prompt-Generierung (Scale-Reversal, Dual-Direction)
2. ✅ Output-Parsing (alle Edge-Cases)
3. ✅ Resume-Logic (keine Duplicates)
4. ✅ vLLM-Integration (Timeout, Concurrency)
5. ✅ Queue-Executor (Dependencies, Cancellation)

**Aufwand-Schätzung:**
- Unit-Tests: ~40 Stunden
- Integration-Tests: ~30 Stunden
- E2E-Tests: ~20 Stunden
- CI-Setup: ~10 Stunden
- **Gesamt: ~100 Stunden (2-3 Wochen Full-Time)**

**ROI:**
- Verhindert teure Fehler auf GPU-Servern
- Schnelleres Debugging durch isolierte Tests
- Confidence für refactorings
- Dokumentation durch Test-Cases
