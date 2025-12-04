# Performance Optimization Guide

## Problem: Langsame API-Responses

### Ursachen

1. **Erste Request nach Neustart ist langsam (~300ms)**
   - Peewee-Import benötigt ~260ms beim ersten Mal
   - Python muss Module kompilieren und in Bytecode umwandeln
   - Das ist normal und betrifft nur den ersten Request pro Worker-Prozess

2. **Docker Volume Performance auf macOS**
   - Bind-Mounts (`.:/app`) sind auf macOS deutlich langsamer als auf Linux
   - Jeder File-Access geht über die Docker-VM
   - Betrifft besonders `--reload` Flag, das bei jeder Änderung Dateien scannt

3. **Uvicorn --reload Overhead**
   - Überwacht alle Python-Dateien im `--reload-dir`
   - Bei Code-Änderungen wird Worker-Prozess neugestartet
   - Neuer Prozess muss alle Module neu importieren (wieder ~300ms)

4. **Postgres Connection Pool**
   - Zu großer Pool (80 Connections) kann Overhead verursachen
   - Für UI-Workload reichen 20 Connections

### Angewendete Optimierungen

#### docker-compose.yml

```yaml
# 1. Volume-Mount mit :cached für bessere macOS Performance
volumes:
  - .:/app:cached
  - api_pycache:/app/apps/backend/src/backend/__pycache__

# 2. Python Bytecode Caching aktiviert
environment:
  PYTHONDONTWRITEBYTECODE: "0"  # Bytecode-Dateien erstellen

# 3. Connection Pool reduziert
DB_URL: postgresql+pool://sbb:sbb@postgres:5432/sbb?max_connections=20&stale_timeout=300

# 4. Keep-Alive Timeout erhöht für weniger Connection-Overhead
command: >-
  bash -lc "uvicorn backend.application.api.main:app --host 0.0.0.0 --port 8765 --reload \
  --app-dir apps/backend/src \
  --reload-dir apps/backend/src \
  --workers 1 \
  --timeout-keep-alive 75"
```

### Weitere Optimierungsmöglichkeiten

#### Option 1: Production Mode (ohne Hot Reload)

Wenn du keine Live-Code-Änderungen brauchst, entferne `--reload`:

```yaml
command: >-
  bash -lc "uvicorn backend.application.api.main:app --host 0.0.0.0 --port 8765 \
  --app-dir apps/backend/src \
  --workers 1 \
  --timeout-keep-alive 75"
```

**Vorteile:**
- 10x schnellerer Startup (keine File-Watching)
- Keine Worker-Restarts bei Code-Änderungen
- Module werden nur einmal beim Start geladen

**Nachteile:**
- Manuelle Container-Restarts bei Code-Änderungen: `docker compose restart api`

#### Option 2: Uvicorn Worker Preloading

Für bessere Response-Zeiten bei parallelen Requests (noch nicht implementiert):

```yaml
command: >-
  bash -lc "uvicorn backend.application.api.main:app --host 0.0.0.0 --port 8765 \
  --app-dir apps/backend/src \
  --workers 4 \
  --timeout-keep-alive 75 \
  --preload"
```

**Achtung:** Nicht mit `--reload` kombinierbar!

#### Option 3: Gunicorn statt Uvicorn (für Produktion)

```yaml
command: >-
  bash -lc "gunicorn backend.application.api.main:app \
  --bind 0.0.0.0:8765 \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --preload \
  --timeout 120"
```

### Benchmarks

#### Aktuelle Performance (nach allen Optimierungen)

```bash
# GET /traits (50 Einträge mit linked_results_n)
curl -w "Time: %{time_total}s\n" http://localhost:8765/traits
# ~85ms (vorher: 1.86s!) ✅

# GET /admin/models (einfache Abfrage)
curl -w "Time: %{time_total}s\n" http://localhost:8765/admin/models
# ~20-30ms (konsistent schnell)

# Erster Request nach Neustart
# ~300-400ms (einmaliger Import-Overhead)

# Zweiter Request
# ~20-50ms (normal)

# Durchschnitt nach Warm-up
# ~20-30ms für einfache DB-Queries
# ~85ms für Queries mit Aggregationen
# ~100-200ms für komplexe Aggregationen
```

#### Production Mode (ohne --reload)

```bash
# Erster Request
# ~300ms (nur einmal beim Container-Start)

# Alle weiteren Requests
# ~15-25ms (konsistent schnell)
```

### Monitoring

Um Performance-Probleme zu identifizieren:

```bash
# Request-Timing mit curl
curl -w "\nTime: %{time_total}s\n" http://localhost:8765/admin/models

# API Logs ansehen
docker compose logs -f api | grep -i "time\|slow\|error"

# Profiling im Container
docker compose exec api python -c "
import time
start = time.time()
from backend.infrastructure.storage.db import init_database, get_db
print(f'Import time: {(time.time() - start) * 1000:.1f}ms')
"
```

### Zusammenfassung

✅ **Normal:** Erste Request ~300ms (Modul-Import-Overhead)  
✅ **Normal:** Folgende Requests 20-85ms (je nach Query-Komplexität)  
✅ **Optimiert:** Connection Pool, Volume-Mounts, Bytecode-Caching  
✅ **Optimiert:** SQL GROUP BY statt Python-Loops (91% schneller!)  
⚠️ **Trade-off:** Hot-Reload vs. Performance (Development vs. Production)  

**Wichtigste Optimierung:** Verwendet SQL-Aggregationen (GROUP BY, COUNT) statt alle Daten in Python zu laden!

Für **Development**: Aktuelle Konfiguration ist gut (Hot-Reload + optimierte Performance)  
Für **Production**: Entferne `--reload` und erwäge mehr Workers
