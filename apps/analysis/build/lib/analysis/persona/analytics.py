from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import peewee as pw

from shared.storage.db import init_database, get_db, db_proxy
from shared.storage.models import Country, Persona

try:
    import seaborn as sns
    import matplotlib.pyplot as plt
except ImportError as exc:  # pragma: no cover - optional during import
    raise RuntimeError(
        "Install seaborn and matplotlib to use plotting helpers: pip install seaborn matplotlib"
    ) from exc


@dataclass(slots=True)
class PersonaDataConfig:
    dataset_ids: tuple[int, ...]
    db_url: str | None = None

    @classmethod
    def from_iterable(cls, dataset_ids: Iterable[int], db_url: str | None = None) -> "PersonaDataConfig":
        return cls(dataset_ids=tuple(int(gid) for gid in dataset_ids), db_url=db_url)


def _ensure_database(db_url: str | None = None) -> None:
    if getattr(db_proxy, "obj", None) is None:
        init_database(db_url=db_url)
    elif db_url:
        # Already initialised with different URL; reconnect explicitly.
        init_database(db_url=db_url)


def load_persona_dataframe(config: PersonaDataConfig) -> pd.DataFrame:
    """Return persona rows for the configured dataset_ids as a DataFrame."""
    if not config.dataset_ids:
        raise ValueError("Provide at least one dataset_id")

    _ensure_database(config.db_url)
    db = get_db()

    query = (
        Persona.select(
            Persona.uuid.alias("persona_uuid"),
            Persona.dataset_id,
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
        .where(Persona.dataset_id.in_(config.dataset_ids))
    )

    # Peewee requires manual alias for join when not using names.
    # Provide deterministic ordering so repeated runs remain stable.
    query = query.order_by(Persona.dataset_id, Persona.created_at)

    with db.atomic():
        rows: list[dict[str, Any]] = list(query.dicts())

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["dataset_id"] = df["dataset_id"].astype(int)
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    return df


def summarise_category(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Aggregate counts and shares for a categorical column per dataset_id."""
    if column not in df.columns:
        raise KeyError(f"Column '{column}' missing from persona dataframe")
    working = df[["dataset_id", column]].copy()
    working[column] = working[column].fillna("Unknown")

    counts = (
        working.groupby(["dataset_id", column], dropna=False)
        .size()
        .rename("count")
        .reset_index()
    )

    totals = counts.groupby("dataset_id")["count"].sum().rename("total")
    summary = counts.merge(totals, on="dataset_id")
    summary["share"] = summary["count"] / summary["total"]
    summary = summary.sort_values(["dataset_id", "count"], ascending=[True, False])
    return summary


def plot_category_distribution(
    df: pd.DataFrame,
    column: str,
    *,
    ax: plt.Axes | None = None,
    figsize: tuple[float, float] = (8, 4),
    palette: str = "tab10",
) -> plt.Axes:
    """Draw a grouped bar chart for a categorical column."""
    summary = summarise_category(df, column)
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)

    sns.barplot(
        data=summary,
        x=column,
        y="share",
        hue="dataset_id",
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
        hue="dataset_id",
        element="step",
        stat="probability",
        common_norm=False,
        bins=bins,
        palette=palette,
        ax=ax,
    )
    ax.set_ylabel("Share")
    ax.set_xlabel("Age")
    ax.set_title("Age distribution by dataset_id")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
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
