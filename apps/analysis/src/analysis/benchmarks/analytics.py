from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence
from pathlib import Path

import pandas as pd
import peewee as pw
import numpy as np
from math import erf, sqrt

from analysis.persona.analytics import set_default_theme
from shared.storage.db import init_database, get_db, db_proxy, create_tables
from shared.storage.models import BenchmarkResult, Persona, Country

try:
    import seaborn as sns
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Install seaborn and matplotlib to use plotting helpers: pip install seaborn matplotlib"
    ) from exc


@dataclass(slots=True)
class BenchQuery:
    gen_ids: Sequence[int] | None = None
    model_names: Sequence[str] | None = None
    question_uuids: Sequence[str] | None = None
    db_url: str | None = None


def _ensure_db(db_url: str | None) -> None:
    if getattr(db_proxy, "obj", None) is None or db_url:
        init_database(db_url=db_url)
    create_tables()


def load_benchmark_dataframe(cfg: BenchQuery) -> pd.DataFrame:
    """Load benchmark results joined with persona demographics.

    Columns: gen_id, persona_uuid, question_uuid, model_name, rating, age, gender,
             origin_region, religion, sexuality, marriage_status, education, occupation
    """
    _ensure_db(cfg.db_url)
    db = get_db()

    q = (
        BenchmarkResult.select(
            BenchmarkResult.persona_uuid.alias("persona_uuid"),
            BenchmarkResult.question_uuid,
            BenchmarkResult.model_name,
            BenchmarkResult.rating,
            Persona.gen_id.alias("gen_id"),
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
        )
        .join(Persona, on=(BenchmarkResult.persona_uuid == Persona.uuid))
        .join(Country, pw.JOIN.LEFT_OUTER, on=(Persona.origin_id == Country.id))
        
    )
    if cfg.gen_ids:
        q = q.where(Persona.gen_id.in_(list(cfg.gen_ids)))
    if cfg.model_names:
        q = q.where(BenchmarkResult.model_name.in_(list(cfg.model_names)))
    if cfg.question_uuids:
        q = q.where(BenchmarkResult.question_uuid.in_(list(cfg.question_uuids)))

    with db.atomic():
        rows = list(q.dicts())
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["gen_id"] = df["gen_id"].astype(int)
    # ensure rating numeric
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
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
    sw2 = float((w ** 2).sum())
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
                rows.append({column: cat, "count": 0.0, "mean": float("nan"), "std": float("nan"), "ci95_low": float("nan"), "ci95_high": float("nan")})
                continue
            mu = float((w * y).sum() / sw)
            var = float((w * (y - mu) ** 2).sum() / sw)
            n_eff = _kish_effective_n(w)
            se = float(np.sqrt(var / n_eff)) if n_eff > 1 else float("nan")
            rows.append({
                column: cat,
                "count": sw,
                "mean": mu,
                "std": float(np.sqrt(var)) if var >= 0 else float("nan"),
                "ci95_low": mu - 1.96 * se if np.isfinite(se) else float("nan"),
                "ci95_high": mu + 1.96 * se if np.isfinite(se) else float("nan"),
            })
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


def plot_rating_distribution(df: pd.DataFrame, *, likert_min: int | None = None, likert_max: int | None = None) -> plt.Axes:
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
    ax = sns.barplot(x=list(map(str, categories)), y=shares.values, color=sns.color_palette("colorblind")[0])
    ax.set_xlabel("Rating (Likert)")
    ax.set_ylabel("Anteil")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_title("Rating-Verteilung")
    plt.tight_layout()
    return ax


def plot_rating_distribution_by_genid(df: pd.DataFrame, *, likert_min: int | None = None, likert_max: int | None = None) -> plt.Axes:
    """Grouped bars: rating distribution per gen_id to compare runs."""
    set_default_theme()
    work = df.copy()
    work["rating"] = pd.to_numeric(work["rating"], errors="coerce").astype("Int64")
    if likert_min is None:
        likert_min = int(work["rating"].min()) if work["rating"].notna().any() else 1
    if likert_max is None:
        likert_max = int(work["rating"].max()) if work["rating"].notna().any() else 7
    cats = list(range(likert_min, likert_max + 1))
    g = (work.dropna(subset=["rating"]).groupby(["gen_id", "rating"]).size().rename("count").reset_index())
    totals = g.groupby("gen_id")["count"].sum().rename("total")
    g = g.merge(totals, on="gen_id")
    g["share"] = g["count"] / g["total"]
    g = g.pivot(index="rating", columns="gen_id", values="share").reindex(index=cats, fill_value=0)
    ax = g.plot(kind="bar", figsize=(8, 4))
    ax.set_xlabel("Rating (Likert)")
    ax.set_ylabel("Anteil")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_title("Rating-Verteilung nach gen_id")
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
    base_mean = float(summary.loc[summary[column] == baseline, "mean"].iloc[0]) if baseline in summary[column].values else float('nan')
    summary = summary.assign(delta=summary["mean"] - base_mean)
    if top_n and top_n > 0:
        summary = summary.sort_values("count", ascending=False).head(top_n)
    summary = summary.sort_values("delta", ascending=True)
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    sns.barplot(data=summary, y=column, x="delta", orient="h", ax=ax, color=sns.color_palette("colorblind")[1])
    ax.axvline(0, color="k", lw=1)
    ax.set_xlabel(f"Delta zum Baseline-Mittel ({baseline})")
    ax.set_ylabel(column.replace("_", " ").title())
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    plt.tight_layout()
    return ax



