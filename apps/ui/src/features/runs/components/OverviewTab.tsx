import { Card, Grid, Text, Title, Badge, Group, Stack } from '@mantine/core';
import { ChartPanel } from '../../../components/ChartPanel';
import { AsyncContent } from '../../../components/AsyncContent';
import type { QuickAnalysis, RunMetrics } from '../api';

type OverviewTabProps = {
    quickAnalysis?: QuickAnalysis | null;
    isLoadingQuick: boolean;
    metrics?: RunMetrics | null;
    isLoadingMetrics: boolean;
    metricsError?: any;
    traitCategoryFilter?: string;
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
}: OverviewTabProps) {
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
                <Title order={4} mb="sm">Quick-Check</Title>
                <AsyncContent isLoading={isLoadingQuick} loadingLabel="Lade Quick-Analyse...">
                    {quickAnalysis ? (
                        <Grid>
                            <Grid.Col span={{ base: 6, md: 3 }}>
                                <Stack gap={4}>
                                    <Text size="sm" c="dimmed">Ergebnisse</Text>
                                    <Text size="xl" fw={600}>{quickAnalysis.total_results.toLocaleString()}</Text>
                                </Stack>
                            </Grid.Col>
                            <Grid.Col span={{ base: 6, md: 3 }}>
                                <Stack gap={4}>
                                    <Text size="sm" c="dimmed">Fehlerrate</Text>
                                    <Group gap={4}>
                                        <Text size="xl" fw={600}>{formatPercent(quickAnalysis.error_rate)}</Text>
                                        {quickAnalysis.error_count > 0 && (
                                            <Badge color="orange" size="sm">{quickAnalysis.error_count}</Badge>
                                        )}
                                    </Group>
                                </Stack>
                            </Grid.Col>
                            <Grid.Col span={{ base: 6, md: 3 }}>
                                <Stack gap={4}>
                                    <Text size="sm" c="dimmed">Order RMA{orderSample?.is_sample ? ' (Sample)' : ''}</Text>
                                    <Text size="xl" fw={600}>{formatRating(orderSample?.rma)}</Text>
                                </Stack>
                            </Grid.Col>
                            <Grid.Col span={{ base: 6, md: 3 }}>
                                <Stack gap={4}>
                                    <Text size="sm" c="dimmed">Order MAE{orderSample?.is_sample ? ' (Sample)' : ''}</Text>
                                    <Text size="xl" fw={600}>{formatRating(orderSample?.mae)}</Text>
                                </Stack>
                            </Grid.Col>
                        </Grid>
                    ) : (
                        <Text c="dimmed">Keine Quick-Analyse verfügbar</Text>
                    )}
                </AsyncContent>
            </Card>

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
