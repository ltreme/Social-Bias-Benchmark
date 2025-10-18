import { Button, Card, Grid, Group, Select, Text, Title } from '@mantine/core';
import { useEffect, useState } from 'react';
import { Link, useParams } from '@tanstack/react-router';
import { ChartPanel } from '../../components/ChartPanel';
import { useRunDeltas, useRunForest, useRunMetrics, useRun, useRunMissing, useRunOrderMetrics, useRunMeans } from './hooks';
import { useStartBenchmark } from '../datasets/hooks';
import { OrderMetricsCard } from './components/OrderMetricsCard';
import { SignificanceTable } from './components/SignificanceTable';

const ATTRS = [
  { value: 'gender', label: 'Geschlecht' },
  { value: 'religion', label: 'Religion' },
  { value: 'sexuality', label: 'Sexualität' },
  { value: 'marriage_status', label: 'Familienstand' },
  { value: 'education', label: 'Bildung' },
  { value: 'origin_subregion', label: 'Herkunft-Subregion' },
];

export function RunDetailPage() {
  const { runId } = useParams({ from: '/runs/$runId' });
  const idNum = Number(runId);
  const { data: run, isLoading: isLoadingRun } = useRun(idNum);
  const { data: metrics } = useRunMetrics(idNum);
  const { data: missing } = useRunMissing(idNum);
  const startBench = useStartBenchmark();
  const order = useRunOrderMetrics(idNum);

  // grade helpers moved into ./components/Grades
  const [attr, setAttr] = useState<string>('gender');
  const availableCats = metrics?.attributes?.[attr]?.categories || [];
  const defaultBaseline = metrics?.attributes?.[attr]?.baseline || undefined;
  const [baseline, setBaseline] = useState<string | undefined>(defaultBaseline);
  const [target, setTarget] = useState<string | undefined>(undefined);

  // keep baseline in sync when attribute changes or metrics load
  useEffect(() => {
    if (!baseline && defaultBaseline) setBaseline(defaultBaseline);
  }, [defaultBaseline]);

  const { data: deltas } = useRunDeltas(idNum, attr, baseline);
  const { data: forest } = useRunForest(idNum, attr, baseline, target);
  // Means for fixed attribute set (avoid calling hooks in loops)
  const meansGender = useRunMeans(idNum, 'gender');
  const meansSubregion = useRunMeans(idNum, 'origin_subregion');
  const meansReligion = useRunMeans(idNum, 'religion');
  const meansMigration = useRunMeans(idNum, 'migration_status');
  const meansSexuality = useRunMeans(idNum, 'sexuality');
  const meansMarriage = useRunMeans(idNum, 'marriage_status');
  const meansEducation = useRunMeans(idNum, 'education');
  const meansData = [
    { a: 'gender', q: meansGender },
    { a: 'origin_subregion', q: meansSubregion },
    { a: 'religion', q: meansReligion },
    { a: 'migration_status', q: meansMigration },
    { a: 'sexuality', q: meansSexuality },
    { a: 'marriage_status', q: meansMarriage },
    { a: 'education', q: meansEducation },
  ];
  // Deltas (significance tables)
  const deltasGender = useRunDeltas(idNum, 'gender');
  const deltasSubregion = useRunDeltas(idNum, 'origin_subregion');
  const deltasReligion = useRunDeltas(idNum, 'religion');
  const deltasMigration = useRunDeltas(idNum, 'migration_status');
  const deltasSexuality = useRunDeltas(idNum, 'sexuality');
  const deltasMarriage = useRunDeltas(idNum, 'marriage_status');
  const deltasEducation = useRunDeltas(idNum, 'education');
  const deltasData = [
    { a: 'gender', q: deltasGender },
    { a: 'origin_subregion', q: deltasSubregion },
    { a: 'religion', q: deltasReligion },
    { a: 'migration_status', q: deltasMigration },
    { a: 'sexuality', q: deltasSexuality },
    { a: 'marriage_status', q: deltasMarriage },
    { a: 'education', q: deltasEducation },
  ];

  const histCounts = metrics?.hist?.counts || (metrics ? metrics.hist.shares.map((p) => Math.round(p * (metrics.n || 0))) : []);
  const histBars: Partial<Plotly.Data>[] = metrics ? [
    { type: 'bar', x: metrics.hist.bins, y: metrics.hist.shares, marker: { color: '#3182bd' }, text: metrics.hist.shares.map((p, i) => `${(p * 100).toFixed(0)}% (n=${histCounts[i] ?? 0})`), textposition: 'outside', hovertemplate: '%{x}: %{y:.0%} (n=%{customdata})', customdata: histCounts },
    { type: 'scatter', mode: 'markers', x: metrics.hist.bins, y: histCounts, yaxis: 'y2', opacity: 0, showlegend: false },
  ] : [];

  // Compute an approximate global significance threshold: ±1.96 * sqrt(sd_b^2/n_b + median(sd_c^2/n_c))
  const approxSigThreshold = (() => {
    if (!deltas || !deltas.rows || deltas.rows.length === 0) return undefined;
    const nB = deltas.rows.find(r => (r.n_base ?? 0) > 1)?.n_base ?? deltas.rows[0].n_base;
    const sdB = deltas.rows.find(r => (r.sd_base ?? NaN) === (r.sd_base ?? NaN))?.sd_base ?? deltas.rows[0].sd_base;
    if (!nB || !sdB || !Number.isFinite(sdB)) return undefined;
    const ns = deltas.rows.map(r => r.n_cat ?? r.count).filter(n => (n ?? 0) > 1) as number[];
    const sds = deltas.rows.map(r => r.sd_cat).filter(v => Number.isFinite(v as number)) as number[];
    if (ns.length === 0 || sds.length === 0) return undefined;
    const med = (arr: number[]) => { const a = [...arr].sort((x,y)=>x-y); const m = Math.floor(a.length/2); return a.length%2? a[m] : (a[m-1]+a[m])/2; };
    const nC = med(ns);
    const sdC = med(sds);
    const se = Math.sqrt((Number(sdB) ** 2) / Number(nB) + (Number(sdC) ** 2) / Number(nC));
    if (!Number.isFinite(se) || se <= 0) return undefined;
    return 1.96 * se;
  })();

  const deltaBars: Partial<Plotly.Data>[] = deltas ? [{
    type: 'bar',
    x: deltas.rows.map(r => r.delta),
    y: deltas.rows.map(r => r.category),
    orientation: 'h',
    marker: { color: '#3182bd' },
    error_x: {
      type: 'data',
      symmetric: false,
      array: deltas.rows.map(r => (r.ci_high != null && r.delta != null) ? Math.max(0, (r.ci_high as number) - (r.delta as number)) : 0),
      arrayminus: deltas.rows.map(r => (r.ci_low != null && r.delta != null) ? Math.max(0, (r.delta as number) - (r.ci_low as number)) : 0),
      thickness: 1.2,
      width: 0,
      color: '#555',
    },
    hovertemplate: deltas.rows.map(r => {
      const p = (r.p_value ?? NaN);
      const q = (r as any).q_value as number | undefined;
      const nB = r.n_base ?? 0, nC = r.n_cat ?? r.count;
      const sdB = r.sd_base ?? NaN, sdC = r.sd_cat ?? NaN;
      const lo = r.ci_low, hi = r.ci_high;
      return `${r.category}<br>Δ=%{x:.3f}${(lo!=null&&hi!=null)?` [${Number(lo).toFixed(3)}, ${Number(hi).toFixed(3)}]`:''}<br>p=${Number(p).toFixed(3)}${q!=null?`; q=${q.toFixed(3)}`:''}<br>n_base=${nB}, sd_base=${Number(sdB).toFixed(2)}<br>n_cat=${nC}, sd_cat=${Number(sdC).toFixed(2)}`;
    }),
    hoverinfo: 'text',
  }] : [];

  const forestLabels = forest?.rows?.map(r => `${r.label || r.case_id} (${r.case_id})`) || [];
  const forestTrace: Partial<Plotly.Data> | null = forest && forest.rows.length > 0 ? {
    type: 'scatter', mode: 'markers',
    x: forest.rows.map(r => r.delta),
    y: forestLabels,
    error_x: {
      type: 'data',
      symmetric: false,
      array: forest.rows.map(r => (r.ci_high != null && r.delta != null) ? Math.max(0, r.ci_high - r.delta) : 0),
      arrayminus: forest.rows.map(r => (r.ci_low != null && r.delta != null) ? Math.max(0, r.delta - r.ci_low) : 0),
      thickness: 1.2,
      width: 0,
    },
    marker: { size: 6 },
  } : null;

  return (
    <Card>
      <Title order={2} mb="md">Run {runId} – Analyse</Title>
      {isLoadingRun ? ('') : run ? (
          <div style={{ marginBottom: '1em' }}>
              <b>Datensatz:</b> <Link to={`/datasets/${run.dataset?.id}`}>{run.dataset?.id}: {run.dataset?.name}</Link> | <b>Modell:</b> {run.model_name} | {run.created_at ? (<><b>Erstellt:</b> {new Date(run.created_at).toLocaleDateString()} | <b>Ergebnisse:</b> {run.n_results} | </>) : null}
              {run.include_rationale ? (<><b>Mit Begründung (with_rational):</b> {run.include_rationale ? 'Ja' : 'Nein'} </>) : null}
              {missing && typeof missing.missing === 'number' && typeof missing.total === 'number' ? (
                <>
                  <br />
                  <b>Status:</b> {missing.missing > 0 ? `partial ${missing.total - missing.missing}/${missing.total}` : `done ${missing.total}/${missing.total}`}
                  {missing.missing > 0 ? (
                    <>
                      <div style={{ marginTop: 6 }}>
                        {missing.samples && missing.samples.length > 0 ? (
                          <>
                            Fehlende Beispiele: {missing.samples.slice(0,5).map(s => `(${s.persona_uuid.slice(0,8)}…, ${s.case_id}${s.adjective ? ' · ' + s.adjective : ''})`).join(', ')}
                          </>
                        ) : null}
                      </div>
                      <div style={{ marginTop: 6 }}>
                        <Button size="xs" onClick={async ()=>{
                          if (!run.dataset?.id) return;
                          try {
                            const rs = await startBench.mutateAsync({ dataset_id: run.dataset.id, resume_run_id: idNum });
                          } catch(e){}
                        }}>Run fortsetzen</Button>
                      </div>
                    </>
                  ) : null}
                </>
              ) : null}
          </div>
      ) : (
          <div style={{ marginBottom: '1em' }}>Run nicht gefunden.</div>
      )}
      <Grid>

        <Grid.Col span={{ base: 12 }}>
          <OrderMetricsCard data={order.data} />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <ChartPanel title="Rating-Verteilung" data={histBars} layout={{
            barmode: 'group',
            yaxis: { tickformat: '.0%', rangemode: 'tozero', title: 'Anteil' },
            yaxis2: { overlaying: 'y', side: 'right', title: 'Anzahl', rangemode: 'tozero', showgrid: false },
          }} />
          <Text size="sm" c="dimmed">Skala: 1 = gar nicht &lt;adjektiv&gt; … 5 = sehr &lt;adjektiv&gt;</Text>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Group align="end">
            <Select label="Merkmal" data={ATTRS} value={attr} onChange={(v) => { setAttr(v || 'gender'); setBaseline(undefined); setTarget(undefined); }} />
            <Select label="Baseline" data={availableCats.map(c => ({ value: c.category, label: c.category }))} value={baseline} onChange={setBaseline} clearable placeholder={defaultBaseline || 'auto'} />
        </Group>
          <ChartPanel title={`Delta vs. Baseline (${baseline || defaultBaseline || 'auto'})`} data={deltaBars} layout={{
            shapes: [
              { type: 'line', x0: 0, x1: 0, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#222', width: 1 } },
              ...(approxSigThreshold ? [
                { type: 'line', x0: approxSigThreshold, x1: approxSigThreshold, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#2ca25f', width: 1, dash: 'dot' } },
                { type: 'line', x0: -approxSigThreshold, x1: -approxSigThreshold, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#2ca25f', width: 1, dash: 'dot' } },
              ] : []),
            ],
          }} />
          <Text size="sm" c="dimmed">Fehlerbalken: 95%-Konfidenzintervall der Mittelwertdifferenz; p nach Permutationstest. Grüne gestrichelte Linien: angenäherte Signifikanzgrenzen (±1.96·SE, global geschätzt).</Text>
        </Grid.Col>
        <Grid.Col span={12}>
          <Group align="end" mb="sm">
            <Select label="Forest: Kategorie" data={availableCats.map(c => ({ value: c.category, label: c.category })).filter(c => c.value !== (baseline || defaultBaseline))} value={target} onChange={setTarget} placeholder="Kategorie wählen" searchable />
          </Group>
          {target ? (forestTrace ? (
            <ChartPanel title={`Per-Question Forest – ${attr}`} data={[forestTrace]} height={Math.max(360, (forest?.rows.length || 1) * 60)}
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
                  // add symmetric significance threshold around 0 based on median SE across rows, if available
                  ...( (() => {
                      const ses = (forest?.rows || []).map(r => r.se).filter(v => typeof v === 'number' && isFinite(v as number)) as number[];
                      if (!ses.length) return [] as any[];
                      const a = [...ses].sort((x,y)=>x-y); const m = Math.floor(a.length/2); const med = a.length%2? a[m] : (a[m-1]+a[m])/2;
                      const thr = 1.96 * med;
                      if (!isFinite(thr) || thr <= 0) return [] as any[];
                      return [
                        { type: 'line', x0: thr, x1: thr, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#888', width: 1, dash: 'dot' } },
                        { type: 'line', x0: -thr, x1: -thr, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#888', width: 1, dash: 'dot' } },
                      ] as any[];
                  })() ),
                ],
                margin: { l: 180, r: 40, t: 24, b: 40 },
                yaxis: { title: 'Adjektiv', automargin: true, categoryorder: 'array', categoryarray: forestLabels },
                xaxis: (() => {
                  const vals = [
                    ...(forest?.rows?.map(r => r.delta) || []),
                    ...(forest?.rows?.map(r => r.ci_low || 0) || []),
                    ...(forest?.rows?.map(r => r.ci_high || 0) || []),
                    ...(forest?.overall ? [forest.overall.mean || 0, forest.overall.ci_low || 0, forest.overall.ci_high || 0] : []),
                  ].filter((v) => v!=null && v===v) as number[];
                  const M = vals.length ? Math.max(...vals.map(v => Math.abs(v))) : 1;
                  const pad = Math.max(0.5, M * 0.1);
                  return { title: `Delta vs Baseline (${baseline || defaultBaseline || ''})`, range: [-(M+pad), (M+pad)] };
                })(),
                showlegend: false,
              }}
            />
          ) : (
            <div>Keine Daten für Forest-Plot.</div>
          )) : (<div>Bitte Kategorie für Forest auswählen.</div>)}
          <Text size="sm" c="dimmed">Legende: 0-Linie (schwarz), Gesamtmittel (grün gestrichelt), 95%-CI (grün transparent). Beide Seiten um 0 werden angezeigt.</Text>
        </Grid.Col>
        <Grid.Col span={12}>
          <Card withBorder padding="md" style={{ marginBottom: 12 }}>
            <Title order={4}>Mittelwerte pro Merkmal</Title>
            {meansData.map(({a,q}) => (
              <div key={a} style={{ marginTop: 8 }}>
                <b>{ATTRS.find(x=>x.value===a)?.label || a}</b>
                <div style={{ fontFamily:'monospace' }}>
                  {q.data?.rows && q.data.rows.length>0 ? q.data.rows.map(r => `${r.category}: mean=${r.mean.toFixed(2)} (n=${r.count})`).join(' · ') : '—'}
                </div>
              </div>
            ))}
          </Card>
        </Grid.Col>
        <Grid.Col span={12}>
          <Card withBorder padding="md" style={{ marginBottom: 12 }}>
            <Title order={4}>Signifikanz-Tabellen (p, q, Cliff’s δ)</Title>
            {deltasData.map(({a,q}) => (
              <div key={a} style={{ marginTop: 12 }}>
                <b>{ATTRS.find(x=>x.value===a)?.label || a}</b>
                <SignificanceTable rows={q.data?.rows || []} />
              </div>
            ))}
          </Card>
        </Grid.Col>

      </Grid>
    </Card>
  );
}