# ---------- Significance (permutation test) ----------

def permutation_p_value(a: pd.Series, b: pd.Series, *, n_perm: int = 2000, random_state: int | None = 42) -> float:
    """Two-sided permutation test for difference in means."""
    import numpy as np
    rng = np.random.default_rng(random_state)
    a = pd.to_numeric(a, errors="coerce").dropna().to_numpy()
    b = pd.to_numeric(b, errors="coerce").dropna().to_numpy()
    if a.size == 0 or b.size == 0:
        return float("nan")
    observed = abs(a.mean() - b.mean())
    pooled = np.concatenate([a, b])
    n_a = a.size
    count = 0
    for _ in range(n_perm):
        rng.shuffle(pooled)
        diff = abs(pooled[:n_a].mean() - pooled[n_a:].mean())
        if diff >= observed:
            count += 1
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
        rows.append({
            column: cat,
            "mean": float(r["mean"]),
            "count": float(r["count"]),
            "delta": float(r["mean"] - base_values.mean()),
            "p_value": float(p),
            "significant": bool(p < alpha),
            "baseline": baseline,
        })
    out = pd.DataFrame(rows).sort_values("delta", ascending=True)
    return out


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
    table = deltas_with_significance(df, column, baseline=baseline, n_perm=n_perm, alpha=alpha, weight_col=weight_col)
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    sns.barplot(data=table, y=column, x="delta", orient="h", ax=ax, hue="significant", dodge=False, palette={True: sns.color_palette("colorblind")[2], False: sns.color_palette("colorblind")[0]})
    ax.axvline(0, color="k", lw=1)
    ax.set_xlabel(f"Delta zum Baseline-Mittel ({table['baseline'].iloc[0]})")
    ax.set_ylabel(column.replace("_", " ").title())
    ax.legend(title="Signifikant (p<%.2f)" % alpha, loc="lower right")
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    plt.tight_layout()
    return ax



def per_question_fixed_effects(df: pd.DataFrame, column: str, *, baseline: str | None = None) -> pd.DataFrame:
    work = df.copy()
    work[column] = work[column].fillna("Unknown")
    if baseline is None:
        s = work.groupby(column)["rating"].size().sort_values(ascending=False)
        baseline = s.index[0]
    rows = []
    for q, sub in work.groupby("question_uuid"):
        g = sub.groupby(column)["rating"].agg(["count","mean","std"]).rename(columns={"count":"n"})
        if baseline not in g.index:
            continue
        base = g.loc[baseline]
        for cat, r in g.iterrows():
            if cat == baseline:
                continue
            n_b = int(base["n"]); n_c = int(r["n"])
            if n_b < 2 or n_c < 2:
                continue
            delta = float(r["mean"] - base["mean"])
            var_b = float(base["std"]**2) if not pd.isna(base["std"]) else 0.0
            var_c = float(r["std"]**2) if not pd.isna(r["std"]) else 0.0
            se = float(np.sqrt(var_b/n_b + var_c/n_c)) if (n_b>1 and n_c>1) else float('nan')
            ci_low = delta - 1.96*se if not pd.isna(se) else float('nan')
            ci_high = delta + 1.96*se if not pd.isna(se) else float('nan')
            rows.append({
                "question_uuid": q,
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
            })
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
    colors=None
    if color_by_question:
        qids = per_q["question_uuid"].astype(str).unique().tolist()
        pal = sns.color_palette("tab20", n_colors=max(3, len(qids)))
        colors = {qid: pal[i % len(pal)] for i, qid in enumerate(qids)}
    for i, r in per_q.iterrows():
        col = colors.get(str(r["question_uuid"])) if colors else "0.35"
        ax.hlines(i, r["ci95_low"], r["ci95_high"], color=col, lw=1.2)
        ax.plot([r["delta"]], [i], "o", color=col, ms=4)
    ax.axvline(0, color="k", lw=1)
    ax.set_yticks(y)
    if target_category is None:
        def _lab(r):
            q=str(r['question_uuid'])
            adj = question_labels.get(q) if question_labels else None
            left = f"{adj}" if adj else q
            return f"{left} · {r[column]}"
        labels = per_q.apply(_lab, axis=1)
        ax.set_ylabel("Question UUID · Kategorie")
    else:
        if question_labels:
            labels = per_q["question_uuid"].astype(str).map(lambda q: f"{question_labels.get(q, q)}")
        else:
            labels = per_q["question_uuid"].astype(str)
        ax.set_ylabel("Question UUID")
    ax.set_yticklabels(labels)
    ax.set_xlabel(f"Delta vs Baseline ({per_q['baseline'].iloc[0]})")
    if per_q["se_delta"].notna().any():
        w = 1.0/(per_q["se_delta"]**2).replace([np.inf, 0], np.nan)
        w = w.fillna(0)
        if w.sum() > 0:
            mu = float(np.nansum(w*per_q["delta"]) / np.nansum(w))
            se_mu = float(np.sqrt(1.0/np.nansum(w))) if np.nansum(w) > 0 else float('nan')
            ax.axvline(mu, color=sns.color_palette("colorblind")[2], lw=2, linestyle="--")
            if not pd.isna(se_mu):
                ax.axvspan(mu-1.96*se_mu, mu+1.96*se_mu, color=sns.color_palette("colorblind")[2], alpha=0.15)
    plt.tight_layout()
    return ax


