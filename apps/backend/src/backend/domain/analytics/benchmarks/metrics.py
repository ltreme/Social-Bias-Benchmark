"""Metrics computation for benchmark analysis."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

UNKNOWN_TRAIT_CATEGORY = "Unbekannt"


def filter_by_trait_category(
    df: pd.DataFrame, trait_category: Optional[str]
) -> pd.DataFrame:
    """Filter DataFrame by trait category.

    Args:
        df: Input DataFrame
        trait_category: Category to filter by, or None for no filtering

    Returns:
        Filtered DataFrame
    """
    if not trait_category:
        return df
    work = df.copy()
    work["trait_category"] = (
        work.get("trait_category").fillna(UNKNOWN_TRAIT_CATEGORY).astype(str)
    )
    return work.loc[work["trait_category"] == trait_category]


def compute_rating_histogram(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute histogram of ratings.

    Args:
        df: DataFrame with 'rating' column

    Returns:
        Dict with bins, shares, and counts
    """
    if df.empty or "rating" not in df.columns:
        return {"bins": [], "shares": [], "counts": []}

    s = df["rating"].dropna().astype(int)
    if s.empty:
        return {"bins": [], "shares": [], "counts": []}

    cats = list(range(int(s.min()), int(s.max()) + 1))
    counts = s.value_counts().reindex(cats, fill_value=0).sort_index()
    shares = (counts / counts.sum()).tolist()

    return {
        "bins": [str(c) for c in cats],
        "shares": shares,
        "counts": [int(x) for x in counts.tolist()],
    }


