import { Text } from '@mantine/core';
import { ChartPanel } from '../../../components/ChartPanel';

type ForestRow = {
  case_id: string | number;
  label?: string;
  delta?: number | null;
  ci_low?: number | null;
  ci_high?: number | null;
  se?: number | null;
};

export type ForestDataset = {
  target: string;
  color?: string;
  rows: ForestRow[];
  overall?: { mean?: number | null; ci_low?: number | null; ci_high?: number | null };
};

const COLORS = ['#1f77b4', '#ff7f0e', '#2ca25f', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'];

export function MultiForestPlotPanel({
  datasets,
  attr,
  baseline,
  defaultBaseline,
  heightPerRow = 60,
}: {
  datasets: ForestDataset[];
  attr: string;
  baseline?: string;
  defaultBaseline?: string;
  heightPerRow?: number;
}) {
  const primary = datasets[0];
  const forestLabels = primary?.rows?.map((r) => `${r.label || r.case_id} (${r.case_id})`) || [];

  const traces: Partial<Plotly.Data>[] = (datasets || []).map((d, i) => ({
    name: d.target,
    type: 'scatter',
    mode: 'markers',
    x: d.rows.map((r) => r.delta ?? null),
    y: forestLabels,
    error_x: {
      type: 'data',
      symmetric: false,
      array: d.rows.map((r) => (r.ci_high != null && r.delta != null) ? Math.max(0, (r.ci_high as number) - (r.delta as number)) : 0),
      arrayminus: d.rows.map((r) => (r.ci_low != null && r.delta != null) ? Math.max(0, (r.delta as number) - (r.ci_low as number)) : 0),
      thickness: 1.2,
      width: 0,
      color: d.color || COLORS[i % COLORS.length],
    },
    marker: { size: 6, color: d.color || COLORS[i % COLORS.length] },
  }));

  const height = Math.max(360, (primary?.rows.length || 1) * heightPerRow);

  const haveData = traces.length > 0 && (primary?.rows?.length || 0) > 0;

  // significance threshold based on primary rows
  const ses = (primary?.rows || [])
    .map((r) => Number(r.se ?? NaN))
    .filter((x) => Number.isFinite(x) && x > 0) as number[];
  const shapes: any[] = [
    { type: 'line', x0: 0, x1: 0, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#222', width: 1 } },
  ];
  if (ses.length) {
    const a = [...ses].sort((x, y) => x - y);
    const m = Math.floor(a.length / 2);
    const med = a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
    const thr = 1.96 * med;
    shapes.push(
      { type: 'line', x0: thr, x1: thr, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#2ca25f', width: 1, dash: 'dot' } },
      { type: 'line', x0: -thr, x1: -thr, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#2ca25f', width: 1, dash: 'dot' } },
    );
  }

  return (
    <>
      {haveData ? (
        <ChartPanel
          title={`Per-Question Forest – ${attr}`}
          data={traces}
          height={height}
          layout={{
            shapes,
            margin: { l: 180, r: 40, t: 24, b: 40 },
            yaxis: { title: { text: 'Adjektiv' }, automargin: true, categoryorder: 'array', categoryarray: forestLabels },
            xaxis: (() => {
              const vals: number[] = [];
              datasets.forEach((d) => {
                d.rows.forEach((r) => {
                  if (r.delta != null) vals.push(r.delta);
                  if (r.ci_low != null) vals.push(r.ci_low);
                  if (r.ci_high != null) vals.push(r.ci_high);
                });
              });
              const M = vals.length ? Math.max(...vals.map((v) => Math.abs(v))) : 1;
              const pad = Math.max(0.5, M * 0.1);
              return { title: { text: `Delta vs Baseline (${baseline || defaultBaseline || ''})` }, range: [-(M + pad), (M + pad)] };
            })(),
            showlegend: true,
            legend: { orientation: 'h', y: -0.12 },
          }}
        />
      ) : (
        <div>Keine Daten für Forest-Plot.</div>
      )}
      <Text size="sm" c="dimmed">Legende: 0-Linie (schwarz), gestrichelte grüne Linien zeigen angenäherte Signifikanzgrenzen (±1.96·SE). Mehrere Kategorien sind farblich unterschieden.</Text>
    </>
  );
}

