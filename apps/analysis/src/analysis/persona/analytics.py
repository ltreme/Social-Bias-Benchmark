from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
import os
from datetime import datetime, date

import pandas as pd
import peewee as pw

from analysis import get_project_root
from shared.storage.db import DEFAULT_SQLITE_PATH, init_database, get_db, db_proxy, create_tables
from shared.storage.models import Country, Persona, PersonaGeneratorRun, DatasetPersona

try:
    import seaborn as sns
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
except ImportError as exc:  # pragma: no cover - optional during import
    raise RuntimeError(
        "Install seaborn and matplotlib to use plotting helpers: pip install seaborn matplotlib"
    ) from exc

# Plotly is optional; functions that need it will check availability
try:  # pragma: no cover - optional dependency
    import plotly.express as px  # type: ignore
except Exception:  # noqa: BLE001
    px = None  # type: ignore


_LAST_DB_URL: str | None = None


@dataclass(slots=True)
class PersonaDataConfig:
    gen_ids: tuple[int, ...]
    db_url: str | None = None

    @classmethod
    def from_iterable(cls, gen_ids: Iterable[int], db_url: str | None = None) -> "PersonaDataConfig":
        return cls(gen_ids=tuple(int(gid) for gid in gen_ids), db_url=db_url)


def _resolve_db_url(db_url: str | None = None) -> str:
    if db_url:
        return db_url

    env_url = os.getenv("DB_URL")
    if env_url:
        return env_url

    project_root = get_project_root()
    default_path = DEFAULT_SQLITE_PATH
    if not default_path.is_absolute():
        default_path = (project_root / default_path).resolve()

    default_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{default_path}"


def _ensure_database(db_url: str | None = None) -> None:
    global _LAST_DB_URL
    resolved_url = _resolve_db_url(db_url)
    if getattr(db_proxy, "obj", None) is None or resolved_url != _LAST_DB_URL:
        init_database(db_url=resolved_url)
        _LAST_DB_URL = resolved_url
    create_tables()


def load_persona_dataframe(config: PersonaDataConfig) -> pd.DataFrame:
    """Return persona rows for the configured gen_ids as a DataFrame."""
    if not config.gen_ids:
        raise ValueError("Provide at least one gen_id")

    _ensure_database(config.db_url)
    db = get_db()

    query = (
        Persona.select(
            Persona.uuid.alias("persona_uuid"),
            Persona.gen_id.alias("gen_id"),
            Persona.age,
            Persona.gender,
            Persona.education,
            Persona.occupation,
            Persona.marriage_status,
            Persona.migration_status,
            Persona.religion,
            Persona.sexuality,
            Persona.created_at,
            Country.country_en.alias("origin_country_en"),
            Country.country_de.alias("origin_country_de"),
            Country.region.alias("origin_region"),
            Country.subregion.alias("origin_subregion"),
        )
        .join(Country, pw.JOIN.LEFT_OUTER)
        .where(Persona.gen_id.in_(config.gen_ids))
    )

    # Peewee requires manual alias for join when not using names.
    # Provide deterministic ordering so repeated runs remain stable.
    query = query.order_by(Persona.gen_id, Persona.created_at)

    with db.atomic():
        rows: list[dict[str, Any]] = list(query.dicts())

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["gen_id"] = df["gen_id"].astype(int)
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    return df


def load_persona_dataframe_for_datasets(dataset_ids: Sequence[int]) -> pd.DataFrame:
    """Return persona rows for given dataset_ids (DatasetPersona memberships).

    Columns mirror load_persona_dataframe but replace gen_id with dataset_id.
    """
    if not dataset_ids:
        raise ValueError("Provide at least one dataset_id")
    _ensure_database()
    db = get_db()
    q = (
        Persona.select(
            DatasetPersona.dataset.alias("dataset_id"),
            Persona.uuid.alias("persona_uuid"),
            Persona.age,
            Persona.gender,
            Persona.education,
            Persona.occupation,
            Persona.marriage_status,
            Persona.migration_status,
            Persona.religion,
            Persona.sexuality,
            Persona.created_at,
            Country.country_en.alias("origin_country_en"),
            Country.country_de.alias("origin_country_de"),
            Country.region.alias("origin_region"),
            Country.subregion.alias("origin_subregion"),
        )
        .join(DatasetPersona, on=(DatasetPersona.persona == Persona.uuid))
        .switch(Persona)
        .join(Country, pw.JOIN.LEFT_OUTER)
        .where(DatasetPersona.dataset.in_(list(map(int, dataset_ids))))
        .order_by(DatasetPersona.dataset, Persona.created_at)
    )
    with db.atomic():
        rows = list(q.dicts())
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["dataset_id"] = pd.to_numeric(df["dataset_id"], errors="coerce").astype(int)
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    return df


