from __future__ import annotations

from dataclasses import dataclass
from math import erf, sqrt
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd
import peewee as pw

from backend.domain.analytics.persona.analytics import set_default_theme
from backend.infrastructure.storage.db import (
    create_tables,
    db_proxy,
    get_db,
    init_database,
)
from backend.infrastructure.storage.models import (
    BenchmarkResult,
    BenchmarkRun,
    Country,
    DatasetPersona,
    Model,
    Persona,
    Trait,
)

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    from matplotlib.ticker import PercentFormatter
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Install seaborn and matplotlib to use plotting helpers: pip install seaborn matplotlib"
    ) from exc


@dataclass(slots=True)
class BenchQuery:
    model_names: Sequence[str] | None = None
    case_ids: Sequence[str] | None = None  # legacy name
    trait_ids: Sequence[str] | None = None
    dataset_ids: Sequence[int] | None = None
    run_ids: Sequence[int] | None = None
    include_rationale: bool | None = None
    db_url: str | None = None


_SCHEMA_READY = False


def _ensure_db(db_url: str | None) -> None:
    global _SCHEMA_READY
    if getattr(db_proxy, "obj", None) is None or db_url:
        init_database(db_url=db_url)
        _SCHEMA_READY = False
    if not _SCHEMA_READY:
        create_tables()
        _SCHEMA_READY = True


def load_benchmark_dataframe(cfg: BenchQuery) -> pd.DataFrame:
    """Load benchmark results joined with persona demographics.

    Columns: dataset_id, persona_uuid, case_id, model_name, rating, age, gender,
            origin_region, religion, sexuality, marriage_status, education, occupation
    """
    _ensure_db(cfg.db_url)
    db = get_db()

    q = (
        BenchmarkResult.select(
            BenchmarkResult.persona_uuid_id.alias("persona_uuid"),
            BenchmarkResult.case_id,
            Model.name.alias("model_name"),
            BenchmarkResult.rating,
            BenchmarkResult.scale_order,
            DatasetPersona.dataset_id.alias("dataset_id"),
            Persona.age,
            Persona.gender,
            Persona.education,
            Persona.occupation,
            Persona.marriage_status,
            Persona.migration_status,
            Persona.religion,
            Persona.sexuality,
            Persona.origin_id,
            Country.region.alias("origin_region"),
            Country.subregion.alias("origin_subregion"),
            Trait.category.alias("trait_category"),
            Trait.valence.alias("trait_valence"),
        )
        .join(Trait, pw.JOIN.LEFT_OUTER, on=(BenchmarkResult.case_id == Trait.id))
        .switch(BenchmarkResult)
        .join(Persona, on=(BenchmarkResult.persona_uuid_id == Persona.uuid))
        .join(Country, pw.JOIN.LEFT_OUTER, on=(Persona.origin_id == Country.id))
        .join(
            BenchmarkRun,
            pw.JOIN.LEFT_OUTER,
            on=(BenchmarkResult.benchmark_run_id == BenchmarkRun.id),
        )
        .join(Model, pw.JOIN.LEFT_OUTER, on=(BenchmarkRun.model_id == Model.id))
        .join(
            DatasetPersona,
            pw.JOIN.LEFT_OUTER,
            on=(DatasetPersona.persona_id == Persona.uuid),
        )
    )
    if cfg.dataset_ids:
        # Filter to results where persona is member of given datasets
        q = q.where(DatasetPersona.dataset_id.in_(list(map(int, cfg.dataset_ids))))
    if cfg.model_names:
        q = q.where(Model.name.in_(list(cfg.model_names)))
    trait_filters = cfg.trait_ids or cfg.case_ids
    if trait_filters:
        q = q.where(BenchmarkResult.case_id.in_(list(trait_filters)))
    if cfg.run_ids:
        q = q.where(BenchmarkResult.benchmark_run_id.in_(list(map(int, cfg.run_ids))))
    if cfg.include_rationale is not None:
        q = q.where(BenchmarkRun.include_rationale == bool(cfg.include_rationale))

    with db.atomic():
        rows = list(q.dicts())
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["dataset_id"] = df["dataset_id"].astype(int)

    if "run_id" in df.columns:
        try:
            df["run_id"] = pd.to_numeric(df["run_id"], errors="coerce").astype("Int64")
        except Exception:
            pass
    # ensure rating numeric and normalise if reversed
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    if "scale_order" in df.columns:
        df["rating_raw"] = df["rating"]

        # map: if 'rev' then 6 - rating, else keep
        def _norm(row):
            try:
                if str(row.get("scale_order") or "in") == "rev" and pd.notna(
                    row.get("rating")
                ):
                    return (
                        6 - int(row["rating"])
                        if row["rating"] == row["rating"]
                        else row["rating"]
                    )
            except Exception:
                pass
            return row.get("rating")

        df["rating"] = df.apply(_norm, axis=1)
    if "trait_valence" in df.columns:
        df["trait_valence"] = pd.to_numeric(df["trait_valence"], errors="coerce")
        df["rating_pre_valence"] = df["rating"]

        def _apply_valence(row):
            rat = row.get("rating")
            val = row.get("trait_valence")
            if pd.isna(rat) or pd.isna(val):
                return rat
            try:
                v = int(val)
            except Exception:
                return rat
            if v < 0:
                return 6 - float(rat)
            return rat

        df["rating_valence_aligned"] = df.apply(_apply_valence, axis=1)
        df["rating"] = df["rating_valence_aligned"]
        df["trait_valence_label"] = df["trait_valence"].map(
            {-1: "negativ", 0: "neutral", 1: "positiv"}
        )
    return df


