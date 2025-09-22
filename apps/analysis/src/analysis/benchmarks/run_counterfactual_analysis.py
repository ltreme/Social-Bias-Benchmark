from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Dict, Tuple, List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from analysis.persona.analytics import set_default_theme
from shared.storage.db import init_database, get_db, db_proxy, create_tables
from shared.storage.models import (
    BenchmarkResult,
    BenchmarkRun,
    CounterfactualLink,
)


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze counterfactual paired effects (dataset-scoped)")
    p.add_argument("--dataset-id", type=int, required=True, help="Counterfactual dataset id")
    p.add_argument("--models", type=str, nargs="*", default=None, help="Model names to include")
    p.add_argument("--case-ids", type=str, nargs="*", default=None, help="Case IDs to include")
    p.add_argument("--rationale", type=str, choices=["on","off"], default=None, help="Filter by include_rationale")
    p.add_argument("--run-ids", type=int, nargs="*", default=None, help="Optional benchmark run ids to include")
    p.add_argument("--attribute", type=str, default=None, help="Optional changed_attribute filter (e.g., gender, age, origin, religion, sexuality)")
    p.add_argument("--output-dir", type=Path, default=Path("out/analysis/benchmark/counterfactuals"))
    return p.parse_args(argv)


def _wilcoxon_signed_rank(x: pd.Series) -> float:
    try:
        import scipy.stats as st  # type: ignore
        # zero_method='pratt' handles zeros sensibly
        s = pd.to_numeric(x, errors="coerce").dropna()
        if s.size < 3:
            return float("nan")
        stat, p = st.wilcoxon(s, zero_method='pratt', alternative='two-sided')
        return float(p)
    except Exception:
        return float("nan")


