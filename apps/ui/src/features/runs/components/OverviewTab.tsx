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
            <Card withBorder padding="sm">
                <Title order={5} mb="sm">Quick-Check</Title>
                <AsyncContent isLoading={isLoadingQuick} loadingLabel="Lade Quick-Analyse...">
                    {quickAnalysis ? (
                        <SimpleGrid cols={{ base: 2, md: 4 }} spacing="sm">
                            {/* Ergebnisse */}
                            <Paper p="sm" bg={getColor('blue').bg} radius="md">
                                <Group gap="xs" wrap="nowrap" justify="space-between">
                                    <Group gap="xs" wrap="nowrap">
                                        <ThemeIcon size="md" radius="md" variant="light" color="blue">
                                            <IconChartBar size={16} />
                                        </ThemeIcon>
                                        <div>
                                            <Text size="xs" c={getColor('blue').label} tt="uppercase" fw={600} lh={1}>Ergebnisse</Text>
                                            <Text size="md" fw={700} c={getColor('blue').text} lh={1.2}>
                                                {quickAnalysis.total_results.toLocaleString('de-DE')}
                                            </Text>
                                        </div>
                                    </Group>
                                    <Tooltip 
                                        label="Gesamtzahl der erfolgreich verarbeiteten Antworten des Modells"
                                        multiline
                                        w={220}
                                        withArrow
                                    >
                                        <ActionIcon variant="subtle" color="gray" size="xs">
                                            <IconInfoCircle size={14} />
                                        </ActionIcon>
                                    </Tooltip>
                                </Group>
                            </Paper>

                            {/* Fehlerrate */}
                            <Paper p="sm" bg={quickAnalysis.error_count > 0 ? getColor('orange').bg : getColor('teal').bg} radius="md">
                                <Group gap="xs" wrap="nowrap" justify="space-between">
                                    <Group gap="xs" wrap="nowrap">
                                        <ThemeIcon 
                                            size="md" 
                                            radius="md" 
                                            variant="light" 
                                            color={quickAnalysis.error_count > 0 ? 'orange' : 'teal'}
                                        >
                                            <IconAlertTriangle size={16} />
                                        </ThemeIcon>
                                        <div>
                                            <Text size="xs" c={quickAnalysis.error_count > 0 ? getColor('orange').label : getColor('teal').label} tt="uppercase" fw={600} lh={1}>Fehlerrate</Text>
                                            <Group gap={4} align="baseline">
                                                <Text 
                                                    size="md" 
                                                    fw={700} 
                                                    c={quickAnalysis.error_count > 0 ? getColor('orange').text : getColor('teal').text}
                                                    lh={1.2}
                                                >
                                                    {formatPercent(quickAnalysis.error_rate)}
                                                </Text>
                                                {quickAnalysis.error_count > 0 && (
                                                    <Badge color="orange" size="xs" variant="filled">
                                                        {quickAnalysis.error_count}
                                                    </Badge>
                                                )}
                                            </Group>
                                        </div>
                                    </Group>
                                    <Tooltip 
                                        label="Anteil der Anfragen, bei denen das Modell keine gültige Antwort liefern konnte (z.B. Parsing-Fehler, Timeout)"
                                        multiline
                                        w={250}
                                        withArrow
                                    >
                                        <ActionIcon variant="subtle" color="gray" size="xs">
                                            <IconInfoCircle size={14} />
                                        </ActionIcon>
                                    </Tooltip>
                                </Group>
                            </Paper>

                            {/* Order RMA */}
                            <Paper p="sm" bg={getColor('violet').bg} radius="md">
                                <Group gap="xs" wrap="nowrap" justify="space-between">
                                    <Group gap="xs" wrap="nowrap">
                                        <ThemeIcon size="md" radius="md" variant="light" color="violet">
                                            <IconArrowsSort size={16} />
                                        </ThemeIcon>
                                        <div>
                                            <Text size="xs" c={getColor('violet').label} tt="uppercase" fw={600} lh={1}>
                                                RMA{orderSample?.is_sample ? ' (Sample)' : ''}
                                            </Text>
                                            <Text size="md" fw={700} c={getColor('violet').text} lh={1.2}>
                                                {formatRating(orderSample?.rma)}
                                            </Text>
                                        </div>
                                    </Group>
                                    <Tooltip 
                                        label="Rank-biserial Moving Average: Misst die Konsistenz der Rangordnung über Paarvergleiche. Werte nahe 1 bedeuten hohe Übereinstimmung."
                                        multiline
                                        w={280}
                                        withArrow
                                    >
                                        <ActionIcon variant="subtle" color="gray" size="xs">
                                            <IconInfoCircle size={14} />
                                        </ActionIcon>
                                    </Tooltip>
                                </Group>
                            </Paper>

                            {/* Order MAE */}
                            <Paper p="sm" bg={getColor('violet').bg} radius="md">
                                <Group gap="xs" wrap="nowrap" justify="space-between">
                                    <Group gap="xs" wrap="nowrap">
                                        <ThemeIcon size="md" radius="md" variant="light" color="grape">
                                            <IconTarget size={16} />
                                        </ThemeIcon>
                                        <div>
                                            <Text size="xs" c={getColor('violet').label} tt="uppercase" fw={600} lh={1}>
                                                MAE{orderSample?.is_sample ? ' (Sample)' : ''}
                                            </Text>
                                            <Text size="md" fw={700} c={getColor('violet').text} lh={1.2}>
                                                {formatRating(orderSample?.mae)}
                                            </Text>
                                        </div>
                                    </Group>
                                    <Tooltip 
                                        label="Mean Absolute Error: Durchschnittliche Abweichung der Bewertungen bei wiederholten Anfragen. Niedrigere Werte = stabilere Antworten."
                                        multiline
                                        w={280}
                                        withArrow
                                    >
                                        <ActionIcon variant="subtle" color="gray" size="xs">
                                            <IconInfoCircle size={14} />
                                        </ActionIcon>
                                    </Tooltip>
                                </Group>
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
        </Stack>
    );
}