def _ci95(series: pd.Series) -> tuple[float, float]:
    s = pd.to_numeric(series, errors="coerce").dropna()
    n = s.count()
    if n == 0:
        return (float("nan"), float("nan"))
    mean = float(s.mean())
    std = float(s.std(ddof=1)) if n > 1 else 0.0
    import math

    half = 1.96 * std / math.sqrt(n) if n > 1 else 0.0
    return (mean - half, mean + half)


def _kish_effective_n(w: pd.Series) -> float:
    sw = float(w.sum())
    sw2 = float((w**2).sum())
    return (sw * sw) / sw2 if sw2 > 0 else 0.0


def summarise_rating_by(
    df: pd.DataFrame,
    column: str,
    *,
    weight_col: str | None = None,
) -> pd.DataFrame:
    """Return mean, count, std, ci95_low/high per category.
    Requires column in df.
    """
    if column not in df.columns:
        raise KeyError(f"Column '{column}' not in dataframe")
    if weight_col and weight_col in df.columns:
        rows: list[dict[str, Any]] = []
        for cat, sub in df.groupby(column, dropna=False):
            y = pd.to_numeric(sub["rating"], errors="coerce")
            w = pd.to_numeric(sub[weight_col], errors="coerce").fillna(0.0)
            msk = y.notna()
            y = y[msk]
            w = w[msk]
            sw = float(w.sum())
            if sw <= 0 or y.empty:
                rows.append(
                    {
                        column: cat,
                        "count": 0.0,
                        "mean": float("nan"),
                        "std": float("nan"),
                        "ci95_low": float("nan"),
                        "ci95_high": float("nan"),
                    }
                )
                continue
            mu = float((w * y).sum() / sw)
            var = float((w * (y - mu) ** 2).sum() / sw)
            n_eff = _kish_effective_n(w)
            se = float(np.sqrt(var / n_eff)) if n_eff > 1 else float("nan")
            rows.append(
                {
                    column: cat,
                    "count": sw,
                    "mean": mu,
                    "std": float(np.sqrt(var)) if var >= 0 else float("nan"),
                    "ci95_low": mu - 1.96 * se if np.isfinite(se) else float("nan"),
                    "ci95_high": mu + 1.96 * se if np.isfinite(se) else float("nan"),
                }
            )
        out = pd.DataFrame(rows)
    else:
        g = df.groupby(column, dropna=False)["rating"]
        out = g.agg(["count", "mean", "std"]).reset_index()
        # CI bounds
        ci_bounds = g.apply(_ci95)
        out["ci95_low"] = [b[0] for b in ci_bounds]
        out["ci95_high"] = [b[1] for b in ci_bounds]
    out = out.sort_values("mean", ascending=False)
    return out


