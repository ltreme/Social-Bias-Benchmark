import { Card, Grid, Paper, Text, Title, Badge, Group, Stack, ThemeIcon, SimpleGrid, Tooltip, ActionIcon } from '@mantine/core';
import { IconChartBar, IconAlertTriangle, IconArrowsSort, IconTarget, IconInfoCircle } from '@tabler/icons-react';
import { ChartPanel } from '../../../components/ChartPanel';
import { AsyncContent } from '../../../components/AsyncContent';
import { BiasRadarGrid } from './BiasRadarChart';
import { useThemedColor } from '../../../lib/useThemeColors';
import type { QuickAnalysis, RunMetrics, RunDeltas } from '../api';

type DeltasQueryResult = {
  data?: RunDeltas;
  isLoading: boolean;
  isError: boolean;
  error?: any;
};

type DeltasData = Array<{ a: string; q: DeltasQueryResult }>;

type OverviewTabProps = {
    quickAnalysis?: QuickAnalysis | null;
    isLoadingQuick: boolean;
    metrics?: RunMetrics | null;
    isLoadingMetrics: boolean;
    metricsError?: any;
    traitCategoryFilter?: string;
    /** Run ID for radar chart */
    runId?: number;
    /** Available trait categories for radar chart */
    radarTraitCategories?: string[];
    /** Map of category -> deltasData for radar grid */
    radarCategoryDeltasMap?: Record<string, DeltasData>;
    /** Loading states per category */
    radarLoadingStates?: Record<string, boolean>;
};

function formatRating(value: number | null | undefined): string {
    if (value === null || value === undefined) return '–';
    return value.toFixed(2);
}

function formatPercent(value: number | null | undefined): string {
    if (value === null || value === undefined) return '–';
    return `${(value * 100).toFixed(1)}%`;
}

