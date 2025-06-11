import pandas as pd
from .eval_tools import extract_score


import pandas as pd
import re
from typing import Dict, List, Any, Optional

class LLMResultEvaluator:
    """
    Evaluates LLM scenario results for bias and group effects.

    Parameters
    ----------
    results_path : str
        Path to CSV results file (must have case_id, persona_id, response).
    personas_path : str
        Path to personas CSV (must have persona_id and demographic features).
    cases_path : str
        Path to cases CSV (must have case_id and expected_bias).
    """

    def __init__(self, results_path: str, personas_path: str, cases_path: str):
        # Load CSV files
        self.results = pd.read_csv(results_path)
        self.personas = pd.read_csv(personas_path)
        self.cases = pd.read_csv(cases_path)
        # Extract score from response
        self.results["score"] = self.results["response"].apply(self._extract_score)
        # Merge all data
        self.merged = (
            self.results
            .merge(self.personas, on="persona_id", how="left")
            .merge(self.cases, on="case_id", how="left")
        )

    def case_metrics(self, groupings: List[str] = ["gender", "ethnicity", "socioeconomic_status"]) -> pd.DataFrame:
        """
        Computes key metrics per case and specified demographic groups.

        Parameters
        ----------
        groupings : list of str
            Demographic columns for group difference calculation.

        Returns
        -------
        pd.DataFrame with one row per case and the following columns:
        - mean, std, min, max, range, n
        - For each grouping: mean_<group>, diff_<group> (where possible)
        """
        df = self.merged.copy()
        metrics = []

        for case_id, sub in df.groupby("case_id"):
            metric = {"case_id": case_id}
            scores = sub["score"].dropna()
            metric.update({
                "mean": scores.mean(),
                "std": scores.std(),
                "min": scores.min(),
                "max": scores.max(),
                "range": scores.max() - scores.min(),
                "n": scores.count(),
                "expected_bias": sub["expected_bias"].iloc[0] if "expected_bias" in sub else None,
            })

            # Compute group mean and difference for each specified demographic
            for group in groupings:
                if group in sub.columns:
                    means = sub.groupby(group)["score"].mean()
                    for k, v in means.items():
                        metric[f"mean_{group}_{k}"] = v
                    if len(means) == 2:
                        # Only for binary groups: diff between the two
                        vals = means.values
                        metric[f"diff_{group}"] = vals[0] - vals[1]
                    else:
                        # For >2 groups, store max difference
                        metric[f"max_diff_{group}"] = means.max() - means.min()
            metrics.append(metric)

        return pd.DataFrame(metrics)

    def summary(self, groupings: List[str] = ["gender", "ethnicity", "socioeconomic_status"]) -> Dict[str, Any]:
        """
        Produces a summary dict of key per-case metrics, outliers, and group differences.

        Returns
        -------
        dict: Summary including metrics per case, cases with highest std/range/group diff, and overall stats.
        """
        metrics = self.case_metrics(groupings=groupings)
        summary = {
            "metrics_per_case": metrics.set_index("case_id").to_dict(orient="index"),
        }
        # Find top outlier cases
        summary["highest_variance_cases"] = metrics.sort_values("std", ascending=False).head(5)["case_id"].tolist()
        summary["highest_range_cases"] = metrics.sort_values("range", ascending=False).head(5)["case_id"].tolist()
        # Find highest group differences per demographic
        for group in groupings:
            diff_cols = [col for col in metrics.columns if col.startswith("diff_") or col.startswith("max_diff_")]
            diff_cols = [c for c in diff_cols if group in c]
            if diff_cols:
                col = diff_cols[0]
                top_cases = metrics.reindex(metrics[col].abs().sort_values(ascending=False).index).head(5)["case_id"].tolist()
                summary[f"highest_{group}_diff_cases"] = top_cases
        return summary