def plot_rating_distribution(
    df: pd.DataFrame, *, likert_min: int | None = None, likert_max: int | None = None
) -> plt.Axes:
    """Discrete bar chart for integer Likert ratings with equal spacing."""
    set_default_theme()
    s = pd.to_numeric(df["rating"], errors="coerce").dropna().astype(int)
    if likert_min is None:
        likert_min = int(s.min()) if not s.empty else 1
    if likert_max is None:
        likert_max = int(s.max()) if not s.empty else 7
    categories = list(range(likert_min, likert_max + 1))
    counts = s.value_counts().reindex(categories, fill_value=0).sort_index()
    shares = counts / counts.sum() if counts.sum() > 0 else counts
    ax = sns.barplot(
        x=list(map(str, categories)),
        y=shares.values,
        color=sns.color_palette("colorblind")[0],
    )
    ax.set_xlabel("Rating (Likert)")
    ax.set_ylabel("Anteil")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_title("Rating-Verteilung")
    plt.tight_layout()
    return ax


def plot_rating_distribution_by_genid(
    df: pd.DataFrame, *, likert_min: int | None = None, likert_max: int | None = None
) -> plt.Axes:
    """Grouped bars: rating distribution per dataset_id to compare runs."""
    set_default_theme()
    work = df.copy()
    work["rating"] = pd.to_numeric(work["rating"], errors="coerce").astype("Int64")
    if likert_min is None:
        likert_min = int(work["rating"].min()) if work["rating"].notna().any() else 1
    if likert_max is None:
        likert_max = int(work["rating"].max()) if work["rating"].notna().any() else 7
    cats = list(range(likert_min, likert_max + 1))
    g = (
        work.dropna(subset=["rating"])
        .groupby(["dataset_id", "rating"])
        .size()
        .rename("count")
        .reset_index()
    )
    totals = g.groupby("dataset_id")["count"].sum().rename("total")
    g = g.merge(totals, on="dataset_id")
    g["share"] = g["count"] / g["total"]
    g = g.pivot(index="rating", columns="dataset_id", values="share").reindex(
        index=cats, fill_value=0
    )
    ax = g.plot(kind="bar", figsize=(8, 4))
    ax.set_xlabel("Rating (Likert)")
    ax.set_ylabel("Anteil")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_title("Rating-Verteilung nach dataset_id")
    plt.tight_layout()
    return ax


def plot_category_means(
    df: pd.DataFrame,
    column: str,
    *,
    ax: plt.Axes | None = None,
    figsize: tuple[float, float] = (7, 4),
    top_n: int | None = 10,
    weight_col: str | None = None,
) -> plt.Axes:
    """Bars mit Mean + 95%-CI je Kategorie. Große Domänen werden via Top-N beschnitten."""
    set_default_theme()
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    work = df.copy()
    work[column] = work[column].fillna("Unknown")
    summary = summarise_rating_by(work, column, weight_col=weight_col)
    if top_n and top_n > 0:
        summary = summary.sort_values("count", ascending=False).head(top_n)
        summary = summary.sort_values("mean", ascending=False)
    sns.barplot(
        data=summary,
        y=column,
        x="mean",
        ax=ax,
        orient="h",
        color=sns.color_palette("colorblind")[0],
        errorbar=None,
    )
    # draw CI whiskers manually
    for i, (_, row) in enumerate(summary.iterrows()):
        ax.hlines(i, row["ci95_low"], row["ci95_high"], colors="k", lw=1.2)
        ax.plot([row["mean"]], [i], "o", color="k", ms=3)
    ax.set_xlabel("Durchschnittliches Rating (±95% CI)")
    ax.set_ylabel(column.replace("_", " ").title())
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    plt.tight_layout()
    return ax


def plot_deltas_vs_baseline(
    df: pd.DataFrame,
    column: str,
    *,
    baseline: str | None = None,
    ax: plt.Axes | None = None,
    figsize: tuple[float, float] = (7, 4),
    top_n: int | None = 10,
    weight_col: str | None = None,
) -> plt.Axes:
    """Delta der Mittelwerte je Kategorie relativ zu einer Baseline."""
    set_default_theme()
    work = df.copy()
    work[column] = work[column].fillna("Unknown")
    summary = summarise_rating_by(work, column, weight_col=weight_col)
    # Choose baseline = häufigste Kategorie, falls nicht angegeben
    if baseline is None and not summary.empty:
        baseline = summary.sort_values("count", ascending=False)[column].iloc[0]
    base_mean = (
        float(summary.loc[summary[column] == baseline, "mean"].iloc[0])
        if baseline in summary[column].values
        else float("nan")
    )
    summary = summary.assign(delta=summary["mean"] - base_mean)
    if top_n and top_n > 0:
        summary = summary.sort_values("count", ascending=False).head(top_n)
    summary = summary.sort_values("delta", ascending=True)
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    sns.barplot(
        data=summary,
        y=column,
        x="delta",
        orient="h",
        ax=ax,
        color=sns.color_palette("colorblind")[1],
    )
    ax.axvline(0, color="k", lw=1)
    ax.set_xlabel(f"Delta zum Baseline-Mittel ({baseline})")
    ax.set_ylabel(column.replace("_", " ").title())
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    plt.tight_layout()
    return ax


