from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt

from analysis.benchmarks.analytics import (
    BenchQuery,
    load_benchmark_dataframe,
    plot_rating_distribution,
    plot_rating_distribution_by_genid,
    plot_category_means,
    plot_deltas_vs_baseline,
    plot_deltas_with_significance,
    export_benchmark_report,
    per_question_fixed_effects,
    plot_fixed_effects_forest,
)
from analysis.persona.analytics import set_default_theme


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze benchmark results by demographics.")
    p.add_argument("--gen-ids", type=int, nargs="+", required=True, help="One or more gen_id values")
    p.add_argument("--models", type=str, nargs="*", default=None, help="Optional list of model names")
    p.add_argument("--question-uuids", type=str, nargs="*", default=None, help="Optional list of question UUIDs. If omitted, uses all questions.")
    p.add_argument("--db-url", type=str, default=None)
    p.add_argument("--output-dir", type=Path, default=Path("out/analysis/benchmark"))
    p.add_argument("--question-map", type=Path, default=None, help="Optional CSV with columns uuid,adjective for consistent coloring/labels")
    p.add_argument("--top-n", type=int, default=10)
    p.add_argument("--alpha", type=float, default=0.05, help="Significance threshold for permutation test")
    p.add_argument("--permutations", type=int, default=2000, help="Number of permutations for p-values")
    p.add_argument(
        "--forest-category",
        type=str,
        nargs="*",
        default=None,
        help="Optional filters for forest plots as pairs like gender=male religion=Christians; one per column.",
    )
    p.add_argument("--forest-min-n", type=int, default=2, help="Minimum n per category/baseline within a question to include in forest plot")
    return p.parse_args(argv)


def save(ax_or_fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = ax_or_fig if hasattr(ax_or_fig, "savefig") else ax_or_fig.figure
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main(argv=None) -> int:
    args = parse_args(argv)
    set_default_theme()
    cfg = BenchQuery(
        gen_ids=args.gen_ids,
        model_names=args.models,
        question_uuids=args.question_uuids,
        db_url=args.db_url,
    )
    df = load_benchmark_dataframe(cfg)
    if df.empty:
        print("No results for given filters.")
        return 1

    # Build structured output dir: <model(s)>/<gen_ids>/<question|all>
    import re, json
    def _sanitize(s: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", s).strip("_")

    model_part = "all-models"
    if args.models:
        model_part = "+".join(_sanitize(m) for m in args.models)

    gen_part = "gen-" + "-".join(map(str, sorted(set(df["gen_id"]))))

    if args.question_uuids is None or len(args.question_uuids) == 0:
        q_part = "q-all"
    elif len(args.question_uuids) == 1:
        q_part = f"q-{_sanitize(args.question_uuids[0])}"
    else:
        q_part = "q-multi"

    out = args.output_dir / model_part / gen_part / q_part
    out.mkdir(parents=True, exist_ok=True)
    # Persist filters for traceability
    (out / "filters.json").write_text(json.dumps({
        "models": args.models,
        "gen_ids": sorted(set(df["gen_id"])) ,
        "question_uuids": args.question_uuids,
        "alpha": args.alpha,
        "permutations": args.permutations,
    }, indent=2))

    # Overall distribution
    ax = plot_rating_distribution(df)
    save(ax, out / "rating_distribution.png")
    if len(set(df["gen_id"])) > 1:
        axg = plot_rating_distribution_by_genid(df)
        save(axg, out / "rating_distribution_by_genid.png")

    # Per-category means + CI and deltas for a few key demographics
    categories = [
        "gender",
        "origin_region",
        "religion",
        "migration_status",
        "sexuality",
        "marriage_status",
        "education",
    ]
        # Parse forest-category mapping
    forest_map: dict[str, str] = {}
    if args.forest_category:
        for tok in args.forest_category:
            if "=" in tok:
                k, v = tok.split("=", 1)
                forest_map[k.strip()] = v.strip()

    # Load question label mapping if provided
    qlabel_map = None
    if args.question_map and args.question_map.exists():
        try:
            import pandas as pd
            qdf = pd.read_csv(args.question_map)
            col_map = {c.lower(): c for c in qdf.columns}
            uuid_col = col_map.get("uuid")
            adj_col = col_map.get("adjective") or col_map.get("label")
            if uuid_col and adj_col:
                qlabel_map = dict(zip(qdf[uuid_col].astype(str), qdf[adj_col].astype(str)))
        except Exception as e:
            print(f"[warn] could not parse question-map: {e}")

    for col in categories:
        if col not in df.columns:
            continue
        ax1 = plot_category_means(df, col, top_n=args.top_n)
        save(ax1, out / f"means_{col}.png")
        ax2 = plot_deltas_with_significance(df, col, baseline=None, n_perm=args.permutations, alpha=args.alpha)
        save(ax2, out / f"delta_{col}.png")
        # Per-question fixed effects + forest
        perq = per_question_fixed_effects(df, col)
        if not perq.empty:
            if col in forest_map:
                ax3 = plot_fixed_effects_forest(perq, col, target_category=forest_map[col], min_n=args.forest_min_n, question_labels=qlabel_map)
                save(ax3, out / f"forest_{col}__{forest_map[col]}.png")
            else:
                ax3 = plot_fixed_effects_forest(perq, col, min_n=args.forest_min_n, question_labels=qlabel_map)
                save(ax3, out / f"forest_{col}.png")

            # Create one focused forest per value (category) vs baseline, into structured subfolders
            try:
                base = str(perq["baseline"].iloc[0])
                values = sorted(v for v in perq[col].astype(str).unique().tolist() if v != base)
                forest_dir = out / "forest" / col
                forest_dir.mkdir(parents=True, exist_ok=True)
                for v in values:
                    sub = perq.loc[perq[col].astype(str) == v].copy()
                    if sub.empty:
                        continue
                    axv = plot_fixed_effects_forest(sub, col, target_category=v, min_n=args.forest_min_n, question_labels=qlabel_map)
                    save(axv, forest_dir / f"{_sanitize(v)}.png")
                    try:
                        sub.to_csv(forest_dir / f"{_sanitize(v)}.csv", index=False)
                    except Exception:
                        pass
            except Exception as e:
                print(f"[warn] could not create per-value forests for {col}: {e}")

    # Text report
    title_bits = []
    title_bits.append(f"gen_id={','.join(map(str, sorted(set(df['gen_id']))))}")
    if args.models:
        title_bits.append(f"models={','.join(args.models)}")
    if args.question_uuids:
        title_bits.append(f"questions={','.join(args.question_uuids)}")
    title = "Benchmark Report – " + " | ".join(title_bits)
    export_benchmark_report(df, out / "reports", title=title, top_n=args.top_n, images_dir=out)

    print(f"Artifacts in {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
