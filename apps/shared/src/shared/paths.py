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


def get_enriched_personas_path(model_name: str) -> str:
    """
    Returns the path to the enriched personas directory.
    """
    path = f"out/enriched_personas/{model_name}"
    if not os.path.exists(path):
        os.makedirs(path)
    return f"{path}/enriched_personas.csv"