# ---------- Significance (permutation test) ----------


def permutation_p_value(
    a: pd.Series, b: pd.Series, *, n_perm: int = 2000, random_state: int | None = 42
) -> float:
    """Two-sided permutation test for difference in means."""
    rng = np.random.default_rng(random_state)
    a = pd.to_numeric(a, errors="coerce").dropna().to_numpy()
    b = pd.to_numeric(b, errors="coerce").dropna().to_numpy()
    if a.size == 0 or b.size == 0:
        return float("nan")
    pooled = np.concatenate([a, b])
    observed = abs(a.mean() - b.mean())
    n_a = a.size
    n_total = pooled.size
    n_b = n_total - n_a
    if n_perm <= 0 or n_a == 0 or n_b == 0:
        return float("nan")

    total_sum = float(pooled.sum())
    count = 0
    done = 0
    # Limit batch size to keep memory bounded (~1e6 floats by default)
    max_batch = max(1, int(1_000_000 // max(1, n_total)))
    batch_size = max(1, min(n_perm, max_batch))

    while done < n_perm:
        cur = min(batch_size, n_perm - done)
        keys = rng.random((cur, n_total))
        # Select indices of the first n_a elements in the random permutation
        idx = np.argpartition(keys, n_a - 1, axis=1)[:, :n_a]
        group_a = np.take(pooled, idx)
        sum_a = group_a.sum(axis=1)
        mean_a = sum_a / n_a
        mean_b = (total_sum - sum_a) / n_b
        diffs = np.abs(mean_a - mean_b)
        count += int(np.count_nonzero(diffs >= observed))
        done += cur
    return (count + 1) / (n_perm + 1)


def deltas_with_significance(
    df: pd.DataFrame,
    column: str,
    *,
    baseline: str | None = None,
    n_perm: int = 2000,
    alpha: float = 0.05,
    weight_col: str | None = None,
) -> pd.DataFrame:
    work = df.copy()
    work[column] = work[column].fillna("Unknown")
    summary = summarise_rating_by(work, column, weight_col=weight_col)
    if baseline is None and not summary.empty:
        baseline = summary.sort_values("count", ascending=False)[column].iloc[0]
    base_values = work.loc[work[column] == baseline, "rating"]
    rows = []
    for _, r in summary.iterrows():
        cat = r[column]
        values = work.loc[work[column] == cat, "rating"]
        p = permutation_p_value(base_values, values, n_perm=n_perm)
        rows.append(
            {
                column: cat,
                "mean": float(r["mean"]),
                "count": float(r["count"]),
                "delta": float(r["mean"] - base_values.mean()),
                "p_value": float(p),
                "significant": bool(p < alpha),
                "baseline": baseline,
            }
        )
    out = pd.DataFrame(rows).sort_values("delta", ascending=True)
    return out


def build_deltas_payload(
    df: pd.DataFrame,
    column: str,
    *,
    baseline: str | None = None,
    n_perm: int = 2000,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """
    Compute delta table (including p/q-values, Cliff's δ, and CI metadata) for one attribute.
    Returns a dict compatible with the /runs/{id}/deltas payload.
    """
    work = df.copy()
    work[column] = work[column].fillna("Unknown").astype(str)
    summary = summarise_rating_by(work, column)
    if summary.empty:
        return {"rows": [], "baseline": None, "n": int(len(df))}

    if baseline is None or baseline not in summary[column].astype(str).values:
        baseline = str(summary.sort_values("count", ascending=False)[column].iloc[0])
    base_stats = summary.loc[summary[column] == baseline]
    if base_stats.empty:
        baseline = str(summary.iloc[0][column])
        base_stats = summary.iloc[[0]]
    base_vals = pd.to_numeric(
        work.loc[work[column] == baseline, "rating"], errors="coerce"
    ).dropna()
    mean_base = (
        float(base_stats["mean"].iloc[0])
        if not base_stats.empty
        else float(base_vals.mean())
    )
    n_base = (
        int(round(float(base_stats["count"].iloc[0])))
        if not base_stats.empty
        else int(base_vals.shape[0])
    )
    sd_base = (
        float(base_stats["std"].iloc[0])
        if not base_stats.empty
        else float(base_vals.std(ddof=1))
    )

    p_values: list[float] = []
    rows_raw: list[dict[str, Any]] = []
    cliffs_values: list[float] = []

    for _, row in summary.iterrows():
        cat = str(row[column])
        vals = pd.to_numeric(
            work.loc[work[column] == cat, "rating"], errors="coerce"
        ).dropna()
        p = permutation_p_value(base_vals, vals, n_perm=n_perm)
        _, _, cliffs = mann_whitney_cliffs(base_vals, vals)
        p_values.append(float(p))
        cliffs_values.append(float(cliffs))
        rows_raw.append(
            {
                "category": cat,
                "count": float(row["count"]),
                "mean": float(row["mean"]),
                "delta": float(row["mean"] - mean_base),
                "p_value": float(p),
                "significant": bool(p < alpha),
            }
        )

    try:
        q_values = benjamini_hochberg(p_values)
    except Exception:
        q_values = [float("nan")] * len(rows_raw)

    rows: list[dict[str, Any]] = []
    for raw, q_val, cliffs in zip(rows_raw, q_values, cliffs_values):
        n_cat = int(round(raw["count"]))
        sd_cat = summary.loc[summary[column] == raw["category"], "std"]
        sd_c = float(sd_cat.iloc[0]) if not sd_cat.empty else float("nan")
        delta = raw["delta"]
        if n_base > 1 and n_cat > 1 and np.isfinite(sd_base) and np.isfinite(sd_c):
            se = float(np.sqrt((sd_base**2) / n_base + (sd_c**2) / n_cat))
            ci_low = float(delta - 1.96 * se)
            ci_high = float(delta + 1.96 * se)
        else:
            se = float("nan")
            ci_low = None
            ci_high = None
        rows.append(
            {
                "category": raw["category"],
                "count": int(round(raw["count"])),
                "mean": raw["mean"],
                "delta": delta if delta == delta else None,
                "p_value": raw["p_value"] if raw["p_value"] == raw["p_value"] else None,
                "q_value": float(q_val) if q_val == q_val else None,
                "cliffs_delta": float(cliffs) if cliffs == cliffs else None,
                "significant": raw["significant"],
                "baseline": baseline,
                "n_base": n_base,
                "sd_base": sd_base if sd_base == sd_base else None,
                "mean_base": mean_base if mean_base == mean_base else None,
                "n_cat": n_cat,
                "sd_cat": sd_c if sd_c == sd_c else None,
                "mean_cat": raw["mean"],
                "se_delta": se if se == se else None,
                "ci_low": ci_low,
                "ci_high": ci_high,
            }
        )

    rows.sort(
        key=lambda r: (
            r["delta"] if r["delta"] == r["delta"] else float("inf"),
            r["category"],
        )
    )

    return {"rows": rows, "baseline": baseline, "n": int(len(df))}


def plot_deltas_with_significance(
    df: pd.DataFrame,
    column: str,
    *,
    baseline: str | None = None,
    n_perm: int = 2000,
    alpha: float = 0.05,
    ax: plt.Axes | None = None,
    figsize: tuple[float, float] = (7, 4),
    weight_col: str | None = None,
) -> plt.Axes:
    set_default_theme()
    table = deltas_with_significance(
        df, column, baseline=baseline, n_perm=n_perm, alpha=alpha, weight_col=weight_col
    )
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    sns.barplot(
        data=table,
        y=column,
        x="delta",
        orient="h",
        ax=ax,
        hue="significant",
        dodge=False,
        palette={
            True: sns.color_palette("colorblind")[2],
            False: sns.color_palette("colorblind")[0],
        },
    )
    ax.axvline(0, color="k", lw=1)
    ax.set_xlabel(f"Delta zum Baseline-Mittel ({table['baseline'].iloc[0]})")
    ax.set_ylabel(column.replace("_", " ").title())
    ax.legend(title="Signifikant (p<%.2f)" % alpha, loc="lower right")
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    plt.tight_layout()
    return ax


def per_question_fixed_effects(
    df: pd.DataFrame, column: str, *, baseline: str | None = None
) -> pd.DataFrame:
    work = df.copy()
    work[column] = work[column].fillna("Unknown")
    if baseline is None:
        s = work.groupby(column)["rating"].size().sort_values(ascending=False)
        baseline = s.index[0]
    rows = []
    for q, sub in work.groupby("case_id"):
        g = (
            sub.groupby(column)["rating"]
            .agg(["count", "mean", "std"])
            .rename(columns={"count": "n"})
        )
        if baseline not in g.index:
            continue
        base = g.loc[baseline]
        for cat, r in g.iterrows():
            if cat == baseline:
                continue
            n_b = int(base["n"])
            n_c = int(r["n"])
            if n_b < 2 or n_c < 2:
                continue
            delta = float(r["mean"] - base["mean"])
            var_b = float(base["std"] ** 2) if not pd.isna(base["std"]) else 0.0
            var_c = float(r["std"] ** 2) if not pd.isna(r["std"]) else 0.0
            se = (
                float(np.sqrt(var_b / n_b + var_c / n_c))
                if (n_b > 1 and n_c > 1)
                else float("nan")
            )
            ci_low = delta - 1.96 * se if not pd.isna(se) else float("nan")
            ci_high = delta + 1.96 * se if not pd.isna(se) else float("nan")
            rows.append(
                {
                    "case_id": q,
                    column: cat,
                    "baseline": baseline,
                    "n_cat": n_c,
                    "n_base": n_b,
                    "mean_cat": float(r["mean"]),
                    "mean_base": float(base["mean"]),
                    "delta": delta,
                    "se_delta": se,
                    "ci95_low": ci_low,
                    "ci95_high": ci_high,
                }
            )
    return pd.DataFrame(rows)


def plot_fixed_effects_forest(
    per_q: pd.DataFrame,
    column: str,
    *,
    target_category: str | None = None,
    min_n: int = 2,
    question_labels: dict[str, str] | None = None,
    color_by_question: bool = True,
    ax=None,
    figsize=(7, 8),
):
    set_default_theme()
    import matplotlib.pyplot as plt
    import seaborn as sns

    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    if per_q.empty:
        return ax
    # filter by counts and optional target category
    mask = (per_q["n_base"] >= min_n) & (per_q["n_cat"] >= min_n)
    if target_category is not None:
        mask &= per_q[column].astype(str) == str(target_category)
    per_q = per_q.loc[mask].copy()
    if per_q.empty:
        return ax
    per_q = per_q.sort_values("delta").reset_index(drop=True)
    y = np.arange(len(per_q))
    # colors per question
    colors = None
    if color_by_question:
        qids = per_q["case_id"].astype(str).unique().tolist()
        pal = sns.color_palette("tab20", n_colors=max(3, len(qids)))
        colors = {qid: pal[i % len(pal)] for i, qid in enumerate(qids)}
    for i, r in per_q.iterrows():
        col = colors.get(str(r["case_id"])) if colors else "0.35"
        ax.hlines(i, r["ci95_low"], r["ci95_high"], color=col, lw=1.2)
        ax.plot([r["delta"]], [i], "o", color=col, ms=4)
    ax.axvline(0, color="k", lw=1)
    ax.set_yticks(y)
    if target_category is None:

        def _lab(r):
            q = str(r["case_id"])
            adj = question_labels.get(q) if question_labels else None
            left = f"{adj}" if adj else q
            return f"{left} · {r[column]}"

        labels = per_q.apply(_lab, axis=1)
        ax.set_ylabel("Question UUID · Kategorie")
    else:
        if question_labels:
            labels = (
                per_q["case_id"]
                .astype(str)
                .map(lambda q: f"{question_labels.get(q, q)}")
            )
        else:
            labels = per_q["case_id"].astype(str)
        ax.set_ylabel("Question UUID")
    ax.set_yticklabels(labels)
    ax.set_xlabel(f"Delta vs Baseline ({per_q['baseline'].iloc[0]})")
    if per_q["se_delta"].notna().any():
        w = 1.0 / (per_q["se_delta"] ** 2).replace([np.inf, 0], np.nan)
        w = w.fillna(0)
        if w.sum() > 0:
            mu = float(np.nansum(w * per_q["delta"]) / np.nansum(w))
            se_mu = (
                float(np.sqrt(1.0 / np.nansum(w))) if np.nansum(w) > 0 else float("nan")
            )
            ax.axvline(
                mu, color=sns.color_palette("colorblind")[2], lw=2, linestyle="--"
            )
            if not pd.isna(se_mu):
                ax.axvspan(
                    mu - 1.96 * se_mu,
                    mu + 1.96 * se_mu,
                    color=sns.color_palette("colorblind")[2],
                    alpha=0.15,
                )
    plt.tight_layout()
    return ax


def benjamini_hochberg(pvals):
    p = np.array([x if np.isfinite(x) else 1.0 for x in pvals], dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranks = np.empty_like(order)
    ranks[order] = np.arange(1, n + 1)
    q = p * n / ranks
    q_sorted = np.minimum.accumulate(q[order][::-1])[::-1]
    out = np.empty_like(q)
    out[order] = np.clip(q_sorted, 0, 1)
    return out.tolist()


def mann_whitney_cliffs(a: pd.Series, b: pd.Series):
    x = pd.to_numeric(a, errors="coerce").dropna().to_numpy()
    y = pd.to_numeric(b, errors="coerce").dropna().to_numpy()
    n1, n2 = len(x), len(y)
    if n1 == 0 or n2 == 0:
        return (np.nan, np.nan, np.nan)
    xy = np.concatenate([x, y])
    ranks = pd.Series(xy).rank(method="average").to_numpy()
    R1 = ranks[:n1].sum()
    U1 = R1 - n1 * (n1 + 1) / 2
    _, counts = np.unique(xy, return_counts=True)
    tie_term = (counts**3 - counts).sum()
    N = n1 + n2
    if N < 2:
        return (float(U1), 1.0, 0.0)
    T = tie_term / (N * (N - 1))
    varU = n1 * n2 * ((N + 1) - T) / 12.0
    if not np.isfinite(varU) or varU <= 0:
        p = 1.0
        cliffs = 2 * U1 / (n1 * n2) - 1
        return (float(U1), float(p), float(cliffs))
    z = (U1 - n1 * n2 / 2.0) / np.sqrt(varU)
    p = 2.0 * (1.0 - 0.5 * (1.0 + erf(abs(z) / sqrt(2.0))))
    cliffs = 2 * U1 / (n1 * n2) - 1
    return (float(U1), float(p), float(cliffs))


# ---------- Report helpers ----------


def export_benchmark_report(
    df: pd.DataFrame,
    output_dir: Path,
    *,
    title: str = "Benchmark Report",
    top_n: int = 10,
    images_dir: Path | None = None,
    significance_tables: dict[str, pd.DataFrame] | None = None,
    method_meta: dict[str, Any] | None = None,
) -> Path:
    """Write a compact Markdown with overall and per-category stats."""
    output_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    # Context block
    if method_meta:
        lines.append("## Context")
        ds = method_meta.get("dataset_ids") or method_meta.get("datasets")
        rat = method_meta.get("rationale")
        models = method_meta.get("models")
        traits = method_meta.get("traits")
        if ds:
            lines.append(f"- Datasets: {ds}")
        if models:
            lines.append(f"- Models: {models}")
        if rat is not None:
            lines.append(f"- Rationale: {rat}")
        if traits:
            lines.append(f"- Traits: {traits}")
        lines.append("")
    total = len(df)
    lines.append(f"N Ergebnisse: **{total}**")
    if "rating" in df:
        s = pd.to_numeric(df["rating"], errors="coerce").dropna()
        if not s.empty:
            lines.append(
                f"Mittel: {s.mean():.2f}  |  SD: {s.std(ddof=1):.2f}  |  Median: {s.median():.2f}"
            )
    lines.append("")
    cat_cols = [
        "gender",
        "origin_region",
        "religion",
        "migration_status",
        "sexuality",
        "marriage_status",
        "education",
        "occupation",
    ]
    # Embed figures if provided
    import os

    if images_dir is not None:

        def _rel(name: str) -> str | None:
            p = images_dir / name
            return (
                os.path.relpath(p, output_dir).replace(os.sep, "/")
                if p.exists()
                else None
            )

        lines.append("## Abbildungen")
        img = _rel("rating_distribution.png")
        if img:
            lines.append(f"![Rating-Verteilung]({img})")
        img = _rel("rating_distribution_by_genid.png")
        if img:
            lines.append(f"![Rating-Verteilung nach dataset_id]({img})")
        lines.append("")
    for col in cat_cols:
        if col not in df.columns:
            continue
        lines.append(f"## {col.replace('_',' ').title()}")
        s = summarise_rating_by(df, col)
        s = s.sort_values("count", ascending=False).head(top_n)
        for _, r in s.iterrows():
            lines.append(f"- {r[col]}: mean={r['mean']:.2f} (n={int(r['count'])})")
        if images_dir is not None:
            means_img = _rel(f"means_{col}.png")
            delta_img = _rel(f"delta_{col}.png")
            forest_img = _rel(f"forest_{col}.png")
            if means_img:
                lines.append("")
                lines.append(f"![Mittelwerte - {col}]({means_img})")
            if delta_img:
                lines.append("")
                lines.append(f"![Delta vs. Baseline - {col}]({delta_img})")
            if forest_img:
                lines.append("")
                lines.append(f"![Per-Question Forest - {col}]({forest_img})")
        lines.append("")
    # Optional: append significance tables at the end (grouped by attribute)
    if significance_tables:
        lines.append("## Signifikanz-Tabellen (p, q, Cliff_delta)")
        for col, tbl in significance_tables.items():
            if col not in df.columns or tbl is None or tbl.empty:
                continue
            lines.append(f"### {col.replace('_',' ').title()}")
            t = tbl.copy()
            t = t.sort_values(["significant", "count"], ascending=[False, False]).head(
                top_n
            )
            lines.append(
                "| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |"
            )
            lines.append("|---|---:|---:|---:|---:|---:|---:|:--:|")
            for _, r in t.iterrows():
                qv = r.get("q_value", float("nan"))
                cd = r.get("cliffs_delta", float("nan"))
                sigmark = "yes" if bool(r.get("significant", False)) else ""
                lines.append(
                    f"| {r[col]} | {int(round(r['count']))} | {r['mean']:.2f} | {r['delta']:.2f} | {r['p_value']:.3f} | {qv:.3f} | {cd:.2f} | {sigmark} |"
                )
            lines.append("")
    path = output_dir / "benchmark_report.md"
    path.write_text("\n".join(lines))
    return path


# ---------- Weighting helpers ----------


def compute_poststrat_weights(
    df: pd.DataFrame,
    by: Sequence[str],
    *,
    target: pd.DataFrame | None = None,
    ref_filter: pd.Series | None = None,
    weight_col: str = "weight",
) -> pd.DataFrame:
    if not by:
        out = df.copy()
        out[weight_col] = 1.0
        return out
    work = df.copy()
    cur = work.groupby(list(by), dropna=False).size().rename("count").reset_index()
    cur["share"] = cur["count"] / cur["count"].sum()
    if target is not None:
        ref = target.copy()
        if "share" not in ref.columns:
            raise ValueError("target must include a 'share' column")
        ref = ref[list(by) + ["share"]].rename(columns={"share": "ref_share"})
    else:
        ref_df = work if ref_filter is None else work.loc[ref_filter]
        ref = (
            ref_df.groupby(list(by), dropna=False)
            .size()
            .rename("ref_count")
            .reset_index()
        )
        ref["ref_share"] = ref["ref_count"] / ref["ref_count"].sum()
    merged = cur.merge(ref, on=list(by), how="left")
    merged["ref_share"] = merged["ref_share"].fillna(0.0)
    merged["share"] = merged["share"].fillna(0.0)

    def _w(row):
        return (row["ref_share"] / row["share"]) if row["share"] > 0 else 0.0

    merged["w"] = merged.apply(_w, axis=1)
    out = work.merge(merged[list(by) + ["w"]], on=list(by), how="left")
    out["w"] = out["w"].fillna(0.0)
    m = float(out["w"].mean()) if out["w"].mean() > 0 else 1.0
    out[weight_col] = out["w"] / m
    out = out.drop(columns=["w"])
    return out
