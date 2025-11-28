import { Alert, Button, Card, Grid, Group, Spoiler, Text, Title, MultiSelect, Progress, Select } from '@mantine/core';
import { useEffect, useState } from 'react';
import { Link, useParams } from '@tanstack/react-router';
import { ChartPanel } from '../../components/ChartPanel';
import { useRunDeltas, useRunMetrics, useRun, useRunMissing, useRunOrderMetrics, useRunForests, useRunWarmup, useRunAllMeans, useRunAllDeltas } from './hooks';
import { useStartBenchmark, useBenchmarkStatus } from '../datasets/hooks';
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

const BASE_WARM_STEP_LABELS: Record<string, string> = {
  metrics: 'Metriken',
  missing: 'Fehlende Kombinationen',
  order_metrics: 'Order-Metriken',
};

function formatAttrLabel(key: string | undefined) {
  if (!key) return '';
  return ATTRS.find((x) => x.value === key)?.label || key;
}

function formatWarmStepName(name: string) {
  if (BASE_WARM_STEP_LABELS[name]) return BASE_WARM_STEP_LABELS[name];
  if (name.startsWith('means:')) {
    return `Mittelwerte (${formatAttrLabel(name.split(':')[1])})`;
  }
  if (name.startsWith('deltas:')) {
    const parts = name.split(':');
    const attr = formatAttrLabel(parts[1]);
    if (parts.length > 2) {
      return `Deltas (${attr} → ${parts.slice(2).join(' · ')})`;
    }
    return `Deltas (${attr})`;
  }
  if (name.startsWith('forest:')) {
    return `Forest Plot (${formatAttrLabel(name.split(':')[1])})`;
  }
  return name;
}

function formatDuration(ms?: number | null) {
  if (typeof ms !== 'number' || !Number.isFinite(ms)) return '–';
  return `${(ms / 1000).toFixed(1)} s`;
}