def benjamini_hochberg(pvals):
    p = np.array([x if np.isfinite(x) else 1.0 for x in pvals], dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranks = np.empty_like(order)
    ranks[order] = np.arange(1, n+1)
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
    U1 = R1 - n1*(n1+1)/2
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
    total = len(df)
    lines.append(f"N Ergebnisse: **{total}**")
    if "rating" in df:
        s = pd.to_numeric(df["rating"], errors="coerce").dropna()
        if not s.empty:
            lines.append(f"Mittel: {s.mean():.2f}  |  SD: {s.std(ddof=1):.2f}  |  Median: {s.median():.2f}")
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
            return os.path.relpath(p, output_dir).replace(os.sep, "/") if p.exists() else None

        lines.append("## Abbildungen")
        img = _rel("rating_distribution.png")
        if img:
            lines.append(f"![Rating-Verteilung]({img})")
        img = _rel("rating_distribution_by_genid.png")
        if img:
            lines.append(f"![Rating-Verteilung nach gen_id]({img})")
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
            t = t.sort_values(["significant", "count"], ascending=[False, False]).head(top_n)
            lines.append("| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |")
            lines.append("|---|---:|---:|---:|---:|---:|---:|:--:|")
            for _, r in t.iterrows():
                qv = r.get("q_value", float("nan"))
                cd = r.get("cliffs_delta", float("nan"))
                sigmark = "yes" if bool(r.get("significant", False)) else ""
                lines.append(f"| {r[col]} | {int(round(r['count']))} | {r['mean']:.2f} | {r['delta']:.2f} | {r['p_value']:.3f} | {qv:.3f} | {cd:.2f} | {sigmark} |")
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
    cur['share'] = cur['count'] / cur['count'].sum()
    if target is not None:
        ref = target.copy()
        if 'share' not in ref.columns:
            raise ValueError("target must include a 'share' column")
        ref = ref[list(by)+['share']].rename(columns={'share':'ref_share'})
    else:
        ref_df = work if ref_filter is None else work.loc[ref_filter]
        ref = ref_df.groupby(list(by), dropna=False).size().rename('ref_count').reset_index()
        ref['ref_share'] = ref['ref_count'] / ref['ref_count'].sum()
    merged = cur.merge(ref, on=list(by), how='left')
    merged['ref_share'] = merged['ref_share'].fillna(0.0)
    merged['share'] = merged['share'].fillna(0.0)
    def _w(row):
        return (row['ref_share']/row['share']) if row['share']>0 else 0.0
    merged['w'] = merged.apply(_w, axis=1)
    out = work.merge(merged[list(by)+['w']], on=list(by), how='left')
    out['w'] = out['w'].fillna(0.0)
    m = float(out['w'].mean()) if out['w'].mean()>0 else 1.0
    out[weight_col] = out['w']/m
    out = out.drop(columns=['w'])
    return out
