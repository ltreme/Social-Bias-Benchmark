import { useState, useEffect } from 'react';
import { Card, Stack, Title, MultiSelect, Text, SimpleGrid, Paper, Group, ThemeIcon, Badge, Tabs, useComputedColorScheme } from '@mantine/core';
import { IconScale, IconChartBar, IconTarget } from '@tabler/icons-react';
import { useSearch } from '@tanstack/react-router';
import { useRuns, useMultiRunMetrics, useMultiRunOrderMetrics, useMultiRunDeltas } from './hooks';
import { AsyncContent } from '../../components/AsyncContent';
import { ChartPanel } from '../../components/ChartPanel';
import { useThemedColor } from '../../lib/useThemeColors';

// Color palette for bias levels
const BIAS_COLORS = {
  minimal: '#40c057',   // Green
  low: '#228be6',       // Blue  
  moderate: '#fab005',  // Yellow/Orange
  high: '#e03131',      // Red
};

const COLOR_THRESHOLDS = {
  minimal: 10,
  low: 25,
  moderate: 45,
  high: 100,
};

function getBiasColor(score: number): string {
  if (score <= COLOR_THRESHOLDS.minimal) return BIAS_COLORS.minimal;
  if (score <= COLOR_THRESHOLDS.low) return BIAS_COLORS.low;
  if (score <= COLOR_THRESHOLDS.moderate) return BIAS_COLORS.moderate;
  return BIAS_COLORS.high;
}

const ATTR_LABELS: Record<string, string> = {
  gender: 'Geschlecht',
  age_group: 'Altersgruppe',
  religion: 'Religion',
  sexuality: 'Sexualität',
  marriage_status: 'Familienstand',
  education: 'Bildung',
  origin_subregion: 'Herkunft',
  migration_status: 'Migration',
};

const chartColors = {
  light: {
    gridcolor: '#e9ecef',
    bgcolor: 'rgba(255,255,255,0)',
    tickcolor: '#495057',
  },
  dark: {
    gridcolor: 'rgba(255,255,255,0.15)',
    bgcolor: 'rgba(0,0,0,0)',
    tickcolor: '#c1c2c5',
  },
};

function formatRating(value: number | null | undefined): string {
    if (value === null || value === undefined) return '–';
    return value.toFixed(2);
}

function formatPercent(value: number | null | undefined): string {
    if (value === null || value === undefined) return '–';
    return `${(value * 100).toFixed(1)}%`;
}

