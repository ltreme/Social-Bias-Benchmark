from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt

from analysis.persona.analytics import (
    PersonaDataConfig,
    export_summary_tables,
    load_persona_dataframe,
    plot_age_distribution,
    plot_category_distribution,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate persona dataset overview plots.")
    parser.add_argument(
        "--gen-ids",
        type=int,
        nargs="+",
        required=True,
        help="One or more persona generation ids to include (e.g. --gen-ids 12 13 14)",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Optional Peewee DB URL. Defaults to project SQLite database.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("out/analysis/persona"),
        help="Directory where plots and tables will be saved.",
    )
    return parser.parse_args(argv)


def save_figure(ax, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = ax.figure
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = PersonaDataConfig.from_iterable(args.gen_ids, db_url=args.db_url)
    df = load_persona_dataframe(config)
    if df.empty:
        print(f"No personas found for gen_ids={config.gen_ids}", file=sys.stderr)
        return 1

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    age_ax = plot_age_distribution(df)
    save_figure(age_ax, output_dir / "age_distribution.png")

    categories = [
        "gender",
        "origin_region",
        "religion",
        "sexuality",
        "marriage_status",
        "education",
        "occupation",
    ]

    for column in categories:
        if column not in df.columns:
            continue
        ax = plot_category_distribution(df, column)
        filename = f"distribution_{column}.png"
        save_figure(ax, output_dir / filename)

    export_summary_tables(df, output_dir)

    print(f"Analysis artifacts written to {output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
