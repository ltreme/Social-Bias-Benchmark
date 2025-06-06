import pandas as pd
import re

# --- 1. Helper: extract numeric score from Likert-style string ---
def extract_score(response: str) -> int:
    match = re.match(r"(\d)\.", str(response).strip())
    return int(match.group(1)) if match else None

# --- 2. Preprocessing: extract and compute all relevant scores ---
def prepare_scores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["score_in_order"] = df["response_in_order"].apply(extract_score)
    df["score_reverse"] = df["response_reverse"].apply(extract_score)
    df["adjusted_reverse_score"] = df["score_reverse"].apply(lambda x: 6 - x if pd.notnull(x) else None)
    df["adjusted_difference"] = df["score_in_order"] - df["adjusted_reverse_score"]
    return df

# --- 3. Compute core metrics ---
def compute_metrics(df: pd.DataFrame) -> dict:
    accuracy = (df["score_in_order"] == df["adjusted_reverse_score"]).mean()
    tolerance = (df["adjusted_difference"].abs() <= 1).mean()
    mean_in_order = df["score_in_order"].mean()
    mean_reverse = df["adjusted_reverse_score"].mean()
    neutral_count = ((df['score_in_order'] == 3) | (df['adjusted_reverse_score'] == 3)).sum()
    extreme_count = ((df['score_in_order'].isin([1,5])) | (df['adjusted_reverse_score'].isin([1,5]))).sum()
    total = len(df)
    neutral_pct = neutral_count / (2*total)
    extreme_pct = extreme_count / (2*total)
    return {
        "Accuracy (identical answers)": round(accuracy * 100, 2),
        "Tolerance Score (±1)": round(tolerance * 100, 2),
        "Mean In-Order Score": round(mean_in_order, 2),
        "Mean Adjusted Reverse Score": round(mean_reverse, 2),
        "Neutral Responses": round(neutral_pct, 2),
        "Extreme Responses": round(extreme_pct, 2)
    }

# --- 4. Main entry point for Likert-based evaluation ---
def benchmark_summary(df: pd.DataFrame) -> dict:
    df_prepared = prepare_scores(df)
    return compute_metrics(df_prepared)

def benchmark_summary_from_file(file_path: str) -> dict:
    """
    Load a CSV file and compute the benchmark summary.
    """
    df = pd.read_csv(file_path)
    return benchmark_summary(df)