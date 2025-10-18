import { Text } from '@mantine/core';
import { ChartPanel } from '../../../components/ChartPanel';

type ForestRow = {
  case_id: string | number;
  label?: string;
  delta?: number;
  ci_low?: number;
  ci_high?: number;
  se?: number;
};

type ForestData = {
  rows: ForestRow[];
  overall?: { mean?: number; ci_low?: number; ci_high?: number };
};

export function ForestPlotPanel({
  forest,
  attr,
  baseline,
  defaultBaseline,
  heightPerRow = 60,
}: {
  forest?: ForestData;
  attr: string;
  baseline?: string;
  defaultBaseline?: string;
  heightPerRow?: number;
}) {
  const forestLabels = forest?.rows?.map((r) => `${r.label || r.case_id} (${r.case_id})`) || [];
  const forestTrace: Partial<Plotly.Data> | null = forest && forest.rows.length > 0 ? {
    type: 'scatter',
    mode: 'markers',
    x: forest.rows.map((r) => r.delta),
    y: forestLabels,
    error_x: {
      type: 'data',
      symmetric: false,
      array: forest.rows.map((r) => (r.ci_high != null && r.delta != null) ? Math.max(0, (r.ci_high as number) - (r.delta as number)) : 0),
      arrayminus: forest.rows.map((r) => (r.ci_low != null && r.delta != null) ? Math.max(0, (r.delta as number) - (r.ci_low as number)) : 0),
      thickness: 1.2,
      width: 0,
    },
    marker: { size: 6 },
  } : null;

  const height = Math.max(360, (forest?.rows.length || 1) * heightPerRow);

  return (
    <>
      {forestTrace ? (
        <ChartPanel
          title={`Per-Question Forest – ${attr}`}
          data={[forestTrace]}
          height={height}
          layout={{
            shapes: [
              { type: 'line', x0: 0, x1: 0, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#222', width: 1 } },
              ...(forest?.overall?.mean != null ? [
                { type: 'line', x0: forest.overall.mean, x1: forest.overall.mean, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#2ca25f', width: 2, dash: 'dash' } },
                ...(forest.overall.ci_low != null && forest.overall.ci_high != null ? [
                  { type: 'rect', x0: forest.overall.ci_low, x1: forest.overall.ci_high, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { width: 0 }, fillcolor: 'rgba(44,162,95,0.15)' },
                  { type: 'line', x0: forest.overall.ci_low, x1: forest.overall.ci_low, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#2ca25f', width: 1, dash: 'dot' } },
                  { type: 'line', x0: forest.overall.ci_high, x1: forest.overall.ci_high, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#2ca25f', width: 1, dash: 'dot' } },
                ] : []),
              ] : []),
              // symmetric significance threshold around 0 based on median SE across rows, if available
              ...(() => {
                const ses = (forest?.rows || []).map((r) => Number(r.se ?? NaN)).filter((x) => Number.isFinite(x) && x > 0) as number[];
                if (!ses.length) return [] as any[];
                const a = [...ses].sort((x, y) => x - y); const m = Math.floor(a.length / 2); const med = a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
                const thr = 1.96 * med;
                return [
                  { type: 'line', x0: thr, x1: thr, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#2ca25f', width: 1, dash: 'dot' } },
                  { type: 'line', x0: -thr, x1: -thr, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#2ca25f', width: 1, dash: 'dot' } },
                ] as any[];
              })(),
            ],
            margin: { l: 180, r: 40, t: 24, b: 40 },
            yaxis: { title: 'Adjektiv', automargin: true, categoryorder: 'array', categoryarray: forestLabels },
            xaxis: (() => {
              const vals = [
                ...(forest?.rows?.map((r) => r.delta) || []),
                ...(forest?.rows?.map((r) => r.ci_low || 0) || []),
                ...(forest?.rows?.map((r) => r.ci_high || 0) || []),
                ...(forest?.overall ? [forest.overall.mean || 0, forest.overall.ci_low || 0, forest.overall.ci_high || 0] : []),
              ].filter((v) => v != null && v === v) as number[];
              const M = vals.length ? Math.max(...vals.map((v) => Math.abs(v))) : 1;
              const pad = Math.max(0.5, M * 0.1);
              return { title: `Delta vs Baseline (${baseline || defaultBaseline || ''})`, range: [-(M + pad), (M + pad)] };
            })(),
            showlegend: false,
          }}
        />
      ) : (
        <div>Keine Daten für Forest-Plot.</div>
      )}
      <Text size="sm" c="dimmed">Legende: 0-Linie (schwarz), Gesamtmittel (grün gestrichelt), 95%-CI (grün transparent). Beide Seiten um 0 werden angezeigt.</Text>
    </>
  );
}

