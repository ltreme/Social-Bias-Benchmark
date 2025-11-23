# Task Queue System

## Overview

Das Task Queue System ermöglicht die Ausführung mehrerer langläufiger Tasks (Benchmarks, Attribute-Generierung) in einer sequentiellen Warteschlange.

## Features

✅ **Task-Types unterstützt:**
- `benchmark`: Benchmark-Läufe
- `attrgen`: Attribut-Generierung für Personas
- `pool_gen`: Pool-Generierung (geplant)
- `balanced_gen`: Balanced Dataset-Generierung (geplant)

✅ **Dependencies (Hybrid-Ansatz):**
- AttrGen → Benchmark Dependencies
- Automatische Injection von `attrgen_run_id` in abhängige Benchmarks
- Cascade Skip bei fehlgeschlagenen Dependencies

✅ **Status-Management:**
- `queued`: Bereit zur Ausführung
- `waiting`: Wartet auf Dependency
- `running`: Wird gerade ausgeführt
- `done`: Erfolgreich abgeschlossen
- `failed`: Fehlgeschlagen
- `cancelled`: Manuell abgebrochen
- `skipped`: Übersprungen (Dependency fehlgeschlagen)

✅ **Notifications:**
- Telegram-Benachrichtigungen bei Task-Completion
- Fehler-Kategorisierung (kritisch vs. normal)
- Retry-Mechanismus für Telegram-API

## Setup

### 1. Migration ausführen

```bash
cd apps/backend
python -m backend.infrastructure.storage.migrate --add-task-queue
```

### 2. Telegram konfigurieren (optional)

```bash
# .env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Ohne Telegram läuft die Queue trotzdem, Benachrichtigungen werden nur geloggt.

## API Endpoints

### Queue Tasks hinzufügen

```http
POST /queue/add
Content-Type: application/json

{
  "task_type": "benchmark",
  "config": {
    "dataset_id": 5,
    "model_name": "mistral-24b",
    "include_rationale": true,
    "batch_size": 4
  },
  "label": "Mistral 24B - Dataset 5 + Rationale",
  "depends_on": null
}
```

**Mit Dependency:**
```json
{
  "task_type": "benchmark",
  "config": {
    "dataset_id": 5,
    "model_name": "mistral-24b",
    "include_rationale": false
  },
  "depends_on": 123  // AttrGen Task ID
}
```

### Queue Status abrufen

```http
GET /queue?include_done=false&limit=50
```

### Task abbrechen

```http
POST /queue/{task_id}/cancel
```

### Queue starten/pausieren

```http
POST /queue/start
POST /queue/pause
POST /queue/resume
POST /queue/stop
```

### Statistiken

```http
GET /queue/stats
```

## Usage Examples

### Beispiel 1: Einfacher Benchmark

```python
import requests

# Task zur Queue hinzufügen
response = requests.post('http://localhost:8765/queue/add', json={
    "task_type": "benchmark",
    "config": {
        "dataset_id": 5,
        "model_name": "mistral-24b",
        "include_rationale": true,
        "llm": "vllm",
        "vllm_base_url": "http://localhost:8000",
        "batch_size": 4
    },
    "label": "Mistral 24B Benchmark"
})

task_id = response.json()['task_id']
print(f"Task added: #{task_id}")

# Queue starten
requests.post('http://localhost:8765/queue/start')
```

### Beispiel 2: AttrGen mit abhängigem Benchmark

```python
# 1. AttrGen Task hinzufügen
attrgen_response = requests.post('http://localhost:8765/queue/add', json={
    "task_type": "attrgen",
    "config": {
        "dataset_id": 5,
        "model_name": "mistral-24b",
        "llm": "vllm",
        "batch_size": 4
    }
})
attrgen_id = attrgen_response.json()['task_id']

# 2. Benchmark mit Dependency hinzufügen
benchmark_response = requests.post('http://localhost:8765/queue/add', json={
    "task_type": "benchmark",
    "config": {
        "dataset_id": 5,
        "model_name": "mistral-24b",
        "include_rationale": true
    },
    "depends_on": attrgen_id  # Wartet auf AttrGen
})

