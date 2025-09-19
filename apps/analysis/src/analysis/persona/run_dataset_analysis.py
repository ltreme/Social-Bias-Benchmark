from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt

from analysis.persona.analytics import (
    set_default_theme,
    load_persona_dataframe_for_datasets,
    plot_category_100pct_grouped,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze persona distributions for dataset memberships.")
    p.add_argument("--dataset-ids", type=int, nargs="+", required=True, help="One or more dataset ids")
    p.add_argument("--output-dir", type=Path, default=Path("out/analysis/datasets"))
    p.add_argument("--top-n", type=int, default=10)
    p.add_argument("--formats", type=str, default="png,svg")
    return p.parse_args(argv)


def save(ax: plt.Axes, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ax.figure.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(ax.figure)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    set_default_theme()
    df = load_persona_dataframe_for_datasets(args.dataset_ids)
    if df.empty:
        print(f"No personas found for dataset_ids={args.dataset_ids}", file=sys.stderr)
        return 1

    out = args.output_dir
    fmts = [f.strip() for f in args.formats.split(',') if f.strip()]

    for col in ["gender", "origin_subregion", "religion", "sexuality"]:
        if col not in df.columns:
            continue
        ax = plot_category_100pct_grouped(df, group_col="dataset_id", column=col, top_n=args.top_n)
        for ext in fmts:
            save(ax, out / f"distribution_{col}_stacked100.{ext}")

    print(f"Dataset analysis written to {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

