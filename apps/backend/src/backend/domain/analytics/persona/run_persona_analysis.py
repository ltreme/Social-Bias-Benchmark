from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt

from backend.domain.analytics.persona.analytics import (
    PersonaDataConfig,
    export_summary_tables,
    generate_persona_reports,
    load_persona_dataframe,
    make_country_share_choropleth,
    make_region_choropleth,
    plot_age_ridgeline,
    plot_category_100pct,
    set_default_theme,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate persona dataset overview plots."
    )
    parser.add_argument(
        "--dataset-ids",
        type=int,
        nargs="+",
        required=True,
        help="One or more dataset ids to include (e.g. --dataset-ids 12 13 14)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Top-N Kategorien behalten, Rest in 'Other' zusammenfassen (0=deaktiviert)",
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
    parser.add_argument(
        "--formats",
        type=str,
        default="png,svg",
        help="Comma-separated list of export formats (e.g. png,svg)",
    )
    parser.add_argument(
        "--with-maps",
        action="store_true",
        help="Export interactive Plotly choropleth maps (HTML).",
    )
    parser.add_argument(
        "--map-normalize",
        type=str,
        default="per_gen_p95",
        choices=["none", "per_gen_p95", "log1p"],
        help="Normalization for country share map to mitigate dominance (default: per_gen_p95)",
    )
    parser.add_argument(
        "--map-vmax-pct",
        type=float,
        default=0.95,
        help="Percentile for per_gen_p95 normalization (0..1)",
    )
    return parser.parse_args(argv)


def save_figure(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = PersonaDataConfig.from_iterable(args.dataset_ids, db_url=args.db_url)
    set_default_theme()
    df = load_persona_dataframe(config)
    if df.empty:
        print(
            f"No personas found for dataset_ids={config.dataset_ids}", file=sys.stderr
        )
        return 1

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Age ridgeline
    g = plot_age_ridgeline(df)
    fmts = [f.strip() for f in args.formats.split(",") if f.strip()]
    for ext in fmts:
        save_figure(g.fig, output_dir / f"age_distribution_ridgeline.{ext}")

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
        ax = plot_category_100pct(df, column, top_n=args.top_n)
        for ext in fmts:
            filename = f"distribution_{column}_stacked100.{ext}"
            save_figure(ax.figure, output_dir / filename)

    export_summary_tables(df, output_dir)
    # Per-dataset_id text/JSON reports
    reports_dir = output_dir / "reports"
    generate_persona_reports(df, reports_dir, top_n=args.top_n)

    if args.with_maps:
        try:
            fig_regions = make_region_choropleth(df, animate=True)
            fig_regions.write_html(output_dir / "map_regions.html")
            fig_share = make_country_share_choropleth(
                df,
                animate=True,
                normalize=args.map_normalize,
                vmax_percentile=args.map_vmax_pct,
            )
            fig_share.write_html(output_dir / "map_country_share.html")
        except RuntimeError as e:
            print(f"[maps] {e}")

    print(f"Analysis artifacts written to {output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
