import { Alert, Badge, Button, Group, Paper, Popover, SimpleGrid, Spoiler, Stack, Text, ThemeIcon, Title, Progress, Tabs, Menu, ActionIcon, Tooltip } from '@mantine/core';
import { IconDownload, IconChartBar, IconAlertTriangle, IconPlayerPlay, IconCheck, IconX, IconFileTypePdf, IconRefresh, IconRobot, IconFileCode } from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from '@tanstack/react-router';
import { useThemedColor } from '../../lib/useThemeColors';
import { 
  useRunMetrics, 
  useRun, 
  useRunMissing, 
  useRunWarmup, 
  useQuickAnalysis, 
  useRunOrderMetrics,
  useRunDeltas,
  useRunForests,
  useRunAllDeltas,
} from './hooks';
import { useStartBenchmark, useBenchmarkStatus } from '../datasets/hooks';
import { AsyncContent } from '../../components/AsyncContent';
import { OverviewTab } from './components/OverviewTab';
import { OrderConsistencyTab } from './components/OrderConsistencyTab';
import { BiasTab } from './components/BiasTab';
import { RunInfoCards } from './components/RunInfoCards';
import { TraitCategorySummary } from './components/TraitCategorySummary';
import { usePdfExport } from './usePdfExport';

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
  const getColor = useThemedColor();
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

  // PDF export
  const { exportToPdf, isExporting, progress: pdfProgress } = usePdfExport();
  
  // Query client für Cache-Invalidierung
  const queryClient = useQueryClient();
  const [isClearingCache, setIsClearingCache] = useState(false);
  
  const clearRunCache = async () => {
    setIsClearingCache(true);
    try {
      // Zuerst Backend-Cache löschen
      const { clearRunCache: clearBackendCache } = await import('./api');
      await clearBackendCache(idNum);
      
      // Dann Frontend-Cache invalidieren
      queryClient.invalidateQueries({ queryKey: ['run', idNum] });
      queryClient.invalidateQueries({ queryKey: ['run-metrics', idNum] });
      queryClient.invalidateQueries({ queryKey: ['run-missing', idNum] });
      queryClient.invalidateQueries({ queryKey: ['run-order-metrics', idNum] });
      queryClient.invalidateQueries({ queryKey: ['run-means', idNum] });
      queryClient.invalidateQueries({ queryKey: ['run-means-all', idNum] });
      queryClient.invalidateQueries({ queryKey: ['run-deltas', idNum] });
      queryClient.invalidateQueries({ queryKey: ['run-deltas-all', idNum] });
      queryClient.invalidateQueries({ queryKey: ['run-forest', idNum] });
      queryClient.invalidateQueries({ queryKey: ['warmup-status', idNum] });
      queryClient.invalidateQueries({ queryKey: ['analysis-status', idNum] });
      queryClient.invalidateQueries({ queryKey: ['quick-analysis', idNum] });
      queryClient.invalidateQueries({ queryKey: ['benchmark-status', idNum] });
      
      // Seite neu laden
      window.location.reload();
    } catch (error) {
      console.error('Failed to clear cache:', error);
      setIsClearingCache(false);
    }
  };

  const warmupErrorMessage =
    (warmup.start.isError ? ((warmup.start.error as any)?.message ?? String(warmup.start.error ?? 'Fehler')) : null) ||
    (warmup.status.isError ? ((warmup.status.error as any)?.message ?? String(warmup.status.error ?? 'Fehler')) : null) ||
    warmStatus?.error ||
    warmStepErrorMessage ||
    null;

  // Core data hooks
  const { data: metrics, isLoading: loadingMetrics, error: metricsError } = useRunMetrics(idNum, { enabled: warmReady });
  const { data: missing, isLoading: loadingMissing } = useRunMissing(idNum, { enabled: warmReady });
  const startBench = useStartBenchmark();
  const benchStatus = useBenchmarkStatus(idNum);
  const order = useRunOrderMetrics(idNum, { enabled: warmReady });
  const benchDone = typeof benchStatus.data?.done === 'number' ? benchStatus.data.done : null;
  const benchTotal = typeof benchStatus.data?.total === 'number' ? benchStatus.data.total : null;
  const benchPct = typeof benchStatus.data?.pct === 'number'
    ? benchStatus.data.pct
    : benchDone !== null && benchTotal ? (benchDone / Math.max(benchTotal, 1)) * 100 : null;

  // Analysis hooks
  const quickAnalysis = useQuickAnalysis(idNum, { enabled: warmReady });

  // Tab state
  const [activeTab, setActiveTab] = useState<string | null>('overview');

  // Bias tab state
  const [attr, setAttr] = useState<string>('gender');
  const availableCats = metrics?.attributes?.[attr]?.categories || [];
  const defaultBaseline = metrics?.attributes?.[attr]?.baseline || undefined;
  const [baseline, setBaseline] = useState<string | undefined>(defaultBaseline);
  const [targets, setTargets] = useState<string[]>([]);

  // Build availableCategories map for all attributes (for SignificanceTableWithFilters)
  const allAttributesCategories: Record<string, Array<{ category: string; count: number; mean: number }>> = {
    gender: metrics?.attributes?.gender?.categories || [],
    age_group: metrics?.attributes?.age_group?.categories || [],
    origin_subregion: metrics?.attributes?.origin_subregion?.categories || [],
    religion: metrics?.attributes?.religion?.categories || [],
    migration_status: metrics?.attributes?.migration_status?.categories || [],
    sexuality: metrics?.attributes?.sexuality?.categories || [],
    marriage_status: metrics?.attributes?.marriage_status?.categories || [],
    education: metrics?.attributes?.education?.categories || [],
  };
  const traitCategorySummary = metrics?.trait_categories?.summary || [];
  const traitCategoryOptions = traitCategorySummary.map((c) => c.category);
  const [traitCategory, setTraitCategory] = useState<string>('__all');
  const traitCategoryFilter = traitCategory === '__all' ? undefined : traitCategory;

  const liveStatus = (benchStatus.data?.status || '').toLowerCase();
  const isActive = ['queued', 'running', 'cancelling'].includes(liveStatus);

  // Keep baseline in sync when attribute changes or metrics load
  useEffect(() => {
    if (!baseline && defaultBaseline) setBaseline(defaultBaseline);
  }, [defaultBaseline, baseline]);

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

  // Bias data hooks
  const { data: deltas, isLoading: loadingDeltas, error: deltasError } = useRunDeltas(idNum, attr, baseline, { enabled: warmReady, traitCategory: traitCategoryFilter });
  const forestsQueries = useRunForests(idNum, attr, baseline, targets, { enabled: warmReady, traitCategory: traitCategoryFilter });

  // Aggregated data
  const { data: allDeltas, isLoading: loadingAllDeltas, isError: errorAllDeltas, error: allDeltasError } = useRunAllDeltas(idNum, { enabled: warmReady });
  
  // Radar chart data for grid view - load data for each trait category
  const radarCategory1 = traitCategoryOptions[0]; // e.g., "kompetenz"
  const radarCategory2 = traitCategoryOptions[1]; // e.g., "sozial"
  
  const { data: radarDeltasAll, isLoading: loadingRadarAll } = useRunAllDeltas(idNum, { enabled: warmReady });
  const { data: radarDeltasCat1, isLoading: loadingRadarCat1 } = useRunAllDeltas(idNum, { enabled: warmReady && !!radarCategory1, traitCategory: radarCategory1 });
  const { data: radarDeltasCat2, isLoading: loadingRadarCat2 } = useRunAllDeltas(idNum, { enabled: warmReady && !!radarCategory2, traitCategory: radarCategory2 });

  const deltasData = [
    { a: 'gender', q: { data: allDeltas?.data?.gender, isLoading: loadingAllDeltas, isError: errorAllDeltas, error: allDeltasError } },
    { a: 'age_group', q: { data: allDeltas?.data?.age_group, isLoading: loadingAllDeltas, isError: errorAllDeltas, error: allDeltasError } },
    { a: 'origin_subregion', q: { data: allDeltas?.data?.origin_subregion, isLoading: loadingAllDeltas, isError: errorAllDeltas, error: allDeltasError } },
    { a: 'religion', q: { data: allDeltas?.data?.religion, isLoading: loadingAllDeltas, isError: errorAllDeltas, error: allDeltasError } },
    { a: 'migration_status', q: { data: allDeltas?.data?.migration_status, isLoading: loadingAllDeltas, isError: errorAllDeltas, error: allDeltasError } },
    { a: 'sexuality', q: { data: allDeltas?.data?.sexuality, isLoading: loadingAllDeltas, isError: errorAllDeltas, error: allDeltasError } },
    { a: 'marriage_status', q: { data: allDeltas?.data?.marriage_status, isLoading: loadingAllDeltas, isError: errorAllDeltas, error: allDeltasError } },
    { a: 'education', q: { data: allDeltas?.data?.education, isLoading: loadingAllDeltas, isError: errorAllDeltas, error: allDeltasError } },
  ];

  // Helper to build deltasData array from raw API response
  const buildDeltasData = (data: typeof radarDeltasAll, isLoading: boolean) => [
    { a: 'gender', q: { data: data?.data?.gender, isLoading, isError: false, error: null } },
    { a: 'age_group', q: { data: data?.data?.age_group, isLoading, isError: false, error: null } },
    { a: 'origin_subregion', q: { data: data?.data?.origin_subregion, isLoading, isError: false, error: null } },
    { a: 'religion', q: { data: data?.data?.religion, isLoading, isError: false, error: null } },
    { a: 'migration_status', q: { data: data?.data?.migration_status, isLoading, isError: false, error: null } },
    { a: 'sexuality', q: { data: data?.data?.sexuality, isLoading, isError: false, error: null } },
    { a: 'marriage_status', q: { data: data?.data?.marriage_status, isLoading, isError: false, error: null } },
    { a: 'education', q: { data: data?.data?.education, isLoading, isError: false, error: null } },
  ];

  // Radar chart category map for grid display
  const radarCategoryDeltasMap: Record<string, typeof deltasData> = {
    '__all': buildDeltasData(radarDeltasAll, loadingRadarAll),
    ...(radarCategory1 ? { [radarCategory1]: buildDeltasData(radarDeltasCat1, loadingRadarCat1) } : {}),
    ...(radarCategory2 ? { [radarCategory2]: buildDeltasData(radarDeltasCat2, loadingRadarCat2) } : {}),
  };

  const radarLoadingStates: Record<string, boolean> = {
    '__all': loadingRadarAll,
    ...(radarCategory1 ? { [radarCategory1]: loadingRadarCat1 } : {}),
    ...(radarCategory2 ? { [radarCategory2]: loadingRadarCat2 } : {}),
  };

  if (isActive) {
    const done = benchStatus.data?.done ?? 0;
    const total = benchStatus.data?.total ?? 0;
    return (
      <Paper p="lg" withBorder>
        <Group gap="xs" mb="md">
          <ThemeIcon size="lg" radius="md" variant="light" color="blue">
            <IconPlayerPlay size={20} />
          </ThemeIcon>
          <Title order={2}>Benchmark #{runId} läuft…</Title>
        </Group>
        <Text mb="md" c="dimmed">Bitte warten, bis der Benchmark abgeschlossen ist.</Text>
        <Paper p="md" bg={getColor('blue').bg} radius="md" mb="md" style={{ maxWidth: 400 }}>
          <Group justify="space-between" mb="xs">
            <Text size="sm" fw={500}>Fortschritt</Text>
            <Text size="sm" c={getColor('blue').text}>{done}/{total}</Text>
          </Group>
          <Progress value={benchStatus.data?.pct ?? 0} size="lg" radius="xl" />
        </Paper>
        {run?.dataset?.id ? (
          <Button component={Link} to={`/datasets/${run.dataset.id}`} variant="light">
            Zur Dataset-Seite
          </Button>
        ) : null}
      </Paper>
    );
  }

  // Show loading state while warmup is initializing (not when it's running)
  if (warmState === 'idle' && warmup.status.isLoading) {
    return (
      <Paper p="lg" withBorder>
        <Title order={2} mb="sm">Run {runId} wird geladen…</Title>
        <Text c="dimmed">Lade Run-Informationen…</Text>
      </Paper>
    );
  }

  return (
    <Stack gap="md">
      {/* Header */}
      <Group justify="space-between" align="center">
        <Group gap="sm" align="center">
          <Title order={3}>Run {runId}</Title>
          {benchStatus.data?.status && (
            <Badge 
              size="md" 
              color={benchStatus.data.status === 'done' ? 'green' : benchStatus.data.status === 'running' ? 'blue' : 'gray'}
              variant="light"
            >
              {benchStatus.data.status}
            </Badge>
          )}
          {run?.created_at && (
            <Text size="sm" c="dimmed" ml="xs">
              {new Date(run.created_at).toLocaleDateString('de-DE', { day: '2-digit', month: 'long', year: 'numeric' })}
            </Text>
          )}
        </Group>
        <Group gap="xs">
          <Tooltip label="Cache leeren">
            <ActionIcon
              variant="light"
              color="gray"
              size="lg"
              onClick={clearRunCache}
              loading={isClearingCache}
              data-print-hide
            >
              <IconRefresh size={20} />
            </ActionIcon>
          </Tooltip>
          
          <Tooltip label="PDF-Report herunterladen">
            <ActionIcon
              variant="light"
              color="blue"
              size="lg"
              onClick={() => run && exportToPdf({
                run,
                metrics,
                orderMetrics: order.data,
                allDeltas: allDeltas?.data,
              }, {
                filename: `run_${runId}_analyse.pdf`,
              })}
              loading={isExporting}
              disabled={isExporting || warmLoading || !run}
              data-print-hide
            >
              <IconFileTypePdf size={20} />
            </ActionIcon>
          </Tooltip>

          <Tooltip label="Export Run Data (JSON)">
            <ActionIcon
              variant="light"
              color="violet"
              size="lg"
              component="a"
              href={`${import.meta.env.VITE_API_BASE_URL || ''}/runs/${runId}/export/json`}
              download={`run_${runId}_data.json`}
              data-print-hide
            >
              <IconDownload size={20} />
            </ActionIcon>
          </Tooltip>

          <Tooltip label="Logs herunterladen (JSON)">
            <ActionIcon
              variant="light"
              color="gray"
              size="lg"
              component="a"
              href={`${import.meta.env.VITE_API_BASE_URL || ''}/runs/${runId}/logs`}
              download={`run_${runId}_logs.json`}
              data-print-hide
            >
              <IconFileCode size={20} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      {isLoadingRun ? null : run ? (
        <>
          {/* Info Cards Grid */}
          <RunInfoCards run={run} benchDone={benchDone} benchTotal={benchTotal} />

          {/* Progress Bar (if not complete) */}
          {benchDone !== null && benchTotal !== null && benchDone < benchTotal && (
            <Paper p="md" withBorder>
              <Group justify="space-between" mb="xs">
                <Text size="sm" fw={500}>Fortschritt</Text>
                <Text size="sm" c="dimmed">{benchPct?.toFixed(1)}%</Text>
              </Group>
              <Progress value={benchPct ?? 0} size="md" radius="xl" />
            </Paper>
          )}

          {/* Missing/Failed Results Info */}
          {!loadingMissing && missing && typeof missing.missing === 'number' && typeof missing.total === 'number' && (
            (missing.missing > 0 || (missing.failed && missing.failed > 0)) ? (
              <Alert 
                color={missing.missing > 0 ? 'blue' : 'yellow'} 
                icon={missing.missing > 0 ? <IconPlayerPlay size={18} /> : <IconAlertTriangle size={18} />}
                title={missing.missing > 0 ? `${missing.missing} fehlende Ergebnisse` : `${missing.failed} fehlgeschlagene Versuche`}
              >
                {missing.missing > 0 ? (
                  <Stack gap="xs">
                    <Text size="sm">
                      {missing.total - missing.missing} von {missing.total} Ergebnissen vorhanden.
                      {missing.failed && missing.failed > 0 && ` (${missing.failed} fehlgeschlagen nach max. Versuchen)`}
                    </Text>
                    {missing.samples && missing.samples.length > 0 && (
                      <Text size="xs" c="dimmed">
                        Beispiele: {missing.samples.slice(0, 3).map(s => `${s.persona_uuid.slice(0, 8)}…`).join(', ')}
                      </Text>
                    )}
                    <Button 
                      size="xs" 
                      variant="light"
                      leftSection={<IconPlayerPlay size={14} />}
                      onClick={async () => {
                        if (!run.dataset?.id) return;
                        try {
                          await startBench.mutateAsync({ dataset_id: run.dataset.id, resume_run_id: idNum });
                        } catch (e) { }
                      }}
                    >
                      Run fortsetzen
                    </Button>
                  </Stack>
                ) : (
                  <Text size="sm">
                    {missing.failed} Items konnten auch nach 3 Versuchen nicht erfolgreich verarbeitet werden.
                  </Text>
                )}
              </Alert>
            ) : null
          )}
          {/* Trait Categories Summary */}
          {metrics?.trait_categories?.summary?.length ? (
            <TraitCategorySummary categories={metrics.trait_categories.summary} />
          ) : null}
        </>
      ) : (
        <Paper p="md" withBorder>
          <Text c="dimmed">Run nicht gefunden.</Text>
        </Paper>
      )}
      {['running', 'idle'].includes(warmState) ? (
        <Paper p="md" withBorder>
          <Group gap="xs" mb="sm">
            <ThemeIcon size="md" radius="md" variant="light" color="blue">
              <IconPlayerPlay size={16} />
            </ThemeIcon>
            <Title order={5}>Vorberechnung</Title>
          </Group>
          <Text size="sm" c="dimmed" mb="sm">
            {warmState === 'idle'
              ? 'Vorberechnung wird gestartet …'
              : `Aktueller Schritt: ${warmCurrentStepLabel ?? '…'}`}
          </Text>
          <Stack gap={6}>
            {warmSteps.length ? (
              warmSteps.map((step, idx) => {
                const isDone = step.status === 'done';
                const isError = step.status === 'error';
                const colorKey = isDone ? 'teal' : isError ? 'red' : 'blue';
                const colorSet = getColor(colorKey);
                return (
                  <Paper key={`${step.name}-${step.started_at ?? idx}`} p="xs" bg={colorSet.bg} radius="sm">
                    <Group justify="space-between" gap={6}>
                      <Group gap="xs">
                        <ThemeIcon size="sm" radius="xl" variant="light" color={colorKey}>
                          {isDone ? <IconCheck size={12} /> : isError ? <IconX size={12} /> : <IconPlayerPlay size={12} />}
                        </ThemeIcon>
                        <Text size="sm">{formatWarmStepName(step.name)}</Text>
                      </Group>
                      <Text size="xs" c={colorSet.text}>
                        {isDone ? formatDuration(step.duration_ms) : isError ? 'Fehler' : 'läuft …'}
                      </Text>
                    </Group>
                    {step.error && isError && (
                      <Text size="xs" c={getColor('red').text} mt={4}>{step.error}</Text>
                    )}
                  </Paper>
                );
              })
            ) : (
              <Text size="sm" c="dimmed">Initialisiere …</Text>
            )}
          </Stack>
        </Paper>
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
        <Tabs value={activeTab} onChange={(v) => setActiveTab(v || 'overview')}>
          <Tabs.List mb="md">
            <Tabs.Tab value="overview">Übersicht</Tabs.Tab>
            <Tabs.Tab value="order">Order-Consistency</Tabs.Tab>
            <Tabs.Tab value="bias">Bias-Analyse</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="overview">
            <OverviewTab
              quickAnalysis={quickAnalysis.data}
              isLoadingQuick={quickAnalysis.isLoading}
              metrics={metrics}
              isLoadingMetrics={loadingMetrics}
              metricsError={metricsError}
              traitCategoryFilter={traitCategoryFilter}
              runId={idNum}
              radarTraitCategories={traitCategoryOptions}
              radarCategoryDeltasMap={radarCategoryDeltasMap}
              radarLoadingStates={radarLoadingStates}
            />
          </Tabs.Panel>

          <Tabs.Panel value="order">
            <OrderConsistencyTab
              orderMetrics={order.data}
              isLoadingOrder={order.isLoading}
              orderError={order.error}
            />
          </Tabs.Panel>

          <Tabs.Panel value="bias">
            <BiasTab
              runId={idNum}
              attribute={attr}
              onAttributeChange={(v) => { setAttr(v); setBaseline(undefined); setTargets([]); }}
              availableCategories={availableCats}
              baseline={baseline}
              defaultBaseline={defaultBaseline}
              onBaselineChange={(v) => setBaseline(v ?? undefined)}
              targets={targets}
              onTargetsChange={setTargets}
              traitCategoryOptions={traitCategoryOptions}
              traitCategory={traitCategory}
              onTraitCategoryChange={(v) => setTraitCategory(v)}
              deltas={deltas}
              isLoadingDeltas={loadingDeltas}
              deltasError={deltasError}
              forestsQueries={forestsQueries}
              deltasData={deltasData}
              allAttributesCategories={allAttributesCategories}
            />
          </Tabs.Panel>
        </Tabs>
      </AsyncContent>
    </Stack>
  );
}
