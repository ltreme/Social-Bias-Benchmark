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
    compute_poststrat_weights,
    benjamini_hochberg,
    mann_whitney_cliffs,
)
from analysis.persona.analytics import set_default_theme


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze benchmark results by demographics.")
    p.add_argument("--gen-ids", type=int, nargs="+", required=False, help="One or more gen_id values (optional when --dataset-ids is used)")
    p.add_argument("--dataset-ids", type=int, nargs="+", required=False, help="Filter to personas that are members of these dataset ids")
    p.add_argument("--models", type=str, nargs="*", default=None, help="Optional list of model names")
    p.add_argument("--case-ids", type=str, nargs="*", default=None, help="Optional list of case IDs. If omitted, uses all cases.")
    p.add_argument("--db-url", type=str, default=None)
    p.add_argument("--output-dir", type=Path, default=Path("out/analysis/benchmark"))
    p.add_argument("--question-map", type=Path, default=Path("data/cases/simple_likert.csv"), help="CSV with columns id,adjective for consistent coloring/labels")
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
    p.add_argument(
        "--baselines",
        type=str,
        nargs="*",
        default=None,
        help="Override baseline per attribute as key=value pairs (e.g., gender=male origin_region=Europe religion=Christians)",
    )
    p.add_argument("--weight-by", type=str, nargs="*", default=None, help="Columns to post-stratify by (e.g., gender origin_region)")
    p.add_argument("--weight-ref-gen", type=int, default=None, help="Reference gen_id distribution for weights")
    p.add_argument("--weight-target-csv", type=Path, default=None, help="CSV with target shares for weight-by columns (must include column 'share')")
    p.add_argument("--run-ids", type=int, nargs="*", default=None, help="Optional benchmark run ids to include")
    p.add_argument("--rationale", type=str, choices=["on","off"], default=None, help="Filter by include_rationale flag")
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
        dataset_ids=args.dataset_ids,
        model_names=args.models,
        case_ids=args.case_ids,
        run_ids=args.run_ids,
        include_rationale=(True if args.rationale == "on" else False) if args.rationale is not None else None,
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

    # Derive gen_id part from data (works for dataset-filtered runs)
    gen_part = "gen-" + "-".join(map(str, sorted(set(df["gen_id"]))))

    ds_part = None
    if args.dataset_ids:
        ds_ids = [str(i) for i in args.dataset_ids]
        ds_part = "ds-" + (ds_ids[0] if len(ds_ids)==1 else f"n{len(ds_ids)}")

    if args.case_ids is None or len(args.case_ids) == 0:
        q_part = "q-all"
    elif len(args.case_ids) == 1:
        q_part = f"q-{_sanitize(args.case_ids[0])}"
    else:
        q_part = "q-multi"
        
    rat_part = None
    if args.rationale:
        rat_part = "rat-on" if args.rationale == "on" else "rat-off"

    out = args.output_dir / model_part / (ds_part or gen_part) / (rat_part or "rat-all") / q_part
    out.mkdir(parents=True, exist_ok=True)
    # Persist filters for traceability
    (out / "filters.json").write_text(json.dumps({
        "models": args.models,
        "gen_ids": sorted(set(df["gen_id"])) ,
        "dataset_ids": args.dataset_ids,
        "case_ids": args.case_ids,
        "alpha": args.alpha,
        "permutations": args.permutations,
        "run_ids": args.run_ids,
        "rationale": args.rationale,
    }, indent=2))


    # Optional: compute post-stratification weights
    weight_col = None
    if args.weight_by:
        target_df = None
        ref_filter = None
        if args.weight_target_csv and args.weight_target_csv.exists():
            import pandas as pd
            target_df = pd.read_csv(args.weight_target_csv)
        elif args.weight_ref_gen is not None:
            ref_filter = (df["gen_id"] == int(args.weight_ref_gen))
        df = compute_poststrat_weights(df, by=args.weight_by, target=target_df, ref_filter=ref_filter, weight_col="weight")
        weight_col = "weight"
    
    # Build context string for plot titles
    ctx_bits = []
    if args.models:
        ctx_bits.append("models=" + ",".join(args.models))
    if args.dataset_ids:
        ctx_bits.append("datasets=" + ",".join(map(str, args.dataset_ids)))
    if args.rationale:
        ctx_bits.append("rationale=" + args.rationale)
    if args.case_ids:
        ctx_bits.append("cases=" + ",".join(args.case_ids))
    context = " | ".join(ctx_bits) if ctx_bits else "(all results)"
    
    ax = plot_rating_distribution(df)
    
    try:
        ax.set_title("Rating distribution\n" + context)
    except Exception:
        pass
    
    save(ax, out / "rating_distribution.png")
    if len(set(df["gen_id"])) > 1:
        axg = plot_rating_distribution_by_genid(df)
        try:
            axg.set_title("Rating distribution by gen_id\n" + context)
        except Exception:
            pass
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

    # Parse baseline overrides
    baseline_map: dict[str, str] = {}
    if args.baselines:
        for tok in args.baselines:
            if "=" in tok:
                k, v = tok.split("=", 1)
                baseline_map[k.strip()] = v.strip()

    # Baseline resolution helper
    def _resolve_baseline_value(frame, col: str, desired: str | None) -> str | None:
        if not desired:
            return None
        if col not in frame.columns:
            return desired
        vals = frame[col].dropna().astype(str).unique().tolist()
        d = desired.strip().lower()
        for v in vals:
            if str(v).strip().lower() == d:
                return str(v)
        return desired

    # Load question label mapping if provided
    qlabel_map = None
    if args.question_map and args.question_map.exists():
        try:
            import pandas as pd
            qdf = pd.read_csv(args.question_map)
            col_map = {c.lower(): c for c in qdf.columns}
            uuid_col = col_map.get("id") or col_map.get("uuid")
            adj_col = col_map.get("adjective") or col_map.get("label")
            if uuid_col and adj_col:
                qlabel_map = dict(zip(qdf[uuid_col].astype(str), qdf[adj_col].astype(str)))
        except Exception as e:
            print(f"[warn] could not parse question-map: {e}")

    for col in categories:
        if col not in df.columns:
            continue
        ax1 = plot_category_means(df, col, top_n=args.top_n, weight_col=weight_col)
        try:
            ax1.set_title(f"Means ±95% CI — {col}\n" + context)
        except Exception:
            pass
        save(ax1, out / f"means_{col}.png")
        # Resolve optional baseline override for this column
        try:
            base_override = _resolve_baseline_value(df, col, baseline_map.get(col))
        except Exception:
            base_override = None
        ax2 = plot_deltas_with_significance(df, col, baseline=base_override, n_perm=args.permutations, alpha=args.alpha, weight_col=weight_col)
        try:
            ax2.set_title(f"Delta vs baseline — {col}\n" + context)
        except Exception:
            pass
        save(ax2, out / f"delta_{col}.png")
        # Per-question fixed effects + forest
        perq = per_question_fixed_effects(df, col, baseline=base_override)
        if not perq.empty:
            if col in forest_map:
                ax3 = plot_fixed_effects_forest(perq, col, target_category=forest_map[col], min_n=args.forest_min_n, question_labels=qlabel_map)
                try:
                    ax3.set_title(f"Forest — {col} (target={forest_map[col]})\n" + context)
                except Exception:
                    pass
                save(ax3, out / f"forest_{col}__{forest_map[col]}.png")
            else:
                ax3 = plot_fixed_effects_forest(perq, col, min_n=args.forest_min_n, question_labels=qlabel_map)
                try:
                    ax3.set_title(f"Forest — {col}\n" + context)
                except Exception:
                    pass
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
                    try:
                        axv.set_title(f"Forest — {col} = {v}\n" + context)
                    except Exception:
                        pass
                    save(axv, forest_dir / f"{_sanitize(v)}.png")
                    try:
                        sub.to_csv(forest_dir / f"{_sanitize(v)}.csv", index=False)
                    except Exception:
                        pass
            except Exception as e:
                print(f"[warn] could not create per-value forests for {col}: {e}")


    # Assemble significance tables (p, q, Cliff's delta)
    sig_tables = {}
    for col in categories:
        if col not in df.columns:
            continue
        sub = df.copy()
        sub[col] = sub[col].fillna("Unknown")
        counts = sub[col].value_counts()
        if counts.empty:
            continue
        base_override = _resolve_baseline_value(sub, col, baseline_map.get(col)) if 'baseline_map' in locals() else None
        baseline = base_override or counts.index[0]
        from analysis.benchmarks.analytics import deltas_with_significance
        t = deltas_with_significance(sub, col, baseline=baseline, n_perm=args.permutations, alpha=args.alpha, weight_col=weight_col)
        t = t.sort_values("p_value")
        t["q_value"] = benjamini_hochberg(t["p_value"].tolist())
        rows = []
        base_vals = sub.loc[sub[col] == baseline, "rating"]
        for _, r in t.iterrows():
            cat = r[col]
            vals = sub.loc[sub[col] == cat, "rating"]
            _, _, cd = mann_whitney_cliffs(base_vals, vals)
            rr = r.to_dict()
            rr["cliffs_delta"] = cd
            rows.append(rr)
        if rows:
            import pandas as pd
            sig_tables[col] = pd.DataFrame(rows)
    # Text report
    title_bits = []
    title_bits.append(f"gen_id={','.join(map(str, sorted(set(df['gen_id']))))}")
    if args.models:
        title_bits.append(f"models={','.join(args.models)}")
    if args.dataset_ids:
        title_bits.append(f"datasets={','.join(map(str,args.dataset_ids))}")
    if args.case_ids:
        title_bits.append(f"cases={','.join(args.case_ids)}")
    title = "Benchmark Report – " + " | ".join(title_bits)
    method_meta = {
        "gen_ids": sorted(set(df["gen_id"])),
        "models": args.models or "all",
        "cases": args.case_ids or "all",
        "dataset_ids": args.dataset_ids or [],
        "rationale": args.rationale,
        "alpha": args.alpha,
        "permutations": args.permutations,
        "weight_by": args.weight_by or [],
        "weight_ref_gen": args.weight_ref_gen,
        "weight_target_csv": str(args.weight_target_csv) if args.weight_target_csv else None,
        "forest_min_n": args.forest_min_n,
        "baselines": baseline_map if 'baseline_map' in locals() else {},
    }
    export_benchmark_report(
        df,
        out / "reports",
        title=title,
        top_n=args.top_n,
        images_dir=out,
        significance_tables=sig_tables,
        method_meta=method_meta,
    )

    print(f"Artifacts in {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