# attrgen_run_id wird automatisch injiziert!
```

### Beispiel 3: Batch-Queue für Nacht-Jobs

```python
# AttrGen für 3 Modelle
models = ["mistral-24b", "llama-70b", "gpt-4"]
dataset_id = 5

for model in models:
    # AttrGen
    attrgen = requests.post('http://localhost:8765/queue/add', json={
        "task_type": "attrgen",
        "config": {"dataset_id": dataset_id, "model_name": model}
    })
    attrgen_id = attrgen.json()['task_id']
    
    # 3 Benchmark-Varianten abhängig von AttrGen
    for rationale in [True, False]:
        for scale_mode in ['in', 'rev']:
            requests.post('http://localhost:8765/queue/add', json={
                "task_type": "benchmark",
                "config": {
                    "dataset_id": dataset_id,
                    "model_name": model,
                    "include_rationale": rationale,
                    "scale_mode": scale_mode
                },
                "depends_on": attrgen_id
            })

# Alles queued → Queue starten und ins Bett gehen!
requests.post('http://localhost:8765/queue/start')
```

## Architektur

```
┌─────────────────────────────────────────┐
│         API Layer (FastAPI)             │
│  /queue/add, /queue, /queue/start, ...  │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         QueueService                    │
│  • add_to_queue()                       │
│  • remove_from_queue()                  │
│  • get_queue_status()                   │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         QueueExecutor (Worker)          │
│  • _get_next_runnable_task()            │
│  • _execute_task()                      │
│  • _check_waiting_tasks()               │
│  • Dependency-Auflösung                 │
└──────────────┬──────────────────────────┘
               │
        ┌──────┴───────┐
        ▼              ▼
┌────────────┐  ┌────────────────┐
│  Benchmark │  │  NotificationService │
│  Service   │  │  (Telegram)          │
└────────────┘  └────────────────┘
```

## Error Handling

### Kritische Fehler
Bei kritischen Fehlern (z.B. vLLM Server nicht erreichbar):
1. Task wird als `failed` markiert
2. Abhängige Tasks werden `skipped`
3. **Telegram-Warnung** mit ⚠️ CRITICAL
4. Queue läuft mit nächstem Task weiter

### Normale Fehler
Bei normalen Fehlern (z.B. Parsing-Error):
1. Task wird als `failed` markiert
2. Abhängige Tasks werden `skipped`
3. Telegram-Benachrichtigung
4. Queue läuft weiter

### Cancellation
Bei manueller Cancellation:
1. Task wird als `cancelled` markiert
2. Abhängige Tasks werden `cancelled` (nicht `skipped`)
3. Keine Telegram-Benachrichtigung

## Limitations (Hybrid-Ansatz)

❌ **Nicht unterstützt:**
- Benchmark → Benchmark Dependencies
- Benchmark → AttrGen Dependencies
- Transitive Dependencies (A→B→C)
- Parallele Ausführung

✅ **Unterstützt:**
- AttrGen → Benchmark Dependencies
- AttrGen → Multiple Benchmarks (Fan-out)
- Sequentielle Abarbeitung (FIFO)

## Monitoring

```bash
# Queue-Status in Terminal
watch -n 2 'curl -s http://localhost:8765/queue/stats | jq'

# Tasks anzeigen
curl -s http://localhost:8765/queue | jq
```

## Troubleshooting

### Queue startet nicht
```bash
curl -X POST http://localhost:8765/queue/start
# Prüfe Response
```

### Task hängt in "running"
```bash
# Check Task Details
curl http://localhost:8765/queue/{task_id}

# Cancel wenn nötig
curl -X POST http://localhost:8765/queue/{task_id}/cancel
```

### Telegram funktioniert nicht
```bash
# Check env vars
echo $TELEGRAM_BOT_TOKEN
echo $TELEGRAM_CHAT_ID

# Test manuell
python -c "
from backend.infrastructure.notification.notification_service import TelegramClient
client = TelegramClient()
client.send_message('Test message')
"
```

## Future Enhancements

- [ ] Pool/Balanced Gen Support
- [ ] Erweiterte Dependencies (arbitrary graph)
- [ ] Task-Prioritäten
- [ ] Scheduled Tasks (Cron-like)
- [ ] Multi-Worker Support
- [ ] Web-UI für Queue-Management
- [ ] Email-Notifications