def summarise_category(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Aggregate counts and shares for a categorical column per gen_id."""
    if column not in df.columns:
        raise KeyError(f"Column '{column}' missing from persona dataframe")
    working = df[["gen_id", column]].copy()
    working[column] = working[column].fillna("Unknown")

    counts = (
        working.groupby(["gen_id", column], dropna=False)
        .size()
        .rename("count")
        .reset_index()
    )

    totals = counts.groupby("gen_id")["count"].sum().rename("total")
    summary = counts.merge(totals, on="gen_id")
    summary["share"] = summary["count"] / summary["total"]
    summary = summary.sort_values(["gen_id", "count"], ascending=[True, False])
    return summary


def summarise_category_grouped(df: pd.DataFrame, group_col: str, column: str) -> pd.DataFrame:
    """Aggregate counts and shares for a categorical column per group_col."""
    if column not in df.columns:
        raise KeyError(f"Column '{column}' missing from dataframe")
    if group_col not in df.columns:
        raise KeyError(f"Group column '{group_col}' missing from dataframe")
    work = df[[group_col, column]].copy()
    work[column] = work[column].fillna("Unknown")
    counts = work.groupby([group_col, column], dropna=False).size().rename("count").reset_index()
    totals = counts.groupby(group_col)["count"].sum().rename("total")
    out = counts.merge(totals, on=group_col)
    out["share"] = out["count"] / out["total"]
    return out.sort_values([group_col, "count"], ascending=[True, False])


def plot_category_100pct_grouped(
    df: pd.DataFrame,
    *,
    group_col: str,
    column: str,
    ax: plt.Axes | None = None,
    figsize: tuple[float, float] = (8, 4),
    top_n: int | None = 10,
) -> plt.Axes:
    """100%-gestapelte Balken: eine Säule pro group_col (e.g., dataset_id)."""
    summary = summarise_category_grouped(df, group_col, column)
    if top_n and top_n > 0:
        # collapse to top-n globally
        top_values = summary.groupby(column)["count"].sum().nlargest(top_n).index.astype(str).to_list()
        s2 = summary.copy()
        s2[column] = s2[column].astype(str)
        s2.loc[~s2[column].isin(top_values), column] = "Other"
        counts = s2.groupby([group_col, column], dropna=False)["count"].sum().reset_index()
        totals = counts.groupby(group_col)["count"].sum().rename("total")
        summary = counts.merge(totals, on=group_col)
        summary["share"] = summary["count"] / summary["total"]
    wide = summary.pivot(index=group_col, columns=column, values="share").fillna(0)
    # order columns by total
    totals = wide.sum(axis=0).sort_values(ascending=False)
    if "Other" in totals.index:
        totals = totals.drop("Other")
        cols = list(totals.index) + ["Other"]
    else:
        cols = list(totals.index)
    wide = wide[cols]
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    wide.plot(kind="bar", stacked=True, ax=ax)
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_xlabel(group_col)
    ax.set_ylabel("Anteil")
    ax.set_title(f"{column.replace('_',' ').title()} – 100% gestapelt")
    leg = ax.legend(title=column.replace("_", " ").title(), bbox_to_anchor=(1.02, 1), loc="upper left", frameon=False, ncol=1)
    if leg and leg.get_title():
        leg.get_title().set_fontsize(10)
    plt.tight_layout()
    return ax


def _apply_top_n(summary: pd.DataFrame, column: str, top_n: int | None) -> pd.DataFrame:
    """Collapse small categories into 'Other' based on global counts (across gen_id)."""
    if top_n is None or top_n <= 0:
        return summary
    # Determine top categories by absolute count over all gen_ids
    top_values: set[str] = (
        summary.groupby(column)["count"].sum().nlargest(top_n).index.astype(str).to_list()
    )
    work = summary.copy()
    work[column] = work[column].astype(str)
    work.loc[~work[column].isin(top_values), column] = "Other"
    # Re-aggregate and recompute shares
    counts = (
        work.groupby(["gen_id", column], dropna=False)["count"].sum().reset_index()
    )
    totals = counts.groupby("gen_id")["count"].sum().rename("total")
    out = counts.merge(totals, on="gen_id")
    out["share"] = out["count"] / out["total"]
    return out


def plot_category_distribution(
    df: pd.DataFrame,
    column: str,
    *,
    ax: plt.Axes | None = None,
    figsize: tuple[float, float] = (8, 4),
    palette: str = "tab10",
    top_n: int | None = None,
) -> plt.Axes:
    """Draw a grouped bar chart for a categorical column."""
    summary = summarise_category(df, column)
    summary = _apply_top_n(summary, column, top_n)
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)

    sns.barplot(
        data=summary,
        x=column,
        y="share",
        hue="gen_id",
        palette=palette,
        ax=ax,
    )
    ax.set_ylabel("Share")
    ax.set_xlabel(column.replace("_", " ").title())
    ax.set_ylim(0, 1)
    ax.legend(title="Gen ID")
    ax.set_title(f"Distribution of {column.replace('_', ' ').title()}")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    plt.tight_layout()
    return ax


def plot_age_distribution(
    df: pd.DataFrame,
    *,
    ax: plt.Axes | None = None,
    bins: int | Iterable[int] = 15,
    figsize: tuple[float, float] = (8, 4),
    palette: str = "tab10",
) -> plt.Axes:
    """Plot age histogram per generation run."""
    if "age" not in df.columns:
        raise KeyError("Column 'age' missing from persona dataframe")
    plot_df = df.dropna(subset=["age"]).copy()
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)

    sns.histplot(
        data=plot_df,
        x="age",
        hue="gen_id",
        element="step",
        stat="probability",
        common_norm=False,
        bins=bins,
        palette=palette,
        ax=ax,
    )
    ax.set_ylabel("Share")
    ax.set_xlabel("Age")
    ax.set_title("Age distribution by gen_id")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    plt.tight_layout()
    return ax


def set_default_theme(*, context: str = "paper", font_scale: float = 0.9, rc_overrides: dict | None = None) -> None:
    """Apply a consistent, publication-ready theme across plots.

    - context: one of 'paper'|'notebook'|'talk'|'poster'
    - font_scale: global font scaling; 0.9 works well for compact figures
    - rc_overrides: optional rcParams to merge
    """
    sns.set_theme(style="whitegrid")
    sns.set_context(context=context, font_scale=font_scale)
    sns.set_palette("colorblind")
    base_rc = {
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "legend.title_fontsize": 10,
    }
    if rc_overrides:
        base_rc.update(rc_overrides)
    plt.rcParams.update(base_rc)


def _palette_for_ids(ids: Sequence[int]) -> list[tuple[float, float, float]]:
    palette = sns.color_palette("colorblind", n_colors=max(3, len(set(ids))))
    return palette


def plot_age_ridgeline(
    df: pd.DataFrame,
    *,
    height: float = 1.3,
    aspect: float = 3.5,
    title_size: int = 10,
) -> sns.FacetGrid:
    """Ridgeline-like KDE small multiples by gen_id.

    Returns the FacetGrid; caller can save via ``g.fig``.
    """
    if "age" not in df.columns:
        raise KeyError("Column 'age' missing from persona dataframe")
    data = df.dropna(subset=["age"]).copy()
    # Order rows by gen_id ascending for consistent stacking
    order = sorted(data["gen_id"].unique())
    g = sns.FacetGrid(
        data,
        row="gen_id",
        row_order=order,
        hue="gen_id",
        sharex=True,
        sharey=False,
        height=height,
        aspect=aspect,
        palette=_palette_for_ids(order),
    )
    g.map(sns.kdeplot, "age", fill=True, alpha=0.7, linewidth=0.9)
    g.map(plt.axhline, y=0, lw=1, clip_on=False, color="0.5")
    g.set_titles(row_template="gen_id = {row_name}", size=title_size)
    for ax in g.axes.flat:
        ax.set_ylabel("")
        ax.grid(axis="x", linestyle="--", alpha=0.3)
    g.fig.subplots_adjust(hspace=0.05)
    g.set_xlabels("Age")
    g.set_ylabels("")
    return g


def plot_category_100pct(
    df: pd.DataFrame,
    column: str,
    *,
    ax: plt.Axes | None = None,
    figsize: tuple[float, float] = (8, 4),
    top_n: int | None = 10,
) -> plt.Axes:
    """100%-gestapelte Balken: eine Säule pro gen_id, Segmente = Kategorien."""
    summary = summarise_category(df, column)
    summary = _apply_top_n(summary, column, top_n)
    wide = summary.pivot(index="gen_id", columns=column, values="share").fillna(0)
    # Order columns by total share across gen_id descending, keep 'Other' at end if present
    totals = wide.sum(axis=0).sort_values(ascending=False)
    if "Other" in totals.index:
        totals = totals.drop("Other")
        cols = list(totals.index) + ["Other"]
    else:
        cols = list(totals.index)
    wide = wide[cols]
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    wide.plot(kind="bar", stacked=True, ax=ax)
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_xlabel("Gen ID", labelpad=6)
    ax.set_ylabel("Anteil")
    ax.set_title(f"{column.replace('_',' ').title()} – 100% gestapelt", fontsize=12)
    leg = ax.legend(
        title=column.replace("_", " ").title(),
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        frameon=False,
        ncol=1,
    )
    if leg and leg.get_title():
        leg.get_title().set_fontsize(10)
    plt.tight_layout()
    return ax


def export_summary_tables(df: pd.DataFrame, output_dir: Path) -> dict[str, Path]:
    """Persist summary CSVs for standard persona dimensions."""
    output_dir.mkdir(parents=True, exist_ok=True)
    columns = [
        "gender",
        "origin_region",
        "religion",
        "sexuality",
        "marriage_status",
        "education",
        "occupation",
    ]
    exported: dict[str, Path] = {}
    for column in columns:
        if column not in df.columns:
            continue
        summary = summarise_category(df, column)
        path = output_dir / f"persona_summary_{column}.csv"
        summary.to_csv(path, index=False)
        exported[column] = path
    return exported


def make_region_choropleth(
    df: pd.DataFrame,
    *,
    animate: bool = True,
) -> "px.choropleth":
    """Interactive categorical choropleth colored by origin_region.

    - Colors each country by its region.
    - If ``animate=True``, adds a slider over ``gen_id``.
    """
    if px is None:  # pragma: no cover
        raise RuntimeError("Install plotly to use choropleth maps: pip install plotly")
    use = df.dropna(subset=["origin_country_en"]).copy()
    agg = (
        use.groupby(["gen_id", "origin_country_en", "origin_region"], dropna=False)
        .size()
        .rename("count")
        .reset_index()
    )
    if animate:
        fig = px.choropleth(
            agg,
            locations="origin_country_en",
            locationmode="country names",
            color="origin_region",
            hover_name="origin_country_en",
            hover_data={"gen_id": True, "count": True, "origin_region": True},
            scope="world",
            projection="natural earth",
            category_orders={"origin_region": sorted(use["origin_region"].dropna().unique())},
            animation_frame="gen_id",
        )
    else:
        # Without animation, collapse across gen_ids and show presence
        present = agg.groupby(["origin_country_en", "origin_region"], dropna=False)[
            "count"
        ].sum().reset_index()
        fig = px.choropleth(
            present,
            locations="origin_country_en",
            locationmode="country names",
            color="origin_region",
            hover_name="origin_country_en",
            hover_data={"origin_region": True, "count": True},
            scope="world",
            projection="natural earth",
            category_orders={"origin_region": sorted(use["origin_region"].dropna().unique())},
        )
    fig.update_layout(legend_title_text="Region")
    return fig


def make_country_share_choropleth(
    df: pd.DataFrame,
    *,
    animate: bool = True,
    normalize: str = "none",  # 'none' | 'per_gen_p95' | 'log1p'
    vmax_percentile: float = 0.95,
    color_scale: str = "Blues",
) -> "px.choropleth":
    """Interactive choropleth shading countries by share of personas per gen_id.

    - normalize='per_gen_p95' rescales shares by the 95th percentile per gen_id
      (clipped to 1). This counters domination durch stark vertretene Laender.
    - normalize='log1p' uses log(1+share) to expand lower values.
    """
    if px is None:  # pragma: no cover
        raise RuntimeError("Install plotly to use choropleth maps: pip install plotly")
    use = df.dropna(subset=["origin_country_en"]).copy()
    counts = (
        use.groupby(["gen_id", "origin_country_en"], dropna=False)
        .size()
        .rename("count")
        .reset_index()
    )
    totals = counts.groupby("gen_id")["count"].sum().rename("total")
    agg = counts.merge(totals, on="gen_id")
    agg["share"] = agg["count"] / agg["total"]

    value_col = "share"
    colorbar_title = "Anteil"
    tickformat = ".0%"  # percentage for raw share
    if normalize == "per_gen_p95":
        # Compute per-gen scaling factor via percentile to reduce outlier dominance
        p = (
            agg.groupby("gen_id")["share"].quantile(vmax_percentile).rename("p95").reset_index()
        )
        agg = agg.merge(p, on="gen_id", how="left")
        agg["share_norm"] = (agg["share"] / agg["p95"]).clip(upper=1.0)
        value_col = "share_norm"
        colorbar_title = f"Rel. Anteil (p{int(vmax_percentile*100)}=1.0)"
        tickformat = ".2f"
    elif normalize == "log1p":
        agg["share_norm"] = (agg["share"].apply(lambda x: float(pd.np.log1p(x))))  # type: ignore[attr-defined]
        value_col = "share_norm"
        colorbar_title = "log(1+Anteil)"
        tickformat = ".2f"

    vmax = max(agg[value_col].max(), 0.001)
    color_kwargs = dict(
        color_continuous_scale=color_scale,
        range_color=(0, vmax),
        labels={value_col: colorbar_title},
    )
    if animate:
        fig = px.choropleth(
            agg,
            locations="origin_country_en",
            locationmode="country names",
            color=value_col,
            hover_name="origin_country_en",
            hover_data={
                "gen_id": True,
                "count": True,
                "share": ":.2%",
                value_col: ":.2f" if normalize != "none" else False,
            },
            scope="world",
            projection="natural earth",
            animation_frame="gen_id",
            **color_kwargs,
        )
    else:
        fig = px.choropleth(
            agg,
            locations="origin_country_en",
            locationmode="country names",
            color=value_col,
            hover_name="origin_country_en",
            hover_data={"gen_id": True, "count": True, "share": ":.2%", value_col: ":.2f"},
            scope="world",
            projection="natural earth",
            **color_kwargs,
        )
    # Clarify colorbar
    fig.update_coloraxes(colorbar_title_text=colorbar_title, colorbar_tickformat=tickformat)
    # Add short explanation in figure metadata
    if normalize == "per_gen_p95":
        fig.update_layout(
            annotations=[
                dict(
                    text=f"Skalierung pro gen_id: 1.0 ≈ {int(vmax_percentile*100)}. Perzentil",
                    x=0.01,
                    y=0.01,
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                    font=dict(size=9, color="#555"),
                )
            ]
        )
    return fig


# -----------------------------
# Reporting helpers (Markdown/JSON)
# -----------------------------

def _non_null_settings(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def load_run_settings(gen_ids: Sequence[int]) -> dict[int, dict[str, Any]]:
    """Fetch PersonaGeneratorRun settings for given gen_ids as a dict."""
    _ensure_database()
    q = (
        PersonaGeneratorRun.select()
        .where(PersonaGeneratorRun.gen_id.in_(list(gen_ids)))
        .order_by(PersonaGeneratorRun.gen_id)
        .dicts()
    )
    result: dict[int, dict[str, Any]] = {}
    for row in q:
        gid = int(row.pop("gen_id"))
        result[gid] = _non_null_settings(row)
    return result


def _age_stats(df: pd.DataFrame) -> dict[str, float]:
    s = pd.to_numeric(df["age"], errors="coerce")
    s = s.dropna()
    if s.empty:
        return {}
    percentiles = s.quantile([0.1, 0.25, 0.5, 0.75, 0.9]).to_dict()
    return {
        "count": float(s.count()),
        "mean": float(s.mean()),
        "std": float(s.std(ddof=1)) if s.count() > 1 else 0.0,
        "min": float(s.min()),
        "p10": float(percentiles.get(0.1, float("nan"))),
        "p25": float(percentiles.get(0.25, float("nan"))),
        "median": float(percentiles.get(0.5, float("nan"))),
        "p75": float(percentiles.get(0.75, float("nan"))),
        "p90": float(percentiles.get(0.9, float("nan"))),
        "max": float(s.max()),
    }


def _category_shares(df: pd.DataFrame, column: str, top_n: int = 10) -> list[dict[str, Any]]:
    summary = summarise_category(df, column)
    summary = _apply_top_n(summary, column, top_n)
    # filter this gen later in per-gen loop
    out = (
        summary[["gen_id", column, "share", "count"]]
        .sort_values(["gen_id", "share"], ascending=[True, False])
        .to_dict(orient="records")
    )
    return out


def generate_persona_reports(
    df: pd.DataFrame,
    output_dir: Path,
    *,
    top_n: int = 10,
) -> list[Path]:
    """Create per-gen_id Markdown and JSON reports with settings + key stats."""
    output_dir.mkdir(parents=True, exist_ok=True)
    gen_ids = sorted(df["gen_id"].astype(int).unique().tolist())
    settings_map = load_run_settings(gen_ids)

    exported: list[Path] = []
    cat_cols = [
        "gender",
        "origin_region",
        "religion",
        "sexuality",
        "marriage_status",
        "education",
        "occupation",
    ]

    for gid in gen_ids:
        sub = df[df["gen_id"] == gid].copy()
        n = int(len(sub))
        missing = {
            col: float(sub[col].isna().mean()) for col in ["age", *cat_cols] if col in sub.columns
        }
        age_stats = _age_stats(sub) if "age" in sub.columns else {}
        cats: dict[str, list[dict[str, Any]]] = {}
        for col in cat_cols:
            if col in sub.columns:
                # filter to this gen and take top_n rows
                s = summarise_category(sub, col).sort_values("share", ascending=False)
                s = _apply_top_n(s, col, top_n)
                s = s.sort_values("share", ascending=False).head(top_n + 1)
                cats[col] = s[[col, "share", "count"]].to_dict(orient="records")

        payload = {
            "gen_id": gid,
            "n_personas": n,
            "settings": settings_map.get(gid, {}),
            "missing_rate": missing,
            "age_stats": age_stats,
            "categories": cats,
        }

        # JSON
        json_path = output_dir / f"persona_report_gen_{gid}.json"
        import json as _json

        json_path.write_text(_json.dumps(payload, indent=2, ensure_ascii=False))
        exported.append(json_path)

        # Markdown
        def _pct(x: float) -> str:
            return f"{x*100:.1f}%"

        md_lines: list[str] = []
        md_lines.append(f"# Persona Report – gen_id {gid}")
        created = settings_map.get(gid, {}).get("created_at")
        if created:
            md_lines.append(f"_Erstellt am_: {created}")
        md_lines.append("")
        md_lines.append(f"Gesamtanzahl Personas: **{n}**")
        md_lines.append("")
        if settings_map.get(gid):
            md_lines.append("## Einstellungen (PersonaGeneratorRun)")
            for k, v in settings_map[gid].items():
                md_lines.append(f"- {k}: {v}")
            md_lines.append("")
        if age_stats:
            md_lines.append("## Altersstatistik")
            md_lines.append(
                "- Mittelwert: {mean:.1f}, Median: {median:.1f}, SD: {std:.1f}, Min/Max: {min:.0f}/{max:.0f}".format(
                    **age_stats
                )
            )
            md_lines.append(
                "- Perzentile: p10={p10:.0f}, p25={p25:.0f}, p75={p75:.0f}, p90={p90:.0f}".format(
                    **age_stats
                )
            )
            md_lines.append("")
        if missing:
            md_lines.append("## Fehlende Werte (Quote)")
            for k, v in missing.items():
                md_lines.append(f"- {k}: {_pct(v)}")
            md_lines.append("")
        if cats:
            md_lines.append("## Kategorien (Top-N)")
            for col, rows in cats.items():
                md_lines.append(f"### {col.replace('_',' ').title()}")
                for r in rows:
                    md_lines.append(f"- {r[col]}: {_pct(r['share'])} ({int(r['count'])})")
                md_lines.append("")

        md_path = output_dir / f"persona_report_gen_{gid}.md"
        md_path.write_text("\n".join(md_lines))
        exported.append(md_path)

    return exported
