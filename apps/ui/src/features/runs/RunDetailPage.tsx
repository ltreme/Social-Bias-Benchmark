import { Card, Grid, Group, Select, Title } from '@mantine/core';
import { useEffect, useState } from 'react';
import { Link, useParams } from '@tanstack/react-router';
import { ChartPanel } from '../../components/ChartPanel';
import { useRunDeltas, useRunForest, useRunMetrics, useRun } from './hooks';

const ATTRS = [
  { value: 'gender', label: 'Geschlecht' },
  { value: 'religion', label: 'Religion' },
  { value: 'sexuality', label: 'Sexualität' },
  { value: 'marriage_status', label: 'Familienstand' },
  { value: 'education', label: 'Bildung' },
  { value: 'origin_region', label: 'Herkunft-Region' },
];

export function RunDetailPage() {
  const { runId } = useParams({ from: '/runs/$runId' });
  const idNum = Number(runId);
  const { data: run, isLoading: isLoadingRun } = useRun(idNum);
  const { data: metrics } = useRunMetrics(idNum);
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

  const histBars: Partial<Plotly.Data>[] = metrics ? [{ type: 'bar', x: metrics.hist.bins, y: metrics.hist.shares, marker: { color: '#3182bd' } }] : [];

  const deltaBars: Partial<Plotly.Data>[] = deltas ? [{
    type: 'bar',
    x: deltas.rows.map(r => r.delta),
    y: deltas.rows.map(r => r.category),
    orientation: 'h',
    marker: {
      color: deltas.rows.map(r => r.significant ? '#2ca25f' : '#3182bd'),
    },
    hovertext: deltas.rows.map(r => `Δ=${r.delta.toFixed(3)}; p=${r.p_value.toFixed(3)}; n=${r.count}`),
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
          </div>
      ) : (
          <div style={{ marginBottom: '1em' }}>Run nicht gefunden.</div>
      )}
      <Grid>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <ChartPanel title="Rating-Verteilung" data={histBars} layout={{ yaxis: { tickformat: '.0%', rangemode: 'tozero' } }} />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Group align="end">
            <Select label="Merkmal" data={ATTRS} value={attr} onChange={(v) => { setAttr(v || 'gender'); setBaseline(undefined); setTarget(undefined); }} />
            <Select label="Baseline" data={availableCats.map(c => ({ value: c.category, label: c.category }))} value={baseline} onChange={setBaseline} clearable placeholder={defaultBaseline || 'auto'} />
        </Group>
          <ChartPanel title={`Delta vs. Baseline (${baseline || defaultBaseline || 'auto'})`} data={deltaBars} layout={{ shapes: [{ type: 'line', x0: 0, x1: 0, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#222', width: 1 } }] }} />
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
                    ...(forest.overall.ci_low != null && forest.overall.ci_high != null ? [{ type: 'rect', x0: forest.overall.ci_low, x1: forest.overall.ci_high, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { width: 0 }, fillcolor: 'rgba(44,162,95,0.15)' }] : []),
                  ] : []),
                ],
                margin: { l: 180, r: 40, t: 24, b: 40 },
                yaxis: { title: 'Adjektiv', automargin: true, categoryorder: 'array', categoryarray: forestLabels },
                xaxis: { title: `Delta vs Baseline (${baseline || defaultBaseline || ''})` },
              }}
            />
          ) : (
            <div>Keine Daten für Forest-Plot.</div>
          )) : (<div>Bitte Kategorie für Forest auswählen.</div>)}
        </Grid.Col>
      </Grid>
    </Card>
  );
}
