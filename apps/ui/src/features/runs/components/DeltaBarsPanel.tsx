import { Text } from '@mantine/core';
import { ChartPanel } from '../../../components/ChartPanel';

type Deltas = {
  rows: Array<{
    category: string;
    delta?: number;
    p_value?: number;
    q_value?: number;
    n_base?: number;
    sd_base?: number;
    n_cat?: number;
    count?: number;
    sd_cat?: number;
    ci_low?: number;
    ci_high?: number;
  }>;
};

function computeApproxSigThreshold(deltas?: Deltas) {
  if (!deltas || !deltas.rows || deltas.rows.length === 0) return undefined;
  const nB = deltas.rows.find((r) => (r.n_base ?? 0) > 1)?.n_base ?? deltas.rows[0].n_base;
  const sdB = deltas.rows.find((r) => (r.sd_base ?? NaN) === (r.sd_base ?? NaN))?.sd_base ?? deltas.rows[0].sd_base;
  if (!nB || !sdB || !Number.isFinite(sdB)) return undefined;
  const ns = deltas.rows.map((r) => r.n_cat ?? r.count).filter((n) => (n ?? 0) > 1) as number[];
  const sds = deltas.rows.map((r) => r.sd_cat).filter((v) => Number.isFinite(v as number)) as number[];
  if (ns.length === 0 || sds.length === 0) return undefined;
  const med = (arr: number[]) => { const a = [...arr].sort((x, y) => x - y); const m = Math.floor(a.length / 2); return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2; };
  const nC = med(ns);
  const sdC = med(sds);
  const se = Math.sqrt((Number(sdB) ** 2) / Number(nB) + (Number(sdC) ** 2) / Number(nC));
  if (!Number.isFinite(se) || se <= 0) return undefined;
  return 1.96 * se;
}

export function DeltaBarsPanel({ deltas, title }: { deltas?: Deltas; title: string }) {
  const approxSigThreshold = computeApproxSigThreshold(deltas);
  const data: Partial<Plotly.Data>[] = deltas ? [{
    type: 'bar',
    x: deltas.rows.map((r) => r.delta),
    y: deltas.rows.map((r) => r.category),
    orientation: 'h',
    marker: { color: '#3182bd' },
    error_x: {
      type: 'data',
      symmetric: false,
      array: deltas.rows.map((r) => (r.ci_high != null && r.delta != null) ? Math.max(0, (r.ci_high as number) - (r.delta as number)) : 0),
      arrayminus: deltas.rows.map((r) => (r.ci_low != null && r.delta != null) ? Math.max(0, (r.delta as number) - (r.ci_low as number)) : 0),
      thickness: 1.2,
      width: 0,
      color: '#555',
    },
    hovertemplate: deltas.rows.map((r) => {
      const p = (r.p_value ?? NaN);
      const q = (r as any).q_value as number | undefined;
      const nB = r.n_base ?? 0, nC = r.n_cat ?? r.count;
      const sdB = r.sd_base ?? NaN, sdC = r.sd_cat ?? NaN;
      const lo = r.ci_low, hi = r.ci_high;
      return `${r.category}<br>Δ=%{x:.3f}${(lo!=null&&hi!=null)?` [${Number(lo).toFixed(3)}, ${Number(hi).toFixed(3)}]`:''}<br>p=${Number(p).toFixed(3)}${q!=null?`; q=${q.toFixed(3)}`:''}<br>n_base=${nB}, sd_base=${Number(sdB).toFixed(2)}<br>n_cat=${nC}, sd_cat=${Number(sdC).toFixed(2)}`;
    }),
    hoverinfo: 'text',
  }] : [];

  return (
    <>
      <ChartPanel title={title} data={data} layout={{
        shapes: [
          { type: 'line', x0: 0, x1: 0, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#222', width: 1 } },
          ...(approxSigThreshold ? [
            { type: 'line', x0: approxSigThreshold, x1: approxSigThreshold, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#2ca25f', width: 1, dash: 'dot' } },
            { type: 'line', x0: -approxSigThreshold, x1: -approxSigThreshold, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#2ca25f', width: 1, dash: 'dot' } },
          ] : []),
        ],
      }} />
      <Text size="sm" c="dimmed">Fehlerbalken: 95%-Konfidenzintervall der Mittelwertdifferenz; p nach Permutationstest. Grüne gestrichelte Linien: angenäherte Signifikanzgrenzen (±1.96·SE, global geschätzt).</Text>
    </>
  );
}

