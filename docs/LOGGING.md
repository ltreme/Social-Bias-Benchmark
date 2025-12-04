# Logging Configuration

## Log Files

Das Backend schreibt nun in separate Log-Dateien für bessere Übersichtlichkeit:

### Dateien

```
logs/
├── api.log         # FastAPI Requests, allgemeine API-Activity
├── queue.log       # Queue Executor, Task Management, Notifications
└── benchmark.log   # Benchmark/AttrGen Execution, Progress, Errors
```

### Konfiguration

- **Log Level**: Umgebungsvariable `LOG_LEVEL` (default: `INFO`)
- **Console Output**: Nur `WARNING` und höher (reduziert Noise)
- **Rotation**: 
  - `api.log`: 10 MB, 5 Backups
  - `queue.log`: 50 MB, 10 Backups
  - `benchmark.log`: 100 MB, 10 Backups

### Verwendung

Die Logs werden automatisch beim API-Start konfiguriert (`setup_logging()` in `app.py`).

Zum Monitoren eines laufenden Benchmarks:

```bash
# Nur Benchmark-Logs
tail -f logs/benchmark.log

# Nur Queue-Logs
tail -f logs/queue.log

# Nur API-Logs (ohne Benchmark-Spam)
tail -f logs/api.log

# Alle wichtigen Events (WARNING+)
docker-compose logs -f api
```

### Stall Detection

Der Queue Executor erkennt jetzt automatisch "hängende" Benchmarks:

- **Timeout**: 15 Minuten ohne Progress
- **Erkennung**: Vergleicht `done` count bei jedem Poll
- **Aktion**: Task als `failed` markiert, Telegram-Notification gesendet
- **Log**: `STALLED: No progress for 900s (stuck at X/Y)`

### Debugging

Bei Problemen:

1. **Benchmark hängt**: `logs/benchmark.log` → Suche nach `STALLED` oder `ERROR`
2. **Queue funktioniert nicht**: `logs/queue.log` → Heartbeat alle 5 Min
3. **Connection Pool**: `logs/queue.log` → Suche nach `Connection pool exhausted`
4. **vLLM Cache**: `logs/benchmark.log` → Suche nach `UNEXPECTED RATIONALE`

### Beispiel Log-Ausgaben

**Benchmark Progress (benchmark.log):**
```
2025-11-23 00:35:12 INFO [backend.domain.benchmarking.benchmark] Processing personas batch 1-500
2025-11-23 00:40:12 INFO [backend.infrastructure.queue.executor] Heartbeat: Task #42 still running (benchmark run_id=123, elapsed=300s)
2025-11-23 00:45:12 INFO [backend.infrastructure.queue.executor] Benchmark 123 progress: 250/1000 (25.0%), last progress: 5s ago
```

**Stall Detection (benchmark.log):**
```
2025-11-23 01:00:00 ERROR [backend.infrastructure.queue.executor] Benchmark 123 STALLED: No progress for 900s (stuck at 250/1000). Possible causes: vLLM timeout, cache pollution, OOM
```

**API Requests (api.log):**
```
2025-11-23 00:35:00 INFO [backend.application.api.routers.queue] GET /queue/tasks - 200
2025-11-23 00:35:03 INFO [backend.application.api.routers.queue] POST /queue/add - 200
```
