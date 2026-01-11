import { Card, Paper, Text, Title, Badge, Group, Stack, ThemeIcon, SimpleGrid, Tooltip, ActionIcon, SegmentedControl } from '@mantine/core';
import { useState } from 'react';
import { IconChartBar, IconAlertTriangle, IconArrowsSort, IconTarget, IconInfoCircle } from '@tabler/icons-react';
import { ChartPanel } from '../../../components/ChartPanel';
import { AsyncContent } from '../../../components/AsyncContent';
import { BiasRadarGrid } from './BiasRadarChart';
import { KruskalWallisByCategory } from './KruskalWallisByCategory';
import { useThemedColor } from '../../../lib/useThemeColors';
import type { QuickAnalysis, RunMetrics, RunDeltas, OrderMetrics } from '../api';

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
    /** Full order metrics (all pairs) */
    orderMetrics?: OrderMetrics | null;
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
    orderMetrics,
}: OverviewTabProps) {
    const getColor = useThemedColor();
    const orderSample = quickAnalysis?.order_consistency_sample;
    const [histogramView, setHistogramView] = useState<'all' | 'categories'>('all');

    // Histogram bars from metrics
    const histCounts = metrics?.hist?.counts || (metrics ? metrics.hist.shares.map((p) => Math.round(p * (metrics.n || 0))) : []);
    // Mantine-harmonische Farbpalette (gedämpftere Farben)
    const palette = ['#339af0', '#9775fa', '#20c997', '#fcc419'];
    let histBars: Partial<Plotly.Data>[] = [];
    if (metrics) {
        if (histogramView === 'categories' && !traitCategoryFilter && metrics.trait_categories?.histograms?.length) {
            histBars = metrics.trait_categories.histograms.map((h, idx) => ({
                type: 'bar',
                name: h.category,
                x: h.bins,
                y: h.shares,
                text: h.shares.map((p: number, i: number) => `${(p * 100).toFixed(0)}% (n=${h.counts[i]})`),
                textposition: 'outside',
                textfont: { size: 10 },
                cliponaxis: false,
                marker: { 
                    color: palette[idx % palette.length], 
                    opacity: 0.9,
                    line: { width: 0, color: palette[idx % palette.length] },
                },
                hovertemplate: '<b>%{x}</b><br>%{y:.1%} (n=%{customdata})<extra></extra>',
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
            // Farbverlauf von Blau zu Violett für einzelne Kategorie
            const barColors = ['#4dabf7', '#748ffc', '#9775fa', '#be4bdb', '#e599f7'];
            histBars = [
                {
                    type: 'bar',
                    x: baseHist.bins,
                    y: baseHist.shares,
                    marker: { 
                        color: barColors,
                        opacity: 0.9,
                        line: { width: 0 },
                    },
                    text: baseHist.shares.map((p: number, i: number) => `${(p * 100).toFixed(0)}% (n=${baseHist.counts[i]})`),
                    textposition: 'outside',
                    textfont: { size: 11 },
                    cliponaxis: false,
                    hovertemplate: '<b>Rating %{x}</b><br>%{y:.1%} (n=%{customdata})<extra></extra>',
                    customdata: baseHist.counts,
                    showlegend: false,
                },
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
                                                RMA
                                            </Text>
                                            <Text size="md" fw={700} c={getColor('violet').text} lh={1.2}>
                                                {formatPercent(orderMetrics?.rma?.exact_rate ?? orderSample?.rma)}
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
                                                MAE
                                            </Text>
                                            <Text size="md" fw={700} c={getColor('violet').text} lh={1.2}>
                                                {formatRating(orderMetrics?.rma?.mae ?? orderSample?.mae)}
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

            {/* Detailed Rating Distribution Chart */}
            <Card withBorder padding="sm">
                <Group justify="space-between" align="center" mb="sm">
                    <Title order={5}>Rating-Verteilung</Title>
                    <Group gap="md">
                        {!traitCategoryFilter && metrics?.trait_categories?.histograms?.length ? (
                            <SegmentedControl
                                size="xs"
                                value={histogramView}
                                onChange={(value) => setHistogramView(value as 'all' | 'categories')}
                                data={[
                                    { label: 'Gesamt', value: 'all' },
                                    { label: 'Nach Kategorie', value: 'categories' },
                                ]}
                            />
                        ) : null}
                        <Text size="xs" c="dimmed">1 = gar nicht · 5 = sehr ‹Adjektiv›</Text>
                    </Group>
                </Group>
                <AsyncContent isLoading={isLoadingMetrics} isError={!!metricsError} error={metricsError}>
                    {metrics ? (
                        <ChartPanel 
                            title="" 
                            data={histBars} 
                            height={200}
                            layout={{
                                barmode: 'group',
                                bargap: 0.3,
                                margin: { t: 40, b: 36, l: 44, r: 12 },
                                xaxis: { 
                                    tickmode: 'array', 
                                    tickvals: [1, 2, 3, 4, 5],
                                    ticktext: ['1', '2', '3', '4', '5'],
                                    fixedrange: true,
                                },
                                yaxis: { 
                                    tickformat: '.0%', 
                                    rangemode: 'tozero', 
                                    title: { text: '' },
                                    fixedrange: true,
                                    gridwidth: 1,
                                },
                                legend: { orientation: 'h', y: -0.2, x: 0.5, xanchor: 'center' },
                                hovermode: 'x unified',
                            }} 
                        />
                    ) : null}
                </AsyncContent>
            </Card>

            {/* Bias Radar Chart Grid - Bias-Intensität pro Merkmal */}
            {runId && radarTraitCategories && radarTraitCategories.length > 0 && radarCategoryDeltasMap && (
                <BiasRadarGrid 
                    runId={runId}
                    traitCategories={radarTraitCategories}
                    categoryDeltasMap={radarCategoryDeltasMap}
                    loadingStates={radarLoadingStates}
                />
            )}

            {/* Kruskal-Wallis Statistical Test */}
            {runId && (
                <KruskalWallisByCategory runId={runId} />
            )}
        </Stack>
    );
}
