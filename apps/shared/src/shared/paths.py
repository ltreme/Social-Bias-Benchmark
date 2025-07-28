PATH_PERSONAS_CSV = "data/benchmark/bias/personas/personas.csv"
PATH_CASES_CSV = "data/benchmark/bias/cases/cases.csv"


def get_likert_benchmark_results_path(model_name: str, timestamp: str) -> str:
    """
    Returns the path to the Likert benchmark results directory.
    """
    return f"out/likert/{model_name}/likert_5_results_{timestamp}.csv"
