import os

PATH_PERSONAS_CSV = "data/benchmark/bias/personas/personas.csv"
PATH_CASES_CSV = "data/benchmark/bias/cases/cases.csv"


def get_likert_benchmark_results_path(model_name: str, timestamp: str) -> str:
    """
    Returns the path to the Likert benchmark results directory.
    """
    if not os.path.exists("out/likert/" + model_name):
        os.makedirs("out/likert/" + model_name)

    return f"out/likert/{model_name}/likert_5_results_{timestamp}.csv"


def get_enriched_personas_path(model_name: str, run_id: str | None = None) -> str:
    """Pfad zur Enriched-Personas CSV.

    Wenn ein RUN_ID (z.B. Timestamp oder Slurm Job-ID) gesetzt ist, wird ein eigener
    Unterordner erzeugt, sodass parallele Jobs nicht kollidieren.
    Beispiel: out/enriched_personas/<model>/<run_id>/enriched_personas.csv
    Ohne RUN_ID bleibt das alte Verhalten zur Abwärtskompatibilität.
    """
    base = f"out/enriched_personas/{model_name}"
    path = f"{base}/{run_id}" if run_id else base
    os.makedirs(path, exist_ok=True)
    return f"{path}/enriched_personas.csv"