def main(argv=None) -> int:
    args = parse_args(argv)
    set_default_theme()
    init_database()
    create_tables()
    db = get_db()

    # Fetch links for this dataset (source <-> cf)
    q_links = CounterfactualLink.select().where(CounterfactualLink.dataset == int(args.dataset_id))
    if args.attribute:
        q_links = q_links.where(CounterfactualLink.changed_attribute == args.attribute)
    links: List[CounterfactualLink] = list(q_links)
    if not links:
        print(f"No counterfactual links in dataset {args.dataset_id} matching filters.")
        return 1

    src_ids = {str(l.source_persona_id) for l in links}
    cf_ids = {str(l.cf_persona_id) for l in links}

    # Build filters
    br_src = BenchmarkResult.select(
        BenchmarkResult.persona_uuid,
        BenchmarkResult.case_id,
        BenchmarkResult.model_name,
        BenchmarkResult.rating,
        BenchmarkResult.benchmark_run.alias("run_id"),
        BenchmarkRun.include_rationale,
    ).join(BenchmarkRun, on=(BenchmarkResult.benchmark_run == BenchmarkRun.id)).where(
        BenchmarkResult.persona_uuid.in_(list(src_ids))
    )
    br_cf = BenchmarkResult.select(
        BenchmarkResult.persona_uuid,
        BenchmarkResult.case_id,
        BenchmarkResult.model_name,
        BenchmarkResult.rating,
        BenchmarkResult.benchmark_run.alias("run_id"),
        BenchmarkRun.include_rationale,
    ).join(BenchmarkRun, on=(BenchmarkResult.benchmark_run == BenchmarkRun.id)).where(
        BenchmarkResult.persona_uuid.in_(list(cf_ids))
    )

    if args.models:
        br_src = br_src.where(BenchmarkResult.model_name.in_(list(args.models)))
        br_cf = br_cf.where(BenchmarkResult.model_name.in_(list(args.models)))
    if args.case_ids:
        br_src = br_src.where(BenchmarkResult.case_id.in_(list(args.case_ids)))
        br_cf = br_cf.where(BenchmarkResult.case_id.in_(list(args.case_ids)))
    if args.run_ids:
        br_src = br_src.where(BenchmarkResult.benchmark_run.in_(list(args.run_ids)))
        br_cf = br_cf.where(BenchmarkResult.benchmark_run.in_(list(args.run_ids)))
    if args.rationale is not None:
        want = True if args.rationale == 'on' else False
        br_src = br_src.where(BenchmarkRun.include_rationale == want)
        br_cf = br_cf.where(BenchmarkRun.include_rationale == want)

    # Materialize into dicts keyed by (persona, case, run, model)
    src_map: Dict[Tuple[str, str, int, str], float] = {}
    for r in br_src.dicts():
        key = (str(r['persona_uuid']), str(r['case_id']), int(r['run_id']) if r['run_id'] is not None else -1, str(r['model_name']))
        src_map[key] = float(r['rating']) if r['rating'] is not None else float('nan')

    cf_map: Dict[Tuple[str, str, int, str], float] = {}
    for r in br_cf.dicts():
        key = (str(r['persona_uuid']), str(r['case_id']), int(r['run_id']) if r['run_id'] is not None else -1, str(r['model_name']))
        cf_map[key] = float(r['rating']) if r['rating'] is not None else float('nan')

    # Pair by links and exact (case,run,model)
    rows: List[dict] = []
    for l in links:
        src_uuid = str(l.source_persona_id)
        cf_uuid = str(l.cf_persona_id)
        # Iterate all source results for this source uuid
        for (p, case_id, run_id, model), y_src in list(src_map.items()):
            if p != src_uuid:
                continue
            y_cf = cf_map.get((cf_uuid, case_id, run_id, model))
            if y_cf is None:
                continue
            rows.append({
                'source_uuid': src_uuid,
                'cf_uuid': cf_uuid,
                'case_id': case_id,
                'run_id': run_id,
                'model_name': model,
                'changed_attribute': l.changed_attribute,
                'from_value': l.from_value,
                'to_value': l.to_value,
                'delta': float(y_cf) - float(y_src),
                'y_src': y_src,
                'y_cf': y_cf,
            })

    if not rows:
        print("No paired results found (check that both source and cf have results under same run/model/case).")
        return 2

    df = pd.DataFrame(rows)
    outdir = args.output_dir / f"ds-{args.dataset_id}"
    outdir.mkdir(parents=True, exist_ok=True)

    # Overall summary
    overall = df['delta'].dropna()
    mean = float(overall.mean()) if not overall.empty else float('nan')
    sd = float(overall.std(ddof=1)) if overall.size > 1 else float('nan')
    n = int(overall.size)
    p_wil = _wilcoxon_signed_rank(overall)

    # By case
    per_case = df.groupby('case_id')['delta'].agg(['count','mean','std']).reset_index()
    per_case['p_wilcoxon'] = (
        df.groupby('case_id')['delta'].apply(_wilcoxon_signed_rank).reindex(per_case['case_id']).values
    )

    # By direction (from->to)
    df['direction'] = df['from_value'].astype(str) + '→' + df['to_value'].astype(str)
    per_dir = df.groupby(['changed_attribute','direction'])['delta'].agg(['count','mean','std']).reset_index()

    # Save CSVs
    df.to_csv(outdir / 'pairs.csv', index=False)
    per_case.to_csv(outdir / 'per_case.csv', index=False)
    per_dir.to_csv(outdir / 'per_direction.csv', index=False)

    # Plots
    sns.set_palette('colorblind')
    fig, ax = plt.subplots(figsize=(7,4))
    sns.histplot(overall, bins=21, kde=True, ax=ax)
    ax.axvline(0, color='k', lw=1)
    ax.set_title(f"Counterfactual paired deltas (cf - src)\nDS={args.dataset_id} | models={','.join(args.models) if args.models else 'all'} | rationale={args.rationale or 'all'}")
    ax.set_xlabel('Delta (rating)')
    fig.tight_layout()
    fig.savefig(outdir / 'delta_hist.png', dpi=200)
    plt.close(fig)

    # Forest per case
    fc = per_case.copy()
    fc = fc.dropna(subset=['mean'])
    fc = fc.sort_values('mean')
    y = np.arange(len(fc))
    fig2, ax2 = plt.subplots(figsize=(7, max(3, 0.3*len(fc)+1)))
    ax2.hlines(y, fc['mean'] - 1.96*fc['std'].fillna(0)/np.sqrt(fc['count'].clip(lower=1)), fc['mean'] + 1.96*fc['std'].fillna(0)/np.sqrt(fc['count'].clip(lower=1)), color='0.4')
    ax2.plot(fc['mean'], y, 'o', color=sns.color_palette('colorblind')[0])
    ax2.axvline(0, color='k', lw=1)
    ax2.set_yticks(y)
    ax2.set_yticklabels(fc['case_id'])
    ax2.set_xlabel('Delta (cf - src)')
    ax2.set_title(f"Per-case paired delta (±95% CI)\nDS={args.dataset_id} | models={','.join(args.models) if args.models else 'all'} | rationale={args.rationale or 'all'}")
    fig2.tight_layout()
    fig2.savefig(outdir / 'per_case_forest.png', dpi=200)
    plt.close(fig2)

    # Markdown summary
    lines = []
    lines.append(f"# Counterfactual Analysis — dataset {args.dataset_id}")
    lines.append("")
    lines.append(f"Models: {args.models or 'all'}  |  Rationale: {args.rationale or 'all'}")
    lines.append("")
    lines.append("## Overall")
    lines.append(f"n_pairs={n}, mean_delta={mean:.3f}, sd={sd:.3f}, Wilcoxon p={p_wil:.4g}")
    lines.append("")
    lines.append("![Delta histogram](delta_hist.png)")
    lines.append("")
    lines.append("## Per case")
    lines.append("![Per-case forest](per_case_forest.png)")
    lines.append("")
    lines.append("Top per-case effects (by |mean|):")
    if not fc.empty:
        top = fc.reindex(fc['mean'].abs().sort_values(ascending=False).index).head(10)
        for _, r in top.iterrows():
            lines.append(f"- {r['case_id']}: mean={r['mean']:.3f} (n={int(r['count'])}, p≈{r['p_wilcoxon']:.4g})")
    lines.append("")
    lines.append("## Per direction (from→to)")
    if not per_dir.empty:
        head = per_dir.reindex(per_dir['mean'].abs().sort_values(ascending=False).index).head(15)
        for _, r in head.iterrows():
            lines.append(f"- {r['changed_attribute']} {r['direction']}: mean={r['mean']:.3f} (n={int(r['count'])})")
    (outdir / 'counterfactual_report.md').write_text("\n".join(lines))

    print(f"Wrote counterfactual analysis to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