def compute_trait_category_histograms(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Compute histograms grouped by trait category.

    Args:
        df: DataFrame with 'rating' and 'trait_category' columns

    Returns:
        List of dicts with category histograms
    """
    if df.empty:
        return []

    cat_work = df.copy()
    if "trait_category" in cat_work.columns:
        tc_series = (
            cat_work["trait_category"].fillna(UNKNOWN_TRAIT_CATEGORY).astype(str)
        )
    else:
        tc_series = pd.Series(
            [UNKNOWN_TRAIT_CATEGORY] * len(cat_work), index=cat_work.index
        )
    cat_work["trait_category"] = tc_series

    s = df["rating"].dropna().astype(int)
    if s.empty:
        return []
    cats = list(range(int(s.min()), int(s.max()) + 1))

    cat_hists: List[Dict[str, Any]] = []
    for cat, sub in cat_work.groupby("trait_category"):
        seq = pd.to_numeric(sub["rating"], errors="coerce").dropna().astype(int)
        cat_counts = seq.value_counts().reindex(cats, fill_value=0).sort_index()
        total_cat = cat_counts.sum()
        cat_shares = (
            (cat_counts / total_cat).tolist() if total_cat > 0 else [0.0] * len(cats)
        )
        cat_hists.append(
            {
                "category": cat,
                "bins": [str(x) for x in cats],
                "counts": [int(x) for x in cat_counts.tolist()],
                "shares": cat_shares,
            }
        )
    return cat_hists


def compute_trait_category_summary(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Compute summary statistics grouped by trait category.

    Args:
        df: DataFrame with 'rating' and 'trait_category' columns

    Returns:
        List of dicts with category summaries
    """
    if df.empty:
        return []

    cat_work = df.copy()
    if "trait_category" in cat_work.columns:
        tc_series = (
            cat_work["trait_category"].fillna(UNKNOWN_TRAIT_CATEGORY).astype(str)
        )
    else:
        tc_series = pd.Series(
            [UNKNOWN_TRAIT_CATEGORY] * len(cat_work), index=cat_work.index
        )
    cat_work["trait_category"] = tc_series

    cat_summary = (
        cat_work.groupby("trait_category")["rating"]
        .agg(["count", "mean", "std"])
        .reset_index()
        .rename(columns={"trait_category": "category"})
    )
    return [
        {
            "category": str(r["category"]),
            "count": int(r["count"]),
            "mean": float(r["mean"]),
            "std": float(r["std"]) if r["std"] == r["std"] else None,
        }
        for _, r in cat_summary.iterrows()
    ]


def compute_order_effect_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute metrics for order effects (in vs. rev).

    Args:
        df: DataFrame with 'scale_order' and 'rating' columns

    Returns:
        Dict with RMA, OBE, usage, test-retest, and correlation metrics
    """
    if df.empty or "scale_order" not in df.columns:
        return {
            "n_pairs": 0,
            "rma": {},
            "obe": {},
            "usage": {},
            "test_retest": {},
            "correlation": {},
            "by_case": [],
            "by_trait_category": [],
        }

    work = df.copy()
    # For order-consistency, we need to compare RAW ratings
    # A consistent model should give: rating_in == 6 - rating_rev_raw
    # (because rev scale is displayed inverted to the user/model)
    #
    # Using rating_raw (before any normalization) is correct here.
    # We do NOT want scale-order normalization applied because that would
    # make the comparison meaningless (we'd be comparing normalized values
    # which are already transformed to be comparable).
    rating_col = "rating_raw" if "rating_raw" in work.columns else "rating"
    sub = work.loc[
        work["scale_order"].isin(["in", "rev"]) & work[rating_col].notna(),
        ["persona_uuid", "case_id", rating_col, "scale_order"],
    ].copy()
    if rating_col != "rating":
        sub = sub.rename(columns={rating_col: "rating"})

    if sub.empty:
        return {
            "n_pairs": 0,
            "rma": {},
            "obe": {},
            "usage": {},
            "test_retest": {},
            "correlation": {},
            "by_case": [],
            "by_trait_category": [],
        }

    piv = sub.pivot_table(
        index=["persona_uuid", "case_id"],
        columns="scale_order",
        values="rating",
        aggfunc="first",
    ).reset_index()

    if not ("in" in piv.columns and "rev" in piv.columns):
        return {
            "n_pairs": 0,
            "rma": {},
            "obe": {},
            "usage": {},
            "test_retest": {},
            "correlation": {},
            "by_case": [],
            "by_trait_category": [],
        }

    pairs = piv.dropna(subset=["in", "rev"]).copy()
    if pairs.empty:
        return {
            "n_pairs": 0,
            "rma": {},
            "obe": {},
            "usage": {},
            "test_retest": {},
            "correlation": {},
            "by_case": [],
            "by_trait_category": [],
        }

    # For consistency check with RAW ratings:
    # - "in" scale: 1 = "gar nicht", 5 = "sehr"
    # - "rev" scale: 1 = "sehr", 5 = "gar nicht" (displayed inverted)
    # A consistent response means: rating_in == 6 - rating_rev
    # So we compute: diff = rating_in - (6 - rating_rev) = rating_in + rating_rev - 6
    # Exact match when diff == 0 (i.e., rating_in + rating_rev == 6)
    pairs["rev_normalized"] = 6 - pairs["rev"].astype(float)
    pairs["diff"] = pairs["in"].astype(float) - pairs["rev_normalized"]
    pairs["abs_diff"] = pairs["diff"].abs()

    # RMA (Response Magnitude Asymmetry)
    exact = float((pairs["abs_diff"] == 0).mean()) if len(pairs) else 0.0
    mae = float(pairs["abs_diff"].mean()) if len(pairs) else 0.0

    try:
        from backend.domain.analytics.benchmarks.analytics import mann_whitney_cliffs

        _, _, cliffs = mann_whitney_cliffs(pairs["in"], pairs["rev_normalized"])
        cliffs = float(cliffs) if np.isfinite(cliffs) else float("nan")
    except Exception:
        cliffs = float("nan")

    # OBE (Order Bias Effect)
    d = pairs["diff"].to_numpy(dtype=float)
    n = d.size
    mu = float(d.mean()) if n else 0.0
    sd = float(d.std(ddof=1)) if n > 1 else 0.0
    se = sd / np.sqrt(n) if n > 1 else 0.0
    ci_low = mu - 1.96 * se
    ci_high = mu + 1.96 * se

    # Usage metrics
    s = pd.to_numeric(sub["rating"], errors="coerce").dropna()
    eei = float(((s == 1) | (s == 5)).mean()) if not s.empty else 0.0
    mni = float((s == 3).mean()) if not s.empty else 0.0
    sv = float(s.std(ddof=1)) if s.size > 1 else 0.0

    # Test-retest
    within1 = float((pairs["abs_diff"] <= 1).mean()) if len(pairs) else 0.0

    # Correlations (comparing in vs normalized rev for consistency)
    pear = (
        float(pairs["in"].corr(pairs["rev_normalized"], method="pearson"))
        if len(pairs) > 1
        else float("nan")
    )
    spear = (
        float(pairs["in"].corr(pairs["rev_normalized"], method="spearman"))
        if len(pairs) > 1
        else float("nan")
    )
    try:
        import scipy.stats as ss

        kend = float(ss.kendalltau(pairs["in"], pairs["rev_normalized"]).correlation)
    except Exception:
        kend = float("nan")

    return {
        "n_pairs": int(len(pairs)),
        "rma": {"exact_rate": exact, "mae": mae, "cliffs_delta": cliffs},
        "obe": {"mean_diff": mu, "ci_low": ci_low, "ci_high": ci_high, "sd": sd},
        "usage": {"eei": eei, "mni": mni, "sv": sv},
        "test_retest": {"within1_rate": within1, "mean_abs_diff": mae},
        "correlation": {"pearson": pear, "spearman": spear, "kendall": kend},
    }


def compute_means_by_attribute(
    df: pd.DataFrame, attribute: str, top_n: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Compute mean ratings grouped by attribute.

    Args:
        df: DataFrame with 'rating' and the specified attribute column
        attribute: Attribute column name
        top_n: Optional limit on number of categories to return

    Returns:
        List of dicts with category, count, and mean
    """
    if df.empty or attribute not in df.columns:
        return []

    work = df.copy()
    work[attribute] = work[attribute].fillna("Unknown").astype(str)
    s = pd.to_numeric(work["rating"], errors="coerce")
    g = work.assign(r=s).groupby(attribute)["r"].agg(["count", "mean"]).reset_index()
    g = g.sort_values("count", ascending=False)
    if top_n and top_n > 0:
        g = g.head(int(top_n))
    return [
        {
            "category": str(r[attribute]),
            "count": int(r["count"]),
            "mean": float(r["mean"]),
        }
        for _, r in g.iterrows()
    ]