export function RunDetailPage() {
  const { runId } = useParams({ from: '/runs/$runId' });
  const idNum = Number(runId);
  const { data: run, isLoading: isLoadingRun } = useRun(idNum);
  const warmup = useRunWarmup(idNum);
  const warmStatus = warmup.status.data;
  const warmState = warmStatus?.status ?? (warmup.status.isError ? 'error' : warmup.status.isLoading ? 'running' : 'idle');
  const warmReady = ['done', 'done_with_errors', 'error'].includes(warmState);
  const warmLoading = !warmReady;
  const warmSteps = warmStatus?.steps || [];
  const warmRunningStep = warmSteps.find((s) => s.status === 'running');
  const warmCurrentStepLabel = warmRunningStep
    ? formatWarmStepName(warmRunningStep.name)
    : warmStatus?.current_step
      ? formatWarmStepName(warmStatus.current_step)
      : null;
  const warmStepErrors = warmSteps.filter((s) => s.status === 'error');
  const warmStepErrorMessage = warmStepErrors.length
    ? warmStepErrors.map((s) => `${formatWarmStepName(s.name)}: ${s.error ?? 'Fehler'}`).join(' • ')
    : null;
  const warmupErrorMessage =
    (warmup.start.isError ? ((warmup.start.error as any)?.message ?? String(warmup.start.error ?? 'Fehler')) : null) ||
    (warmup.status.isError ? ((warmup.status.error as any)?.message ?? String(warmup.status.error ?? 'Fehler')) : null) ||
    warmStatus?.error ||
    warmStepErrorMessage ||
    null;
  const { data: metrics, isLoading: loadingMetrics, isError: errorMetrics, error: metricsError } = useRunMetrics(idNum, { enabled: warmReady });
  const { data: missing, isLoading: loadingMissing } = useRunMissing(idNum, { enabled: warmReady });
  const startBench = useStartBenchmark();
  const benchStatus = useBenchmarkStatus(idNum);
  const order = useRunOrderMetrics(idNum, { enabled: warmReady });
  const benchDone = typeof benchStatus.data?.done === 'number' ? benchStatus.data.done : null;
  const benchTotal = typeof benchStatus.data?.total === 'number' ? benchStatus.data.total : null;
  const benchPct = typeof benchStatus.data?.pct === 'number'
    ? benchStatus.data.pct
    : benchDone !== null && benchTotal ? (benchDone / Math.max(benchTotal, 1)) * 100 : null;

  // grade helpers moved into ./components/Grades
  const [attr, setAttr] = useState<string>('gender');
  const availableCats = metrics?.attributes?.[attr]?.categories || [];
  const defaultBaseline = metrics?.attributes?.[attr]?.baseline || undefined;
  const [baseline, setBaseline] = useState<string | undefined>(defaultBaseline);
  const [targets, setTargets] = useState<string[]>([]);
  const traitCategorySummary = metrics?.trait_categories?.summary || [];
  const traitCategoryOptions = traitCategorySummary.map((c) => c.category);
  const [traitCategory, setTraitCategory] = useState<string>('__all');
  const traitCategoryFilter = traitCategory === '__all' ? undefined : traitCategory;
  const attrLabel = ATTRS.find((x) => x.value === attr)?.label || attr;

  const liveStatus = (benchStatus.data?.status || '').toLowerCase();
  // Only truly active statuses - 'partial' means incomplete but not running
  const isActive = ['queued', 'running', 'cancelling'].includes(liveStatus);

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
  useEffect(() => {
    if (traitCategoryFilter && !traitCategoryOptions.includes(traitCategoryFilter)) {
      setTraitCategory('__all');
    }
  }, [traitCategoryOptions.join(','), traitCategoryFilter]);

  const { data: deltas, isLoading: loadingDeltas, isError: errorDeltas, error: deltasError } = useRunDeltas(idNum, attr, baseline, { enabled: warmReady, traitCategory: traitCategoryFilter });
  const forestsQueries = useRunForests(idNum, attr, baseline, targets, { enabled: warmReady, traitCategory: traitCategoryFilter });
  const loadingForest = forestsQueries.length > 0 ? forestsQueries.some((q) => q.isLoading) : false;
  const errorForest = forestsQueries.length > 0 ? forestsQueries.some((q) => q.isError) : false;
  const forestError = forestsQueries.find((q) => q.isError)?.error as any;

  // AGGREGATED CALLS
  const { data: allMeans, isLoading: loadingAllMeans, isError: errorAllMeans, error: allMeansError } = useRunAllMeans(idNum, { enabled: warmReady });
  const { data: allDeltas, isLoading: loadingAllDeltas, isError: errorAllDeltas, error: allDeltasError } = useRunAllDeltas(idNum, { enabled: warmReady });

  const meansData = [
    { a: 'gender', q: { data: { rows: allMeans?.data?.gender || [] }, isLoading: loadingAllMeans, isError: errorAllMeans, error: allMeansError } },
    { a: 'origin_subregion', q: { data: { rows: allMeans?.data?.origin_subregion || [] }, isLoading: loadingAllMeans, isError: errorAllMeans, error: allMeansError } },
    { a: 'religion', q: { data: { rows: allMeans?.data?.religion || [] }, isLoading: loadingAllMeans, isError: errorAllMeans, error: allMeansError } },
    { a: 'migration_status', q: { data: { rows: allMeans?.data?.migration_status || [] }, isLoading: loadingAllMeans, isError: errorAllMeans, error: allMeansError } },
    { a: 'sexuality', q: { data: { rows: allMeans?.data?.sexuality || [] }, isLoading: loadingAllMeans, isError: errorAllMeans, error: allMeansError } },
    { a: 'marriage_status', q: { data: { rows: allMeans?.data?.marriage_status || [] }, isLoading: loadingAllMeans, isError: errorAllMeans, error: allMeansError } },
    { a: 'education', q: { data: { rows: allMeans?.data?.education || [] }, isLoading: loadingAllMeans, isError: errorAllMeans, error: allMeansError } },
  ];

  const deltasData = [
    { a: 'gender', q: { data: allDeltas?.data?.gender, isLoading: loadingAllDeltas, isError: errorAllDeltas, error: allDeltasError } },
    { a: 'origin_subregion', q: { data: allDeltas?.data?.origin_subregion, isLoading: loadingAllDeltas, isError: errorAllDeltas, error: allDeltasError } },
    { a: 'religion', q: { data: allDeltas?.data?.religion, isLoading: loadingAllDeltas, isError: errorAllDeltas, error: allDeltasError } },
    { a: 'migration_status', q: { data: allDeltas?.data?.migration_status, isLoading: loadingAllDeltas, isError: errorAllDeltas, error: allDeltasError } },
    { a: 'sexuality', q: { data: allDeltas?.data?.sexuality, isLoading: loadingAllDeltas, isError: errorAllDeltas, error: allDeltasError } },
    { a: 'marriage_status', q: { data: allDeltas?.data?.marriage_status, isLoading: loadingAllDeltas, isError: errorAllDeltas, error: allDeltasError } },
    { a: 'education', q: { data: allDeltas?.data?.education, isLoading: loadingAllDeltas, isError: errorAllDeltas, error: allDeltasError } },
  ];

  if (isActive) {
    const done = benchStatus.data?.done ?? 0;
    const total = benchStatus.data?.total ?? 0;
    return (
      <Card>
        <Title order={2} mb="sm">Benchmark #{runId} läuft…</Title>
        <Text mb="sm">Bitte warten, bis der Benchmark abgeschlossen ist. Den Fortschritt kannst du auch auf der Dataset-Seite verfolgen.</Text>
        <div style={{ width: 360, marginBottom: 12 }}>
          <b>Status:</b> {benchStatus.data?.status} {done}/{total}
          <Progress value={benchStatus.data?.pct ?? 0} mt="xs" />
        </div>
        {run?.dataset?.id ? (
          <Button component={Link} to={'/datasets/$datasetId'} params={{ datasetId: String(run.dataset.id) }}>
            Zur Dataset-Seite
          </Button>
        ) : null}
      </Card>
    );
  }

  // Show loading state while warmup is initializing (not when it's running)
  if (warmState === 'idle' && warmup.status.isLoading) {
    return (
      <Card>
        <Title order={2} mb="sm">Run {runId} wird geladen…</Title>
        <Text>Lade Run-Informationen…</Text>
      </Card>
    );
  }

  const histCounts = metrics?.hist?.counts || (metrics ? metrics.hist.shares.map((p) => Math.round(p * (metrics.n || 0))) : []);
  const palette = ['#3182bd', '#e6550d', '#31a354', '#756bb1'];
  let histBars: Partial<Plotly.Data>[] = [];
  if (metrics) {
    if (!traitCategoryFilter && metrics.trait_categories?.histograms?.length) {
      histBars = metrics.trait_categories.histograms.map((h, idx) => ({
        type: 'bar',
        name: h.category,
        x: h.bins,
        y: h.shares,
        marker: { color: palette[idx % palette.length], opacity: 0.85 },
        hovertemplate: '%{x}: %{y:.0%} (n=%{customdata})',
        customdata: h.counts,
      }));
    } else {
      const selectedHist = traitCategoryFilter
        ? metrics.trait_categories?.histograms?.find((h) => h.category === traitCategoryFilter)
        : undefined;
      const baseHist = selectedHist || {
        bins: metrics.hist.bins,
        shares: metrics.hist.shares,
        counts: histCounts,
      };
      histBars = [
        {
          type: 'bar',
          x: baseHist.bins,
          y: baseHist.shares,
          marker: { color: '#3182bd' },
          text: baseHist.shares.map((p: number, i: number) => `${(p * 100).toFixed(0)}% (n=${baseHist.counts?.[i] ?? 0})`),
          textposition: 'outside',
          hovertemplate: '%{x}: %{y:.0%} (n=%{customdata})',
          customdata: baseHist.counts,
        },
        { type: 'scatter', mode: 'markers', x: baseHist.bins, y: baseHist.counts, yaxis: 'y2', opacity: 0, showlegend: false },
      ];
    }
  }

  // delta bars moved into DeltaBarsPanel; forest rendering handled in MultiForestPlotPanel

  return (
    <Card>
      <Title order={2} mb="md">Run {runId} – Analyse</Title>
      {isLoadingRun ? ('') : run ? (
        <div style={{ marginBottom: '1em' }}>
          <b>Datensatz:</b> <Link to={`/datasets/${run.dataset?.id}`}>{run.dataset?.id}: {run.dataset?.name}</Link> | <b>Modell:</b> {run.model_name} {run.system_prompt ? <span title="Custom System Prompt verwendet" style={{ color: '#fd7e14', fontWeight: 'bold' }}>⚠️</span> : null} | {run.created_at ? (<><b>Erstellt:</b> {new Date(run.created_at).toLocaleDateString()} | <b>Ergebnisse:</b> {run.n_results} | </>) : null}
          {run.include_rationale ? (<><b>Mit Begründung (with_rational):</b> {run.include_rationale ? 'Ja' : 'Nein'} </>) : null}
          {run.system_prompt ? (
            <>
              <br />
              <Spoiler maxHeight={0} showLabel="System Prompt anzeigen" hideLabel="System Prompt verbergen">
                <Text size="sm" c="dimmed" style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', background: '#f8f9fa', padding: '0.5rem', borderRadius: '4px', marginTop: '0.5rem' }}>
                  {run.system_prompt}
                </Text>
              </Spoiler>
            </>
          ) : null}
          {benchStatus.data ? (
            <>
              <br />
              <b>Benchmark-Status:</b> {(benchStatus.data.status || 'unbekannt')}
              {benchDone !== null && benchTotal !== null ? (
                <> · Fortschritt: {benchPct !== null ? `${benchPct.toFixed(1)}%` : ''} ({benchDone}/{benchTotal})</>
              ) : null}
            </>
          ) : null}
          {loadingMissing ? null : (missing && typeof missing.missing === 'number' && typeof missing.total === 'number' ? (
            <>
              <br />
              <Text size="sm">
                <b>Ergebnisse:</b> {missing.total - missing.missing}/{missing.total}
                {missing.failed && missing.failed > 0 ? (
                  <span style={{ color: 'var(--mantine-color-orange-6)', marginLeft: 8 }}>
                    ({missing.failed} fehlgeschlagen nach max. Versuchen)
                  </span>
                ) : null}
              </Text>
              {missing.failed && missing.failed > 0 && missing.missing === 0 ? (
                <Text size="xs" c="dimmed" mt={4}>
                  Hinweis: {missing.failed} Items konnten auch nach 3 Versuchen nicht erfolgreich verarbeitet werden und werden als fehlgeschlagen markiert. Sie fließen in die Gesamtzahl ein, aber nicht in die Auswertung.
                </Text>
              ) : null}
              {missing.missing > 0 ? (
                <>
                  <div style={{ marginTop: 6 }}>
                    {missing.samples && missing.samples.length > 0 ? (
                      <>
                        Fehlende Beispiele: {missing.samples.slice(0, 5).map(s => `(${s.persona_uuid.slice(0, 8)}…, ${s.case_id}${s.adjective ? ' · ' + s.adjective : ''})`).join(', ')}
                      </>
                    ) : null}
                  </div>
                  <div style={{ marginTop: 6 }}>
                    <Button size="xs" onClick={async () => {
                      if (!run.dataset?.id) return;
                      try {
                        const rs = await startBench.mutateAsync({ dataset_id: run.dataset.id, resume_run_id: idNum });
                      } catch (e) { }
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
      {metrics?.trait_categories?.summary?.length ? (
        <Card withBorder padding="sm" mb="md">
          <Title order={5}>Trait-Kategorien – Überblick</Title>
          <Text size="sm" c="dimmed">Mittelwerte pro Trait-Kategorie helfen einzuschätzen, ob „sozial“ vs. „Kompetenz“ unterschiedlich bewertet werden. Nutze den Filter über den Diagrammen, um alle Auswertungen darauf einzuschränken.</Text>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginTop: 8 }}>
            {metrics.trait_categories.summary.map((cat) => (
              <div key={cat.category} style={{ minWidth: 180 }}>
                <b>{cat.category}</b>
                <Text size="sm">n={cat.count} · Mittelwert {(cat.mean ?? 0).toFixed(2)}{typeof cat.std === 'number' ? ` · SD ${cat.std.toFixed(2)}` : ''}</Text>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      {/* Versuchsaufbau / Beschreibung */}
      <Card withBorder padding="md" style={{ marginBottom: 12 }}>
        <Title order={4} mb="xs">Versuchsaufbau</Title>
        <Text size="sm" mb="xs">
          Dieser Benchmark evaluiert Modellantworten zu Personas auf einer 5‑Punkte‑Likert‑Skala
          pro Trait (Adjektiv). Höhere Werte bedeuten stärkere Ausprägung der Eigenschaft
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
              Der Forest‑Plot zeigt Unterschiede pro Trait mit Konfidenzintervallen; die Gesamtnadel
              fasst die Effekte über Traits zusammen.
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
      {['running', 'idle'].includes(warmState) ? (
        <Card withBorder padding="md" mb="md">
          <Title order={4} mb="xs">Vorberechnung</Title>
          <Text size="sm" mb="sm">
            {warmState === 'idle'
              ? 'Vorberechnung wird gestartet …'
              : `Aktueller Schritt: ${warmCurrentStepLabel ?? '…'}`}
          </Text>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {warmSteps.length ? (
              warmSteps.map((step, idx) => {
                const status =
                  step.status === 'done'
                    ? `fertig (${formatDuration(step.duration_ms)})`
                    : step.status === 'error'
                      ? 'Fehler'
                      : 'läuft …';
                const color =
                  step.status === 'done' ? '#2ca25f' : step.status === 'error' ? '#d62828' : '#1f77b4';
                return (
                  <div key={`${step.name}-${step.started_at ?? idx}`} style={{ borderLeft: `3px solid ${color}`, paddingLeft: 8 }}>
                    <Group justify="space-between" gap={6}>
                      <Text size="sm">{formatWarmStepName(step.name)}</Text>
                      <Text size="xs" c={color}>{status}</Text>
                    </Group>
                    {step.error && step.status === 'error' ? (
                      <Text size="xs" c="red.7">{step.error}</Text>
                    ) : null}
                  </div>
                );
              })
            ) : (
              <Text size="sm" c="dimmed">Initialisiere …</Text>
            )}
          </div>
        </Card>
      ) : null}
      {warmState === 'done_with_errors' ? (
        <Alert color="yellow" title="Vorberechnung teilweise fehlgeschlagen" mb="md">
          {warmStepErrorMessage || 'Einige Schritte konnten nicht vorbereitet werden. Die Seite lädt Daten live nach.'}
        </Alert>
      ) : null}
      {warmState === 'error' ? (
        <Alert color="red" title="Vorberechnung fehlgeschlagen" mb="md">
          {warmupErrorMessage || 'Die Auswertungen werden live berechnet.'}
        </Alert>
      ) : warmupErrorMessage && warmState === 'done' ? (
        <Alert color="yellow" title="Hinweis" mb="md">
          {warmupErrorMessage}
        </Alert>
      ) : null}
      <AsyncContent isLoading={warmLoading} loadingLabel="Bereite Auswertungen vor…">
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
              <Select
                label="Trait-Kategorie"
                data={[{ value: '__all', label: 'Alle Kategorien' }, ...traitCategoryOptions.map((c) => ({ value: c, label: c }))]}
                value={traitCategory}
                onChange={(val) => setTraitCategory(val ?? '__all')}
                style={{ minWidth: 220 }}
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
                error={meansData.find(({ q }) => q.isError)?.q.error}
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
              {deltasData.map(({ a, q }) => (
                <div key={a} style={{ marginTop: 12 }}>
                  <b>{ATTRS.find(x => x.value === a)?.label || a}</b>
                  <AsyncContent isLoading={q.isLoading} isError={q.isError} error={q.error}>
                    <SignificanceTable rows={q.data?.rows || []} />
                  </AsyncContent>
                </div>
              ))}
            </Card>
          </Grid.Col>

        </Grid>
      </AsyncContent>
    </Card>
  );
}