export function CompareRunsPage() {
    const { data: runs = [] } = useRuns();
    const search = useSearch({ from: '/runs/compare' }) as { runIds?: string[] };
    const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
    const getColor = useThemedColor();
    const colorScheme = useComputedColorScheme('light');
    const isDark = colorScheme === 'dark';
    const colors = isDark ? chartColors.dark : chartColors.light;

    // Initialize from URL params
    useEffect(() => {
        if (search?.runIds && Array.isArray(search.runIds)) {
            setSelectedRunIds(search.runIds);
        }
    }, [search]);

    const runIds = selectedRunIds.map(id => parseInt(id, 10)).filter(id => !isNaN(id));
    const hasSelection = runIds.length > 0;

    // Data hooks
    const { data: metrics, isLoading: loadingMetrics } = useMultiRunMetrics(runIds, { enabled: hasSelection });
    const { data: orderMetrics, isLoading: loadingOrder } = useMultiRunOrderMetrics(runIds, { enabled: hasSelection });
    const { data: deltasAll, isLoading: loadingDeltasAll } = useMultiRunDeltas(runIds, undefined, { enabled: hasSelection });

    // Run selection options
    const runOptions = runs.map(run => ({
        value: String(run.id),
        label: `#${run.id} – ${run.model_name}`,
    }));

    // Histogram data
    const histBars: Partial<Plotly.Data>[] = metrics && metrics.hist?.bins?.length > 0 ? [
        {
            type: 'bar',
            x: metrics.hist.bins,
            y: metrics.hist.shares,
            marker: {
                color: ['#4dabf7', '#748ffc', '#9775fa', '#be4bdb', '#e599f7'],
                opacity: 0.9,
            },
            text: metrics.hist.shares.map((p: number) => `${(p * 100).toFixed(0)}%`),
            textposition: 'outside',
            textfont: { size: 11 },
            cliponaxis: false,
            hovertemplate: '<b>Rating %{x}</b><br>%{y:.1%}<extra></extra>',
            showlegend: false,
        }
    ] : [];

    // Bias radar data - bias_intensity is already on 0-100 scale
    const radarScores = deltasAll?.data ? Object.entries(deltasAll.data)
        .map(([attr, data]) => ({
            attribute: attr,
            label: ATTR_LABELS[attr] || attr,
            score: data.bias_intensity ?? 0,
        }))
        .filter(item => item.score !== null) : [];

    // Prepare radar chart
    const radarCategories = radarScores.map(s => s.label);
    const radarValues = radarScores.map(s => s.score);
    const radarColors = radarValues.map(v => getBiasColor(v));
    const radarCategoriesClosed = [...radarCategories, radarCategories[0]];
    const radarValuesClosed = [...radarValues, radarValues[0]];
    const radarColorsClosed = [...radarColors, radarColors[0]];

    return (
        <Stack gap="md">
            <Card>
                <Group justify="space-between" mb="md">
                    <Group gap="sm">
                        <IconScale size={28} color="#228be6" />
                        <Title order={2}>Run-Vergleich</Title>
                    </Group>
                </Group>

                <Text size="sm" c="dimmed" mb="md">
                    Wähle mehrere Benchmark-Runs aus, um deren aggregierte Metriken und Bias-Analysen zu vergleichen.
                </Text>

                <MultiSelect
                    label="Runs auswählen"
                    placeholder="Wähle Runs zum Vergleichen..."
                    data={runOptions}
                    value={selectedRunIds}
                    onChange={setSelectedRunIds}
                    searchable
                    clearable
                    maxDropdownHeight={400}
                />
            </Card>

            {hasSelection && (
                <>
                    {/* Selected Runs Info */}
                    <Card withBorder padding="sm">
                        <Title order={5} mb="sm">Ausgewählte Runs</Title>
                        <Group gap="xs">
                            {metrics?.runs.map(run => (
                                <Badge key={run.run_id} variant="light" size="lg">
                                    #{run.run_id} · {run.model} · {run.n.toLocaleString('de-DE')} Ergebnisse
                                </Badge>
                            ))}
                        </Group>
                    </Card>

                    <Tabs defaultValue="overview">
                        <Tabs.List>
                            <Tabs.Tab value="overview">Übersicht</Tabs.Tab>
                            <Tabs.Tab value="order">Order-Consistency</Tabs.Tab>
                            <Tabs.Tab value="bias">Bias-Analyse</Tabs.Tab>
                        </Tabs.List>

                        {/* Overview Tab */}
                        <Tabs.Panel value="overview" pt="md">
                            <Stack gap="md">
                                {/* Summary Stats */}
                                <SimpleGrid cols={{ base: 2, md: 4 }} spacing="sm">
                                    <Paper p="sm" bg={getColor('blue').bg} radius="md">
                                        <Group gap="xs" wrap="nowrap">
                                            <ThemeIcon size="md" radius="md" variant="light" color="blue">
                                                <IconChartBar size={16} />
                                            </ThemeIcon>
                                            <div>
                                                <Text size="xs" c={getColor('blue').label} tt="uppercase" fw={600} lh={1}>
                                                    Gesamt Ergebnisse
                                                </Text>
                                                <Text size="md" fw={700} c={getColor('blue').text} lh={1.2}>
                                                    {metrics?.n.toLocaleString('de-DE') ?? '–'}
                                                </Text>
                                            </div>
                                        </Group>
                                    </Paper>

                                    <Paper p="sm" bg={getColor('violet').bg} radius="md">
                                        <Group gap="xs" wrap="nowrap">
                                            <ThemeIcon size="md" radius="md" variant="light" color="violet">
                                                <IconChartBar size={16} />
                                            </ThemeIcon>
                                            <div>
                                                <Text size="xs" c={getColor('violet').label} tt="uppercase" fw={600} lh={1}>
                                                    ⌀ Rating
                                                </Text>
                                                <Text size="md" fw={700} c={getColor('violet').text} lh={1.2}>
                                                    {formatRating(metrics?.mean)}
                                                </Text>
                                            </div>
                                        </Group>
                                    </Paper>

                                    <Paper p="sm" bg={getColor('teal').bg} radius="md">
                                        <Group gap="xs" wrap="nowrap">
                                            <ThemeIcon size="md" radius="md" variant="light" color="teal">
                                                <IconTarget size={16} />
                                            </ThemeIcon>
                                            <div>
                                                <Text size="xs" c={getColor('teal').label} tt="uppercase" fw={600} lh={1}>
                                                    Median
                                                </Text>
                                                <Text size="md" fw={700} c={getColor('teal').text} lh={1.2}>
                                                    {formatRating(metrics?.median)}
                                                </Text>
                                            </div>
                                        </Group>
                                    </Paper>

                                    <Paper p="sm" bg={getColor('orange').bg} radius="md">
                                        <Group gap="xs" wrap="nowrap">
                                            <ThemeIcon size="md" radius="md" variant="light" color="orange">
                                                <IconScale size={16} />
                                            </ThemeIcon>
                                            <div>
                                                <Text size="xs" c={getColor('orange').label} tt="uppercase" fw={600} lh={1}>
                                                    Runs
                                                </Text>
                                                <Text size="md" fw={700} c={getColor('orange').text} lh={1.2}>
                                                    {metrics?.runs.length ?? 0}
                                                </Text>
                                            </div>
                                        </Group>
                                    </Paper>
                                </SimpleGrid>

                                {/* Rating Distribution */}
                                <Card withBorder padding="sm">
                                    <Title order={5} mb="sm">Kombinierte Rating-Verteilung</Title>
                                    <AsyncContent isLoading={loadingMetrics}>
                                        {metrics && histBars.length > 0 ? (
                                            <ChartPanel
                                                title=""
                                                data={histBars}
                                                height={250}
                                                layout={{
                                                    barmode: 'group',
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
                                                    },
                                                }}
                                            />
                                        ) : metrics ? (
                                            <Text c="dimmed" ta="center" py="md">Keine Rating-Daten verfügbar</Text>
                                        ) : null}
                                    </AsyncContent>
                                </Card>
                            </Stack>
                        </Tabs.Panel>

                        {/* Order Consistency Tab */}
                        <Tabs.Panel value="order" pt="md">
                            <Card withBorder padding="sm">
                                <Title order={5} mb="md">Order-Consistency Metriken (Aggregiert)</Title>
                                <AsyncContent isLoading={loadingOrder}>
                                    {orderMetrics?.summary ? (
                                        <SimpleGrid cols={{ base: 2, md: 4 }} spacing="sm">
                                            <Paper p="md" bg={getColor('violet').bg} radius="md">
                                                <Text size="xs" c={getColor('violet').label} tt="uppercase" fw={600} mb={4}>
                                                    ⌀ RMA
                                                </Text>
                                                <Text size="xl" fw={700} c={getColor('violet').text}>
                                                    {formatRating(orderMetrics.summary.avg_rma)}
                                                </Text>
                                            </Paper>

                                            <Paper p="md" bg={getColor('blue').bg} radius="md">
                                                <Text size="xs" c={getColor('blue').label} tt="uppercase" fw={600} mb={4}>
                                                    ⌀ MAE
                                                </Text>
                                                <Text size="xl" fw={700} c={getColor('blue').text}>
                                                    {formatRating(orderMetrics.summary.avg_mae)}
                                                </Text>
                                            </Paper>

                                            <Paper p="md" bg={getColor('teal').bg} radius="md">
                                                <Text size="xs" c={getColor('teal').label} tt="uppercase" fw={600} mb={4}>
                                                    ⌀ Within-1 Rate
                                                </Text>
                                                <Text size="xl" fw={700} c={getColor('teal').text}>
                                                    {formatPercent(orderMetrics.summary.avg_within1_rate)}
                                                </Text>
                                            </Paper>

                                            <Paper p="md" bg={getColor('orange').bg} radius="md">
                                                <Text size="xs" c={getColor('orange').label} tt="uppercase" fw={600} mb={4}>
                                                    ⌀ Korrelation
                                                </Text>
                                                <Text size="xl" fw={700} c={getColor('orange').text}>
                                                    {formatRating(orderMetrics.summary.avg_correlation)}
                                                </Text>
                                            </Paper>
                                        </SimpleGrid>
                                    ) : (
                                        <Text c="dimmed">Keine Order-Metriken verfügbar</Text>
                                    )}
                                </AsyncContent>

                                {/* Per-Run Breakdown */}
                                {orderMetrics?.runs && orderMetrics.runs.length > 0 && (
                                    <Stack gap="xs" mt="md">
                                        <Text size="sm" fw={600} c="dimmed">Pro Run:</Text>
                                        {orderMetrics.runs.map(run => (
                                            <Paper key={run.run_id} p="xs" withBorder>
                                                <Group justify="space-between">
                                                    <Text size="sm" fw={500}>#{run.run_id} · {run.model}</Text>
                                                    <Group gap="md">
                                                        <Text size="xs" c="dimmed">RMA: {formatPercent(run.rma)}</Text>
                                                        <Text size="xs" c="dimmed">MAE: {formatRating(run.mae)}</Text>
                                                        <Text size="xs" c="dimmed">Within-1: {formatPercent(run.within1_rate)}</Text>
                                                    </Group>
                                                </Group>
                                            </Paper>
                                        ))}
                                    </Stack>
                                )}
                            </Card>
                        </Tabs.Panel>

                        {/* Bias Analysis Tab */}
                        <Tabs.Panel value="bias" pt="md">
                            <Card withBorder padding="sm">
                                <Title order={5} mb="md">Bias-Intensität pro Merkmal (Aggregiert)</Title>
                                <AsyncContent isLoading={loadingDeltasAll}>
                                    {radarScores.length > 0 ? (
                                        <>
                                            <ChartPanel
                                                data={[
                                                    {
                                                        type: 'scatterpolar',
                                                        r: radarValuesClosed,
                                                        theta: radarCategoriesClosed,
                                                        fill: 'toself',
                                                        fillcolor: 'rgba(173, 181, 189, 0.15)',
                                                        line: { color: '#adb5bd', width: 1.5, dash: 'dot' },
                                                        marker: { size: 0 },
                                                        name: 'Bias-Bereich',
                                                        hoverinfo: 'skip',
                                                        showlegend: false,
                                                    } as Partial<Plotly.Data>,
                                                    {
                                                        type: 'scatterpolar',
                                                        r: radarValuesClosed,
                                                        theta: radarCategoriesClosed,
                                                        mode: 'markers',
                                                        marker: {
                                                            size: 12,
                                                            color: radarColorsClosed,
                                                            line: { color: isDark ? '#25262b' : '#fff', width: 2 },
                                                        },
                                                        name: 'Bias-Score',
                                                        hovertemplate: '<b>%{theta}</b><br>Score: %{r:.1f}/100<extra></extra>',
                                                    } as unknown as Partial<Plotly.Data>,
                                                ]}
                                                height={400}
                                                layout={{
                                                    polar: {
                                                        radialaxis: {
                                                            visible: true,
                                                            range: [0, 100],
                                                            tickvals: [0, 25, 50, 75, 100],
                                                            ticktext: ['0', '25', '50', '75', '100'],
                                                            gridcolor: colors.gridcolor,
                                                            tickfont: { color: colors.tickcolor },
                                                        },
                                                        angularaxis: {
                                                            tickfont: { size: 11, color: colors.tickcolor },
                                                            gridcolor: colors.gridcolor,
                                                        },
                                                        bgcolor: colors.bgcolor,
                                                    },
                                                    margin: { l: 80, r: 80, t: 30, b: 30 },
                                                    showlegend: false,
                                                }}
                                            />
                                            
                                            {/* Color Legend */}
                                            <Group gap="lg" mt="md" justify="center" wrap="wrap">
                                                <Group gap="xs">
                                                    <div style={{ width: 12, height: 12, backgroundColor: BIAS_COLORS.minimal, borderRadius: 3 }} />
                                                    <Text size="xs" c="dimmed">0-{COLOR_THRESHOLDS.minimal}: Minimal</Text>
                                                </Group>
                                                <Group gap="xs">
                                                    <div style={{ width: 12, height: 12, backgroundColor: BIAS_COLORS.low, borderRadius: 3 }} />
                                                    <Text size="xs" c="dimmed">{COLOR_THRESHOLDS.minimal}-{COLOR_THRESHOLDS.low}: Gering</Text>
                                                </Group>
                                                <Group gap="xs">
                                                    <div style={{ width: 12, height: 12, backgroundColor: BIAS_COLORS.moderate, borderRadius: 3 }} />
                                                    <Text size="xs" c="dimmed">{COLOR_THRESHOLDS.low}-{COLOR_THRESHOLDS.moderate}: Moderat</Text>
                                                </Group>
                                                <Group gap="xs">
                                                    <div style={{ width: 12, height: 12, backgroundColor: BIAS_COLORS.high, borderRadius: 3 }} />
                                                    <Text size="xs" c="dimmed">{COLOR_THRESHOLDS.moderate}+: Stark</Text>
                                                </Group>
                                            </Group>
                                        </>
                                    ) : (
                                        <Text c="dimmed">Keine Bias-Daten verfügbar</Text>
                                    )}
                                </AsyncContent>
                            </Card>
                        </Tabs.Panel>
                    </Tabs>
                </>
            )}
        </Stack>
    );
}
