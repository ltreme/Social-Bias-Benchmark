import { Button, Card, Grid, Group, Select, Text, Title } from '@mantine/core';
import { useEffect, useState } from 'react';
import { Link, useParams } from '@tanstack/react-router';
import { ChartPanel } from '../../components/ChartPanel';
import { useRunDeltas, useRunForest, useRunMetrics, useRun, useRunMissing, useRunOrderMetrics, useRunMeans } from './hooks';
import { useStartBenchmark } from '../datasets/hooks';
import { OrderMetricsCard } from './components/OrderMetricsCard';
import { SignificanceTable } from './components/SignificanceTable';
import { AttributeBaselineSelector } from './components/AttributeBaselineSelector';
import { DeltaBarsPanel } from './components/DeltaBarsPanel';
import { ForestPlotPanel } from './components/ForestPlotPanel';
import { MeansSummary } from './components/MeansSummary';
import { AsyncContent } from '../../components/AsyncContent';

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
  const { data: metrics, isLoading: loadingMetrics, isError: errorMetrics, error: metricsError } = useRunMetrics(idNum);
  const { data: missing, isLoading: loadingMissing } = useRunMissing(idNum);
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

  const { data: deltas, isLoading: loadingDeltas, isError: errorDeltas, error: deltasError } = useRunDeltas(idNum, attr, baseline);
  const { data: forest, isLoading: loadingForest, isError: errorForest, error: forestError } = useRunForest(idNum, attr, baseline, target);
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

  // delta bars moved into DeltaBarsPanel

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
              {loadingMissing ? null : (missing && typeof missing.missing === 'number' && typeof missing.total === 'number' ? (
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
              ) : null)}
          </div>
      ) : (
          <div style={{ marginBottom: '1em' }}>Run nicht gefunden.</div>
      )}
      <Grid>

        <Grid.Col span={{ base: 12 }}>
          <AsyncContent isLoading={order.isLoading} isError={order.isError} error={order.error}>
            <OrderMetricsCard data={order.data} />
          </AsyncContent>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <AsyncContent isLoading={loadingMetrics} isError={errorMetrics} error={metricsError}>
            <ChartPanel title="Rating-Verteilung" data={histBars} layout={{
              barmode: 'group',
              yaxis: { tickformat: '.0%', rangemode: 'tozero', title: 'Anteil' },
              yaxis2: { overlaying: 'y', side: 'right', title: 'Anzahl', rangemode: 'tozero', showgrid: false },
            }} />
            <Text size="sm" c="dimmed">Skala: 1 = gar nicht &lt;adjektiv&gt; … 5 = sehr &lt;adjektiv&gt;</Text>
          </AsyncContent>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <AttributeBaselineSelector
            attributes={ATTRS}
            attribute={attr}
            onAttributeChange={(v) => { setAttr(v); setBaseline(undefined); setTarget(undefined); }}
            categories={availableCats.map((c) => c.category)}
            baseline={baseline}
            defaultBaseline={defaultBaseline}
            onBaselineChange={setBaseline}
          />
          <AsyncContent isLoading={loadingDeltas} isError={errorDeltas} error={deltasError}>
            <DeltaBarsPanel deltas={deltas as any} title={`Delta vs. Baseline (${baseline || defaultBaseline || 'auto'})`} />
          </AsyncContent>
        </Grid.Col>
        <Grid.Col span={12}>
          <Group align="end" mb="sm">
            <Select label="Forest: Kategorie" data={availableCats.map(c => ({ value: c.category, label: c.category })).filter(c => c.value !== (baseline || defaultBaseline))} value={target} onChange={setTarget} placeholder="Kategorie wählen" searchable />
          </Group>
          {target ? (
            <AsyncContent isLoading={loadingForest} isError={errorForest} error={forestError}>
              <ForestPlotPanel forest={forest as any} attr={attr} baseline={baseline} defaultBaseline={defaultBaseline} />
            </AsyncContent>
          ) : (<div>Bitte Kategorie für Forest auswählen.</div>)}
        </Grid.Col>
        <Grid.Col span={12}>
          <Card withBorder padding="md" style={{ marginBottom: 12 }}>
            <Title order={4}>Mittelwerte pro Merkmal</Title>
            <AsyncContent
              isLoading={meansData.some(({ q }) => q.isLoading)}
              isError={meansData.some(({ q }) => q.isError)}
              error={meansData.find(({ q }) => q.isError)?.error}
            >
              <MeansSummary
                items={meansData.map(({ a, q }) => ({ key: a, rows: q.data?.rows }))}
                getLabel={(key) => ATTRS.find((x) => x.value === key)?.label || key}
              />
            </AsyncContent>
          </Card>
        </Grid.Col>
        <Grid.Col span={12}>
          <Card withBorder padding="md" style={{ marginBottom: 12 }}>
            <Title order={4}>Signifikanz-Tabellen (p, q, Cliff’s δ)</Title>
            {deltasData.map(({a,q}) => (
              <div key={a} style={{ marginTop: 12 }}>
                <b>{ATTRS.find(x=>x.value===a)?.label || a}</b>
                <AsyncContent isLoading={q.isLoading} isError={q.isError} error={q.error}>
                  <SignificanceTable rows={q.data?.rows || []} />
                </AsyncContent>
              </div>
            ))}
          </Card>
        </Grid.Col>

      </Grid>
    </Card>
  );
}
