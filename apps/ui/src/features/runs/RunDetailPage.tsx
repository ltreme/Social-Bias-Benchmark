import { Button, Card, Grid, Group, Spoiler, Text, Title, MultiSelect } from '@mantine/core';
import { useEffect, useState } from 'react';
import { Link, useParams } from '@tanstack/react-router';
import { ChartPanel } from '../../components/ChartPanel';
import { useRunDeltas, useRunMetrics, useRun, useRunMissing, useRunOrderMetrics, useRunMeans, useRunForests } from './hooks';
import { useStartBenchmark } from '../datasets/hooks';
import { OrderMetricsCard } from './components/OrderMetricsCard';
import { SignificanceTable } from './components/SignificanceTable';
import { AttributeBaselineSelector } from './components/AttributeBaselineSelector';
import { DeltaBarsPanel } from './components/DeltaBarsPanel';
import { MultiForestPlotPanel } from './components/MultiForestPlotPanel';
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
  const [targets, setTargets] = useState<string[]>([]);
  const attrLabel = ATTRS.find((x) => x.value === attr)?.label || attr;

  // keep baseline in sync when attribute changes or metrics load
  useEffect(() => {
    if (!baseline && defaultBaseline) setBaseline(defaultBaseline);
  }, [defaultBaseline]);

  // Auto-select a sensible forest category whenever attribute/baseline changes
  useEffect(() => {
    const cats = availableCats.map((c) => c.category);
    const base = baseline || defaultBaseline;
    if (cats.length === 0) return;
    const current = targets.filter((t) => cats.includes(t) && t !== base);
    if (current.length === targets.length && current.length > 0) return;
    const first = cats.find((c) => c !== base) || cats[0];
    if (!first) return;
    setTargets([first]);
  }, [attr, baseline, defaultBaseline, availableCats.length]);

  const { data: deltas, isLoading: loadingDeltas, isError: errorDeltas, error: deltasError } = useRunDeltas(idNum, attr, baseline);
  const forestsQueries = useRunForests(idNum, attr, baseline, targets);
  const loadingForest = forestsQueries.length > 0 ? forestsQueries.some((q) => q.isLoading) : false;
  const errorForest = forestsQueries.length > 0 ? forestsQueries.some((q) => q.isError) : false;
  const forestError = forestsQueries.find((q) => q.isError)?.error as any;
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

  // delta bars moved into DeltaBarsPanel; forest rendering handled in MultiForestPlotPanel

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

      {/* Versuchsaufbau / Beschreibung */}
      <Card withBorder padding="md" style={{ marginBottom: 12 }}>
        <Title order={4} mb="xs">Versuchsaufbau</Title>
        <Text size="sm" mb="xs">
          Dieser Benchmark evaluiert Modellantworten zu Personas auf einer 5‑Punkte‑Likert‑Skala
          pro Fall (Case) und Adjektiv. Höhere Werte bedeuten stärkere Ausprägung der Eigenschaft
          (1 = gar nicht &lt;adjektiv&gt; … 5 = sehr &lt;adjektiv&gt;).
        </Text>
        <Text size="sm" c="dimmed" mb="xs">
          Datensatz: {run?.dataset?.name ?? '–'}{metrics?.n ? ` · n=${metrics.n}` : ''} · Modell: {run?.model_name}
          {typeof run?.include_rationale === 'boolean' ? ` · Begründungen: ${run.include_rationale ? 'ein' : 'aus'}` : ''}
        </Text>
        <Spoiler maxHeight={0} showLabel="Details anzeigen" hideLabel="Details verbergen">
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            <li>
              Verteilungen und Mittelwerte fassen Bewertungen über alle Antworten zusammen. Die
              „Rating‑Verteilung“ zeigt die Häufigkeit der Skalenwerte.
            </li>
            <li>
              Deltas zeigen Mittelwerts‑Unterschiede zwischen einer Baseline‑Gruppe und einer
              Zielkategorie je Merkmal (z. B. weiblich vs. männlich). Positive Werte bedeuten höhere
              Bewertungen als die Baseline.
            </li>
            <li>
              Der Forest‑Plot zeigt Unterschiede pro Case mit Konfidenzintervallen; die Gesamtnadel
              fasst die Effekte über Cases zusammen.
            </li>
            <li>
              Signifikanz‑Tabellen enthalten p‑Werte, q‑Werte (FDR‑Korrektur) und Cliff’s δ
              (Effektstärke) zur Interpretation der Unterschiede.
            </li>
            <li>
              Die Order‑Metriken oben bewerten Konsistenz und Stabilität von Rangordnungen über
              Paarvergleiche und Wiederholungen.
            </li>
          </ul>
        </Spoiler>
      </Card>
      <Grid>

        <Grid.Col span={{ base: 12 }}>
          <AsyncContent isLoading={order.isLoading} isError={order.isError} error={order.error}>
            <OrderMetricsCard data={order.data} />
          </AsyncContent>
        </Grid.Col>
        
        <Grid.Col span={{ base: 12 }}>
          <Group align="end" mb="sm">
            <AttributeBaselineSelector
              attributes={ATTRS}
              attribute={attr}
              onAttributeChange={(v) => { setAttr(v); setBaseline(undefined); setTargets([]); }}
              categories={availableCats.map((c) => c.category)}
              baseline={baseline}
              defaultBaseline={defaultBaseline}
              onBaselineChange={setBaseline}
            />
            <MultiSelect
              label="Forest: Kategorien"
              data={availableCats.map(c => ({ value: c.category, label: c.category })).filter(c => c.value !== (baseline || defaultBaseline))}
              value={targets}
              onChange={(vals) => setTargets(vals)}
              placeholder="Kategorien wählen"
              searchable
              style={{ minWidth: 280 }}
              maxDropdownHeight={240}
            />
          </Group>
          <Text size="sm" className="print-only" c="dimmed">
            Einstellungen: Merkmal {attrLabel}; Baseline {baseline || defaultBaseline || 'auto'}; Kategorien: {targets.join(', ') || '—'}
          </Text>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <AsyncContent isLoading={loadingDeltas} isError={errorDeltas} error={deltasError}>
            <DeltaBarsPanel deltas={deltas as any} title={`Delta vs. Baseline (${baseline || defaultBaseline || 'auto'})`} />
          </AsyncContent>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          {targets.length > 0 ? (
            <AsyncContent isLoading={loadingForest} isError={errorForest} error={forestError}>
              <MultiForestPlotPanel
                datasets={forestsQueries.map((q, i) => ({ target: targets[i], rows: (q.data as any)?.rows || [], overall: (q.data as any)?.overall }))}
                attr={attr}
                baseline={baseline}
                defaultBaseline={defaultBaseline}
              />
            </AsyncContent>
          ) : (<div>Bitte Kategorie(n) für Forest wählen.</div>)}
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