export function OverviewTab({
    quickAnalysis,
    isLoadingQuick,
    metrics,
    isLoadingMetrics,
    metricsError,
    traitCategoryFilter,
    runId,
    radarTraitCategories,
    radarCategoryDeltasMap,
    radarLoadingStates,
}: OverviewTabProps) {
    const getColor = useThemedColor();
    const orderSample = quickAnalysis?.order_consistency_sample;

    // Histogram bars from metrics
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

    return (
        <Stack gap="md">
            {/* Quick Analysis Summary */}
            <Card withBorder padding="md">
                <Title order={4} mb="md">Quick-Check</Title>
                <AsyncContent isLoading={isLoadingQuick} loadingLabel="Lade Quick-Analyse...">
                    {quickAnalysis ? (
                        <SimpleGrid cols={{ base: 2, md: 4 }} spacing="md">
                            {/* Ergebnisse */}
                            <Paper p="md" bg={getColor('blue').bg} radius="md">
                                <Group justify="space-between" align="flex-start" mb="xs">
                                    <ThemeIcon size={44} radius="md" variant="light" color="blue">
                                        <IconChartBar size={24} />
                                    </ThemeIcon>
                                    <Tooltip 
                                        label="Gesamtzahl der erfolgreich verarbeiteten Antworten des Modells"
                                        multiline
                                        w={220}
                                        withArrow
                                    >
                                        <ActionIcon variant="subtle" color="gray" size="sm">
                                            <IconInfoCircle size={16} />
                                        </ActionIcon>
                                    </Tooltip>
                                </Group>
                                <Text size="xs" c={getColor('blue').label} tt="uppercase" fw={600}>Ergebnisse</Text>
                                <Text size="xl" fw={700} c={getColor('blue').text}>
                                    {quickAnalysis.total_results.toLocaleString('de-DE')}
                                </Text>
                            </Paper>

                            {/* Fehlerrate */}
                            <Paper p="md" bg={quickAnalysis.error_count > 0 ? getColor('orange').bg : getColor('teal').bg} radius="md">
                                <Group justify="space-between" align="flex-start" mb="xs">
                                    <ThemeIcon 
                                        size={44} 
                                        radius="md" 
                                        variant="light" 
                                        color={quickAnalysis.error_count > 0 ? 'orange' : 'teal'}
                                    >
                                        <IconAlertTriangle size={24} />
                                    </ThemeIcon>
                                    <Tooltip 
                                        label="Anteil der Anfragen, bei denen das Modell keine gültige Antwort liefern konnte (z.B. Parsing-Fehler, Timeout)"
                                        multiline
                                        w={250}
                                        withArrow
                                    >
                                        <ActionIcon variant="subtle" color="gray" size="sm">
                                            <IconInfoCircle size={16} />
                                        </ActionIcon>
                                    </Tooltip>
                                </Group>
                                <Text size="xs" c={quickAnalysis.error_count > 0 ? getColor('orange').label : getColor('teal').label} tt="uppercase" fw={600}>Fehlerrate</Text>
                                <Group gap={6} align="baseline">
                                    <Text 
                                        size="xl" 
                                        fw={700} 
                                        c={quickAnalysis.error_count > 0 ? getColor('orange').text : getColor('teal').text}
                                    >
                                        {formatPercent(quickAnalysis.error_rate)}
                                    </Text>
                                    {quickAnalysis.error_count > 0 && (
                                        <Badge color="orange" size="sm" variant="filled">
                                            {quickAnalysis.error_count}
                                        </Badge>
                                    )}
                                </Group>
                            </Paper>

                            {/* Order RMA */}
                            <Paper p="md" bg={getColor('violet').bg} radius="md">
                                <Group justify="space-between" align="flex-start" mb="xs">
                                    <ThemeIcon size={44} radius="md" variant="light" color="violet">
                                        <IconArrowsSort size={24} />
                                    </ThemeIcon>
                                    <Tooltip 
                                        label="Rank-biserial Moving Average: Misst die Konsistenz der Rangordnung über Paarvergleiche. Werte nahe 1 bedeuten hohe Übereinstimmung."
                                        multiline
                                        w={280}
                                        withArrow
                                    >
                                        <ActionIcon variant="subtle" color="gray" size="sm">
                                            <IconInfoCircle size={16} />
                                        </ActionIcon>
                                    </Tooltip>
                                </Group>
                                <Text size="xs" c={getColor('violet').label} tt="uppercase" fw={600}>
                                    Order RMA{orderSample?.is_sample ? ' (Sample)' : ''}
                                </Text>
                                <Text size="xl" fw={700} c={getColor('violet').text}>
                                    {formatRating(orderSample?.rma)}
                                </Text>
                            </Paper>

                            {/* Order MAE */}
                            <Paper p="md" bg={getColor('violet').bg} radius="md">
                                <Group justify="space-between" align="flex-start" mb="xs">
                                    <ThemeIcon size={44} radius="md" variant="light" color="grape">
                                        <IconTarget size={24} />
                                    </ThemeIcon>
                                    <Tooltip 
                                        label="Mean Absolute Error: Durchschnittliche Abweichung der Bewertungen bei wiederholten Anfragen. Niedrigere Werte = stabilere Antworten."
                                        multiline
                                        w={280}
                                        withArrow
                                    >
                                        <ActionIcon variant="subtle" color="gray" size="sm">
                                            <IconInfoCircle size={16} />
                                        </ActionIcon>
                                    </Tooltip>
                                </Group>
                                <Text size="xs" c={getColor('violet').label} tt="uppercase" fw={600}>
                                    Order MAE{orderSample?.is_sample ? ' (Sample)' : ''}
                                </Text>
                                <Text size="xl" fw={700} c={getColor('violet').text}>
                                    {formatRating(orderSample?.mae)}
                                </Text>
                            </Paper>
                        </SimpleGrid>
                    ) : (
                        <Text c="dimmed">Keine Quick-Analyse verfügbar</Text>
                    )}
                </AsyncContent>
            </Card>

            {/* Bias Radar Chart Grid - positioned prominently after Quick-Check */}
            {runId && radarTraitCategories && radarTraitCategories.length > 0 && radarCategoryDeltasMap && (
                <BiasRadarGrid 
                    runId={runId}
                    traitCategories={radarTraitCategories}
                    categoryDeltasMap={radarCategoryDeltasMap}
                    loadingStates={radarLoadingStates}
                />
            )}

            {/* Detailed Rating Distribution Chart */}
            <Card withBorder padding="md">
                <Title order={4} mb="sm">Rating-Verteilung</Title>
                <AsyncContent isLoading={isLoadingMetrics} isError={!!metricsError} error={metricsError}>
                    {metrics ? (
                        <>
                            <ChartPanel 
                                title="" 
                                data={histBars} 
                                layout={{
                                    barmode: 'group',
                                    yaxis: { tickformat: '.0%', rangemode: 'tozero', title: { text: 'Anteil' } },
                                    yaxis2: { overlaying: 'y', side: 'right', title: { text: 'Anzahl' }, rangemode: 'tozero', showgrid: false },
                                }} 
                            />
                            <Text size="sm" c="dimmed">Skala: 1 = gar nicht &lt;adjektiv&gt; … 5 = sehr &lt;adjektiv&gt;</Text>
                        </>
                    ) : null}
                </AsyncContent>
            </Card>

            {/* Trait Categories Overview */}
            {metrics?.trait_categories?.summary?.length ? (
                <Card withBorder padding="md">
                    <Title order={4} mb="sm">Trait-Kategorien – Überblick</Title>
                    <Text size="sm" c="dimmed" mb="sm">
                        Mittelwerte pro Trait-Kategorie helfen einzuschätzen, ob „sozial" vs. „Kompetenz" unterschiedlich bewertet werden.
                    </Text>
                    <Grid>
                        {metrics.trait_categories.summary.map((cat) => (
                            <Grid.Col key={cat.category} span={{ base: 6, md: 4 }}>
                                <Card withBorder padding="sm">
                                    <Text fw={600}>{cat.category}</Text>
                                    <Text size="sm">n={cat.count}</Text>
                                    <Text size="sm">
                                        Mittelwert: {cat.mean?.toFixed(2)}
                                        {typeof cat.std === 'number' ? ` (SD ${cat.std.toFixed(2)})` : ''}
                                    </Text>
                                </Card>
                            </Grid.Col>
                        ))}
                    </Grid>
                </Card>
            ) : null}
        </Stack>
    );
}
