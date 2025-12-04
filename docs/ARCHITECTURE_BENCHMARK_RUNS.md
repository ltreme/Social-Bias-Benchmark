# Architektur-Übersicht: Benchmark Runs Modul

## Clean Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                     API / Presentation Layer                     │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  application/api/routers/runs.py (160 LOC)                │  │
│  │  • @router.get("/runs")                                   │  │
│  │  • @router.post("/benchmarks/start")                      │  │
│  │  • Parameter extraction & validation                      │  │
│  │  • HTTP error handling                                    │  │
│  └───────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Application Layer                          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  services/benchmark_service.py (650 LOC)                  │  │
│  │  • start_benchmark()  - orchestrate benchmark execution   │  │
│  │  • get_metrics()      - fetch & compute metrics           │  │
│  │  • get_deltas()       - coordinate delta analysis         │  │
│  │  • Coordinates Domain + Infrastructure                    │  │
│  └───────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
┌─────────────────────────┐   ┌────────────────────────────────┐
│      Domain Layer       │   │   Infrastructure Layer         │
│  ┌───────────────────┐  │   │  ┌──────────────────────────┐  │
│  │ analytics/        │  │   │  │ benchmark/               │  │
│  │   benchmarks/     │  │   │  │   progress_tracker.py    │  │
│  │     metrics.py    │  │   │  │   executor.py            │  │
│  │   (250 LOC)       │  │   │  │   data_loader.py         │  │
│  │                   │  │   │  │   cache_warming.py       │  │
│  │ • compute_*()     │  │   │  │                          │  │
│  │ • filter_*()      │  │   │  │ storage/                 │  │
│  │ • Pure functions  │  │   │  │   benchmark_cache.py     │  │
│  │ • No deps!        │  │   │  │                          │  │
│  └───────────────────┘  │   │  │ • DB access              │  │
│                         │   │  │ • Threading              │  │
└─────────────────────────┘   │  │ • External services      │  │
                              │  └──────────────────────────┘  │
                              └────────────────────────────────┘
```

## Dependency Flow

```
┌──────────┐      ┌─────────┐      ┌────────┐
│  Router  │─────▶│ Service │─────▶│ Domain │
└──────────┘      └────┬────┘      └────────┘
                       │                ▲
                       │                │
                       ▼                │
                  ┌────────────┐        │
                  │ Infra-     │────────┘
                  │ structure  │  (uses)
                  └────────────┘
```

**Regel**: Domain hat KEINE Dependencies nach außen!

## Module Mapping (Alt → Neu)

### Router-Funktionen
```
runs.py (alt)                    →  runs.py (neu)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
list_runs()                      →  list_runs()             [delegiert an Service]
get_run()                        →  get_run()               [delegiert an Service]
start_benchmark()                →  start_benchmark()       [delegiert an Service]
bench_status()                   →  bench_status()          [delegiert an Service]
run_metrics()                    →  run_metrics()           [delegiert an Service]
```

### Verschobene Logik

#### → Domain Layer (`metrics.py`)
```
_filter_by_trait_category()      →  filter_by_trait_category()
run_metrics() [Berechnungen]     →  compute_rating_histogram()
                                    compute_trait_category_histograms()
                                    compute_trait_category_summary()
run_order_metrics() [Berechn.]   →  compute_order_effect_metrics()
run_means() [Berechnungen]       →  compute_means_by_attribute()
```

#### → Infrastructure Layer

**progress_tracker.py**
```
_BENCH_PROGRESS                  →  _BENCH_PROGRESS
_bench_update_progress()         →  update_progress()
_bench_progress_poller()         →  progress_poller()
_completed_keys_for_run()        →  get_completed_keys()
_progress_status()               →  _progress_status()
```

**benchmark_cache.py**
```
_cache_key()                     →  cache_key()
_cache_get()                     →  get_cached()
_cache_put()                     →  put_cached()
_result_row_count()              →  result_row_count()
```

**data_loader.py**
```
_load_run_df()                   →  load_run_df()
_load_run_df_cached()            →  load_run_df_cached()
_df_for_read()                   →  df_for_read()
```

**cache_warming.py**
```
_WARM_CACHE_JOBS                 →  _WARM_CACHE_JOBS
_start_warm_cache_job()          →  start_warm_cache_job()
_warm_cache_worker()             →  _warm_cache_worker()
_run_warm_step()                 →  _run_warm_step()
_warm_job_snapshot()             →  warm_job_snapshot()
```

**executor.py**
```
_bench_run_background()          →  execute_benchmark_run()
  [vLLM setup logic]             →  _create_vllm_client()
```

#### → Application Layer (`benchmark_service.py`)
```
Alle Endpoint-Logik               →  BenchmarkService.method()
  - Koordination                     - start_benchmark()
  - Cache-Nutzung                    - get_metrics()
  - Error-Handling                   - get_deltas()
  - Use-Case-Workflows               - get_forest()
                                     - etc.
```

## Daten-Fluss Beispiel: GET /runs/{id}/metrics

### Alt (runs.py - alles in einem)
```
HTTP Request
    ↓
run_metrics(run_id)
    ├─ ensure_db()
    ├─ _cache_key()
    ├─ _cache_get()
    ├─ _df_for_read()
    │   ├─ _BENCH_PROGRESS.get()
    │   ├─ _load_run_df() oder _load_run_df_cached()
    ├─ [INLINE Berechnung: Histogramm]
    ├─ [INLINE Berechnung: Attribute Meta]
    ├─ [INLINE Berechnung: Kategorie-Histogramme]
    ├─ _cache_put()
    └─ return payload
    ↓
HTTP Response
```

### Neu (Clean Architecture)
```
HTTP Request
    ↓
Router.run_metrics(run_id)
    ↓
Service.get_metrics(run_id)
    ├─ cache.get_cached()                    [Infrastructure]
    ├─ data_loader.df_for_read()             [Infrastructure]
    ├─ metrics.compute_rating_histogram()    [Domain]
    ├─ analytics.summarise_rating_by()       [Domain]
    ├─ metrics.compute_trait_category_*()    [Domain]
    ├─ cache.put_cached()                    [Infrastructure]
    └─ return payload
    ↓
Router (Response)
    ↓
HTTP Response
```

**Vorteil**: Jede Schicht kann einzeln getestet werden!

## Testbarkeit

### Domain Layer (100% testbar ohne DB/HTTP)
```python
def test_compute_rating_histogram():
    df = pd.DataFrame({"rating": [1, 2, 3, 3, 4, 5]})
    result = compute_rating_histogram(df)
    assert result["bins"] == ["1", "2", "3", "4", "5"]
    assert len(result["shares"]) == 5
```

### Service Layer (testbar mit Mocks)
```python
def test_get_metrics(mocker):
    mocker.patch('data_loader.df_for_read', return_value=mock_df)
    mocker.patch('cache.get_cached', return_value=None)
    
    service = BenchmarkService()
    result = service.get_metrics(run_id=1)
    
    assert result["ok"] == True
```

### Router (nur Integration-Tests nötig)
```python
def test_run_metrics_endpoint(client):
    response = client.get("/runs/1/metrics")
    assert response.status_code == 200
    assert "hist" in response.json()
```

## Fazit

✅ **1579 Zeilen** monolithischer Code
✅ **8 Module** mit klaren Verantwortlichkeiten
✅ **Domain-Logik** ohne externe Dependencies
✅ **Service-Layer** für Wiederverwendbarkeit
✅ **Router** auf 160 Zeilen reduziert
✅ **Testbarkeit** drastisch verbessert
✅ **Wartbarkeit** durch Separation of Concerns
