# Multi-GPU LLM Benchmark Setup - Anleitung

## Zusammenfassung der Konfiguration

Ich habe das Multi-GPU Setup für den SLURM Cluster vollständig konfiguriert:

### 🔧 Konfigurierte Komponenten

1. **Accelerate Konfiguration** (`accelerate_config.yaml`)
   - 2 GPUs (GPU IDs 0,1 aus PyTorch-Sicht)
   - Mixed Precision FP16
   - Multi-GPU Distribution

2. **SLURM Konfiguration** (`scripts/run_slurm.sh`)
   - 2 A6000 GPUs angefordert
   - `CUDA_VISIBLE_DEVICES=1,3` (nur funktionierende GPUs)
   - Erweiterte GPU-Diagnostics
   - HuggingFace Token-Handling

3. **Benchmark Script** (`scripts/benchmark.sh`)
   - Verwendet explizite Accelerate-Konfiguration
   - 2 Prozesse für Multi-GPU
   - Klare Logging-Ausgaben

4. **Model Handler** (`app/llm_handler/model.py`)
   - HuggingFace Authentifizierung
   - Multi-GPU device mapping
   - 4-bit Quantisierung für große Modelle
   - Erweiterte Fehlerbehandlung

5. **Main Script** (`app/main.py`)
   - GPU-Diagnostics
   - Fehlerbehandlung mit Fallbacks
   - Detaillierte Telegram-Benachrichtigungen

### 🚀 Nächste Schritte

#### 1. HuggingFace Token konfigurieren
```bash
# Erstelle .env Datei
cp .env.example .env
# Füge deinen HuggingFace Token hinzu
# HF_TOKEN=hf_your_token_here
```

#### 2. Test der GPU-Konfiguration (lokal)
```bash
chmod +x scripts/test_gpu_config.sh
./scripts/test_gpu_config.sh
```

#### 3. SLURM Job starten
```bash
chmod +x start_slurm_job.sh
./start_slurm_job.sh
```

### 🔍 Monitoring

- **Job Status**: `squeue -u $USER`
- **Live Logs**: `tail -f logs/slurm-JOBID.out`
- **GPU Status**: `srun --pty bash` → `nvidia-smi`

### 🛠 Fehlerbehebung

#### GPU-Erkennungsprobleme
- Überprüfe `CUDA_VISIBLE_DEVICES` in den Logs
- Checke `nvidia-smi` Output im SLURM-Skript
- PyTorch sollte 2 GPUs erkennen nach Remapping

#### HuggingFace Zugriffsfehler
- Stelle sicher, dass HF_TOKEN in .env gesetzt ist
- Beantrage Zugriff auf Llama-3.3-70B-Instruct Model
- Fallback auf kleinere Modelle bei Bedarf

#### Memory Issues
- 4-bit Quantisierung ist aktiviert
- Device_map="auto" für automatische Verteilung
- Überwache GPU Memory mit `nvidia-smi`

### 📊 Erwartete Verbesserungen

- **Speicher**: 4-bit Quantisierung reduziert VRAM-Bedarf um ~75%
- **Speed**: Multi-GPU sollte Inference-Zeit halbieren
- **Reliability**: Bessere Fehlerbehandlung und Monitoring
- **Accessibility**: Automatische HF-Authentifizierung

Die Konfiguration ist jetzt bereit für den Produktiveinsatz mit dem 70B Llama Modell auf 2 GPUs!
