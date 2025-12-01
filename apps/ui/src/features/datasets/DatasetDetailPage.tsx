import { Accordion, Badge, Button, Card, Grid, Group, Progress, Text, Title, useComputedColorScheme } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useParams, Link } from '@tanstack/react-router';
import { ChartPanel } from '../../components/ChartPanel';
import { toBar, toDonut, CHART_COLORS } from '../../components/ChartUtils';
import { useDatasetComposition, useDataset, useDatasetRuns, useAttrgenStatus, useLatestAttrgen, useAttrgenRuns, useBenchmarkStatus, useCancelBenchmark, useActiveBenchmark } from './hooks';
import { useModelsAdmin } from '../models/hooks';
import { useEffect, useState } from 'react';
// no modal inputs here; forms live in child components
import { AttrGenModal } from './components/AttrGenModal';
import { BenchmarkModal } from './components/BenchmarkModal';
import { AttrgenRunsTable } from './components/AttrgenRunsTable';
import { DatasetRunsTable } from './components/DatasetRunsTable';
import { IconDatabase, IconUsers, IconPlayerPlay, IconSparkles, IconChartBar, IconCalendar, IconSettings, IconSitemap, IconTarget, IconArrowsShuffle, IconCpu, IconGenderBigender, IconWorld, IconSchool } from '@tabler/icons-react';

// Helper to format date nicely
function formatDate(dateStr?: string | null): string {
    if (!dateStr) return '–';
    const d = new Date(dateStr);
    return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

// Map kind to badge
function getKindBadge(kind?: string) {
    switch (kind) {
        case 'pool':
            return <Badge leftSection={<IconDatabase size={12} />} variant="light" color="blue" size="lg">Pool</Badge>;
        case 'balanced':
            return <Badge leftSection={<IconSitemap size={12} />} variant="light" color="green" size="lg">Balanced</Badge>;
        case 'reality':
            return <Badge leftSection={<IconUsers size={12} />} variant="light" color="orange" size="lg">Reality</Badge>;
        case 'counterfactual':
            return <Badge leftSection={<IconArrowsShuffle size={12} />} variant="light" color="pink" size="lg">Counterfactual</Badge>;
        case 'generated':
            return <Badge variant="light" color="gray" size="lg">Generated</Badge>;
        default:
            return <Badge variant="light" color="gray" size="lg">{kind || 'Unbekannt'}</Badge>;
    }
}

// Render config_json in a user-friendly way
function ConfigDisplay({ config, isDark }: { config: Record<string, any>; isDark: boolean }) {
    const items: { label: string; value: React.ReactNode; icon: React.ReactNode }[] = [];

    if (config.source_dataset_id !== undefined) {
        items.push({
            label: 'Quell-Dataset',
            value: <Badge variant="light" color="blue">#{config.source_dataset_id}</Badge>,
            icon: <IconDatabase size={14} />
        });
    }
    if (config.dataset_id !== undefined) {
        items.push({
            label: 'Basis-Dataset',
            value: <Badge variant="light" color="blue">#{config.dataset_id}</Badge>,
            icon: <IconDatabase size={14} />
        });
    }
    if (config.from_dataset !== undefined) {
        items.push({
            label: 'Von Dataset',
            value: <Badge variant="light" color="blue">#{config.from_dataset}</Badge>,
            icon: <IconDatabase size={14} />
        });
    }
    if (config.n_target !== undefined) {
        items.push({
            label: 'Zielgröße',
            value: <Text fw={500}>{config.n_target.toLocaleString('de-DE')}</Text>,
            icon: <IconTarget size={14} />
        });
    }
    if (config.n !== undefined) {
        items.push({
            label: 'Stichprobengröße',
            value: <Text fw={500}>{config.n.toLocaleString('de-DE')}</Text>,
            icon: <IconUsers size={14} />
        });
    }
    if (config.axes && Array.isArray(config.axes)) {
        items.push({
            label: 'Balancierungs-Achsen',
            value: <Group gap={4}>{config.axes.map((a: string) => <Badge key={a} variant="light" color="teal" size="sm">{a}</Badge>)}</Group>,
            icon: <IconSitemap size={14} />
        });
    }
    if (config.method) {
        items.push({
            label: 'Methode',
            value: <Badge variant="outline" color="gray">{config.method}</Badge>,
            icon: <IconCpu size={14} />
        });
    }
    if (config.strategy) {
        items.push({
            label: 'Strategie',
            value: <Badge variant="outline" color="gray">{config.strategy}</Badge>,
            icon: <IconArrowsShuffle size={14} />
        });
    }

    if (items.length === 0) {
        return <Text size="sm" c="dimmed">Keine Konfiguration</Text>;
    }

    return (
        <Group gap="lg" wrap="wrap">
            {items.map((item, i) => (
                <div key={i}>
                    <Group gap={4} mb={2}>
                        <span style={{ color: isDark ? '#909296' : '#868e96' }}>{item.icon}</span>
                        <Text size="xs" c="dimmed">{item.label}</Text>
                    </Group>
                    {item.value}
                </div>
            ))}
        </Group>
    );
}

export function DatasetDetailPage() {
    const { datasetId } = useParams({ from: '/datasets/$datasetId' });
    const idNum = Number(datasetId);
    const { data: dataset_info, isLoading: isLoadingDataset } = useDataset(idNum);
    const { data, isLoading } = useDatasetComposition(idNum);
    const { data: runs, isLoading: isLoadingRuns } = useDatasetRuns(idNum);
    const { data: availableModels } = useModelsAdmin();
    const [modalOpen, setModalOpen] = useState(false);
    const [benchModalOpen, setBenchModalOpen] = useState(false);
    const [runId, setRunId] = useState<number | undefined>(undefined);
    const runsList = useAttrgenRuns(idNum);
    const [benchRunId, setBenchRunId] = useState<number | undefined>(undefined);
    const [attrgenRunForBenchmark, setAttrgenRunForBenchmark] = useState<number | undefined>(undefined);
    const [benchInitialModelName, setBenchInitialModelName] = useState<string | undefined>(undefined);
    const benchStatus = useBenchmarkStatus(benchRunId);
    const activeBenchmark = useActiveBenchmark(idNum);
    const cancelBench = useCancelBenchmark();
    const status = useAttrgenStatus(runId);
    const latest = useLatestAttrgen(idNum);
    const colorScheme = useComputedColorScheme('light');
    const isDark = colorScheme === 'dark';
    
    useEffect(() => {
        if (!runId && latest.data && latest.data.found && latest.data.run_id) {
            setRunId(latest.data.run_id);
        }
    }, [latest.data, runId]);

    // Notify user on failed attrgen status
    useEffect(() => {
        const s = status.data?.status;
        const l = latest.data?.status;
        const err = (status.data as any)?.error || (latest.data as any)?.error;
        if ((s === 'failed' || l === 'failed') && err) {
            notifications.show({ color: 'red', title: 'AttrGen fehlgeschlagen', message: String(err) });
        }
    }, [status.data?.status, latest.data?.status]);

    // Sync benchRunId with active benchmark info
    useEffect(() => {
        if (activeBenchmark.data?.active && activeBenchmark.data.run_id) {
            setBenchRunId(activeBenchmark.data.run_id);
        } else if (!activeBenchmark.data?.active && benchStatus.data?.status && ['done', 'failed', 'cancelled'].includes(benchStatus.data.status)) {
            setBenchRunId(undefined);
        }
    }, [activeBenchmark.data?.active, activeBenchmark.data?.run_id, benchStatus.data?.status]);

    // Notify user on failed benchmark status
    useEffect(() => {
        const st = benchStatus.data?.status;
        if (st === 'failed' && (benchStatus.data as any)?.error) {
            notifications.show({ color: 'red', title: 'Benchmark fehlgeschlagen', message: String((benchStatus.data as any).error) });
        }
    }, [benchStatus.data?.status]);

    const gender = data?.attributes?.gender ?? [];
    const religion = data?.attributes?.religion ?? [];
    const sexuality = data?.attributes?.sexuality ?? [];
    const education = data?.attributes?.education ?? [];
    const marriage = data?.attributes?.marriage_status ?? [];
    const migrationRaw = data?.attributes?.migration_status ?? [];
    const originRegion = data?.attributes?.origin_region ?? [];
    const originCountry = data?.attributes?.origin_country ?? [];

    // Transform migration labels to be more readable
    const migration = migrationRaw.map(m => ({
        ...m,
        value: m.value === 'with_migration' ? 'Mit Migrationshintergrund' 
             : m.value === 'without_migration' ? 'Ohne Migrationshintergrund'
             : m.value
    }));

    // Calculate KPIs
    const totalPersonas = data?.n ?? 0;
    const avgAge = (() => {
        if (!data?.age?.bins || !data?.age?.male || !data?.age?.female) return null;
        let totalAge = 0;
        let totalCount = 0;
        data.age.bins.forEach((bin, i) => {
            // Parse bin like "25-29" to get midpoint
            const match = bin.match(/(\d+)/);
            if (match) {
                const midAge = parseInt(match[1]) + 2; // approximate midpoint
                const count = (data.age.male[i] || 0) + (data.age.female[i] || 0) + (data.age.other?.[i] || 0);
                totalAge += midAge * count;
                totalCount += count;
            }
        });
        return totalCount > 0 ? Math.round(totalAge / totalCount) : null;
    })();
    
    // Gender distribution percentages
    const genderTotal = gender.reduce((sum, g) => sum + g.count, 0);
    const genderPcts = gender.map(g => ({ ...g, pct: genderTotal > 0 ? (g.count / genderTotal * 100).toFixed(1) : '0' }));

    // Age pyramid setup: male negative on X, female positive
    const ageBins = data?.age?.bins ?? [];
    const male = (data?.age?.male ?? []).map((v) => -v);
    const female = data?.age?.female ?? [];
    const other = data?.age?.other ?? [];
    const traces: Partial<Plotly.Data>[] = [
        { name: 'Male', type: 'bar', x: male, y: ageBins, orientation: 'h' },
        { name: 'Female', type: 'bar', x: female, y: ageBins, orientation: 'h' },
    ];
    if (other.some((v) => v > 0)) {
        traces.push({ name: 'Other', type: 'bar', x: other, y: ageBins, orientation: 'h' });
    }

    // tables moved into components

    return (
        <>
        <Card>
            {/* Header */}
            <Group justify="space-between" mb="lg">
                <Group gap="sm">
                    <IconDatabase size={28} color="#228be6" />
                    <Title order={2}>Dataset #{datasetId}</Title>
                    {dataset_info?.name && (
                        <Text size="xl" c="dimmed" fw={400}>{dataset_info.name}</Text>
                    )}
                </Group>
                <Group gap="sm">
                    <Button 
                        variant="light" 
                        color="cyan"
                        leftSection={<IconPlayerPlay size={16} />}
                        onClick={() => setBenchModalOpen(true)}
                    >
                        Benchmark starten
                    </Button>
                    <Button 
                        color="violet"
                        leftSection={<IconSparkles size={16} />}
                        onClick={() => setModalOpen(true)}
                    >
                        Attribute generieren
                    </Button>
                </Group>
            </Group>
            
            {/* Dataset Info Card */}
            {isLoadingDataset ? (
                <Text c="dimmed" py="md">Dataset wird geladen…</Text>
            ) : dataset_info ? (
                <Card 
                    withBorder 
                    mb="lg" 
                    padding="lg" 
                    style={{ 
                        background: isDark ? 'rgba(34, 139, 230, 0.08)' : 'rgba(34, 139, 230, 0.05)',
                        borderColor: isDark ? 'rgba(34, 139, 230, 0.3)' : 'rgba(34, 139, 230, 0.2)'
                    }}
                >
                    <Group gap="xl" wrap="wrap">
                        {/* Art */}
                        <div>
                            <Text size="xs" c="dimmed" mb={4}>Art</Text>
                            {getKindBadge(dataset_info.kind)}
                        </div>
                        
                        {/* Größe */}
                        <div>
                            <Text size="xs" c="dimmed" mb={4}>Größe</Text>
                            <Group gap={4}>
                                <IconUsers size={16} color={isDark ? '#909296' : '#868e96'} />
                                <Text fw={600} size="lg">{dataset_info.size?.toLocaleString('de-DE')}</Text>
                            </Group>
                        </div>
                        
                        {/* Erstellt */}
                        {dataset_info.created_at && (
                            <div>
                                <Text size="xs" c="dimmed" mb={4}>Erstellt</Text>
                                <Group gap={4}>
                                    <IconCalendar size={16} color={isDark ? '#909296' : '#868e96'} />
                                    <Text fw={500}>{formatDate(dataset_info.created_at)}</Text>
                                </Group>
                            </div>
                        )}
                        
                        {/* Seed */}
                        {dataset_info.seed && (
                            <div>
                                <Text size="xs" c="dimmed" mb={4}>Seed</Text>
                                <Badge variant="light" color="gray" size="lg">{dataset_info.seed}</Badge>
                            </div>
                        )}
                        
                        {/* Personas Link */}
                        <div>
                            <Text size="xs" c="dimmed" mb={4}>Personas</Text>
                            <Button 
                                component={Link} 
                                to={`/datasets/${datasetId}/personas`}
                                variant="light"
                                size="xs"
                                leftSection={<IconUsers size={14} />}
                            >
                                Anzeigen
                            </Button>
                        </div>
                    </Group>
                    
                    {/* Config - schöne Darstellung */}
                    {dataset_info.config_json && Object.keys(dataset_info.config_json).length > 0 && (
                        <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}` }}>
                            <Group gap={4} mb="sm">
                                <IconSettings size={14} color={isDark ? '#909296' : '#868e96'} />
                                <Text size="xs" c="dimmed">Konfiguration</Text>
                            </Group>
                            <ConfigDisplay config={dataset_info.config_json} isDark={isDark} />
                        </div>
                    )}
                </Card>
            ) : (
                <Card withBorder mb="lg" padding="lg">
                    <Text c="red">Dataset nicht gefunden.</Text>
                </Card>
            )}

            {/* Einklappbare Sektionen für AttrGen und Benchmark Runs */}
            <Accordion 
                variant="separated" 
                multiple
                defaultValue={['attrgen', 'benchmark']}
                mb="lg"
                styles={{
                    control: { padding: '12px 16px' },
                    panel: { padding: '0 16px 16px' },
                }}
            >
                {/* Attribute-Generierung Runs */}
                {(runsList.data?.runs && runsList.data.runs.length > 0) && (
                    <Accordion.Item value="attrgen">
                        <Accordion.Control>
                            <Group gap="sm">
                                <IconSparkles size={20} color="#7950f2" />
                                <Text fw={600}>Attribute-Generierung</Text>
                                <Badge variant="light" color="violet" size="sm">{runsList.data.runs.length} Runs</Badge>
                            </Group>
                        </Accordion.Control>
                        <Accordion.Panel>
                            <AttrgenRunsTable
                                datasetId={idNum}
                                runs={runsList.data.runs}
                                onRequestBenchmark={(modelName, runId) => { setBenchInitialModelName(modelName || undefined); setAttrgenRunForBenchmark(runId); setBenchModalOpen(true); }}
                            />
                            {benchRunId && (benchStatus.data || activeBenchmark.data?.active) ? (
                                <Card withBorder mt="md" padding="md" style={{ 
                                    background: isDark ? 'rgba(34, 139, 230, 0.08)' : 'rgba(34, 139, 230, 0.05)',
                                    borderColor: isDark ? 'rgba(34, 139, 230, 0.3)' : 'rgba(34, 139, 230, 0.2)'
                                }}>
                                    {(benchStatus.data?.status || activeBenchmark.data?.status) === 'failed' ? (
                                        <Text c="red" fw={500}>
                                            Benchmark-Fehler: {(benchStatus.data as any)?.error || (activeBenchmark.data as any)?.error || 'Unbekannter Fehler'}
                                        </Text>
                                    ) : (
                                        <Group gap="md" align="center">
                                            <div style={{ flex: 1 }}>
                                                <Group gap="xs" mb={4}>
                                                    <IconPlayerPlay size={16} color="#228be6" />
                                                    <Text fw={500}>Benchmark-Status: {benchStatus.data?.status || activeBenchmark.data?.status || 'unknown'}</Text>
                                                    <Badge variant="light" color="blue" size="sm">
                                                        {benchStatus.data?.done ?? activeBenchmark.data?.done ?? 0}/{benchStatus.data?.total ?? activeBenchmark.data?.total ?? 0}
                                                    </Badge>
                                                </Group>
                                                <Progress value={benchStatus.data?.pct ?? activeBenchmark.data?.pct ?? 0} color="blue" />
                                            </div>
                                            {['running', 'queued', 'partial', 'cancelling'].includes((benchStatus.data?.status || activeBenchmark.data?.status || '').toLowerCase()) && (
                                                <Button
                                                    variant="light"
                                                    size="xs"
                                                    color="red"
                                                    loading={cancelBench.isPending}
                                                    onClick={async () => {
                                                        if (!benchRunId) return;
                                                        if (!confirm('Benchmark wirklich abbrechen?')) return;
                                                        try {
                                                            await cancelBench.mutateAsync(benchRunId);
                                                        } catch {
                                                            /* notification via interceptor */
                                                        }
                                                    }}
                                                >
                                                    {(benchStatus.data?.status || activeBenchmark.data?.status || '').toLowerCase() === 'cancelling' ? 'Abbruch läuft…' : 'Abbrechen'}
                                                </Button>
                                            )}
                                        </Group>
                                    )}
                                </Card>
                            ) : null}
                        </Accordion.Panel>
                    </Accordion.Item>
                )}

                {/* Benchmark Runs */}
                {runs && runs.length > 0 && (
                    <Accordion.Item value="benchmark">
                        <Accordion.Control>
                            <Group gap="sm">
                                <IconPlayerPlay size={20} color="#228be6" />
                                <Text fw={600}>Benchmark-Runs</Text>
                                <Badge variant="light" color="blue" size="sm">{runs.length} Runs</Badge>
                            </Group>
                        </Accordion.Control>
                        <Accordion.Panel>
                            {(() => {
                                // Runs nach Modell gruppieren
                                const groupedRuns = runs.reduce((acc, run) => {
                                    const modelName = run.model_name || 'Unbekanntes Modell';
                                    if (!acc[modelName]) {
                                        acc[modelName] = [];
                                    }
                                    acc[modelName].push(run);
                                    return acc;
                                }, {} as Record<string, typeof runs>);
                                
                                const modelNames = Object.keys(groupedRuns).sort();
                                const hasMultipleModels = modelNames.length > 1;
                                
                                // Wenn nur ein Modell, dann einfach die Tabelle anzeigen
                                if (!hasMultipleModels) {
                                    return <DatasetRunsTable datasetId={idNum} runs={runs} />;
                                }
                                
                                // Mehrere Modelle: Kompaktes Accordion
                                return (
                                    <Accordion 
                                        variant="contained" 
                                        defaultValue={null}
                                        styles={{
                                            item: { borderBottom: 'none' },
                                            control: { padding: '8px 12px' },
                                            panel: { padding: '0 12px 12px' },
                                        }}
                                    >
                                        {modelNames.map((modelName) => {
                                            const modelRuns = groupedRuns[modelName];
                                            return (
                                                <Accordion.Item key={modelName} value={modelName}>
                                                    <Accordion.Control>
                                                        <Group gap="xs">
                                                            <IconCpu size={14} color="#228be6" />
                                                            <Text size="sm" fw={500}>{modelName}</Text>
                                                            <Badge variant="light" color="blue" size="xs">{modelRuns.length}</Badge>
                                                        </Group>
                                                    </Accordion.Control>
                                                    <Accordion.Panel>
                                                        <DatasetRunsTable datasetId={idNum} runs={modelRuns} />
                                                    </Accordion.Panel>
                                                </Accordion.Item>
                                            );
                                        })}
                                    </Accordion>
                                );
                            })()}
                        </Accordion.Panel>
                    </Accordion.Item>
                )}
            </Accordion>

            {/* Leere States außerhalb des Accordions */}
            {isLoadingRuns && (
                <Text c="dimmed" py="md">Runs werden geladen…</Text>
            )}
            {!isLoadingRuns && runs && runs.length === 0 && (
                <Card withBorder mb="lg" padding="md" style={{ 
                    background: isDark ? 'rgba(134, 142, 150, 0.05)' : 'rgba(134, 142, 150, 0.03)',
                }}>
                    <Group gap="sm">
                        <IconPlayerPlay size={16} color={isDark ? '#909296' : '#868e96'} />
                        <Text c="dimmed">Noch keine Benchmark-Runs mit diesem Dataset.</Text>
                    </Group>
                </Card>
            )}

            {/* Charts zur Zusammensetzung */}
            {isLoading || !data ? (
                <Card withBorder padding="lg">
                    <Group gap="sm" mb="md">
                        <IconChartBar size={20} color="#12b886" />
                        <Title order={4}>Zusammensetzung</Title>
                    </Group>
                    <Text c="dimmed">Charts werden geladen…</Text>
                </Card>
            ) : (
                <>
                    {/* KPI Cards */}
                    <Card withBorder padding="lg" mb="lg">
                        <Group gap="sm" mb="md">
                            <IconChartBar size={20} color="#12b886" />
                            <Title order={4}>Übersicht</Title>
                            <Badge variant="light" color="teal" size="sm">n={totalPersonas.toLocaleString('de-DE')}</Badge>
                        </Group>
                        <Grid>
                            <Grid.Col span={{ base: 6, sm: 4, md: 2 }}>
                                <Card withBorder padding="sm" style={{ background: isDark ? 'rgba(34, 139, 230, 0.08)' : 'rgba(34, 139, 230, 0.05)', textAlign: 'center' }}>
                                    <IconUsers size={24} color="#228be6" style={{ marginBottom: 4 }} />
                                    <Text size="xl" fw={700}>{totalPersonas.toLocaleString('de-DE')}</Text>
                                    <Text size="xs" c="dimmed">Personas</Text>
                                </Card>
                            </Grid.Col>
                            {avgAge && (
                                <Grid.Col span={{ base: 6, sm: 4, md: 2 }}>
                                    <Card withBorder padding="sm" style={{ background: isDark ? 'rgba(250, 82, 82, 0.08)' : 'rgba(250, 82, 82, 0.05)', textAlign: 'center' }}>
                                        <IconCalendar size={24} color="#fa5252" style={{ marginBottom: 4 }} />
                                        <Text size="xl" fw={700}>{avgAge}</Text>
                                        <Text size="xs" c="dimmed">Ø Alter</Text>
                                    </Card>
                                </Grid.Col>
                            )}
                            {genderPcts.map((g, i) => (
                                <Grid.Col key={g.value} span={{ base: 6, sm: 4, md: 2 }}>
                                    <Card withBorder padding="sm" style={{ background: isDark ? 'rgba(64, 192, 87, 0.08)' : 'rgba(64, 192, 87, 0.05)', textAlign: 'center' }}>
                                        <IconGenderBigender size={24} color={CHART_COLORS.gender[i] || '#40c057'} style={{ marginBottom: 4 }} />
                                        <Text size="xl" fw={700}>{g.pct}%</Text>
                                        <Text size="xs" c="dimmed">{g.value}</Text>
                                    </Card>
                                </Grid.Col>
                            ))}
                        </Grid>
                    </Card>

                    {/* Demografie */}
                    <Card withBorder padding="lg" mb="lg">
                        <Group gap="sm" mb="md">
                            <IconUsers size={20} color="#228be6" />
                            <Title order={4}>Demografie</Title>
                        </Group>
                        <Grid>
                            {/* Linke Spalte: 3 Donut-Charts */}
                            <Grid.Col span={{ base: 12, lg: 5 }}>
                                <Grid>
                                    <Grid.Col span={12}>
                                        <ChartPanel 
                                            title="Geschlecht" 
                                            data={toDonut(gender, { colors: CHART_COLORS.gender })} 
                                            height={240}
                                        />
                                    </Grid.Col>
                                    <Grid.Col span={6}>
                                        <ChartPanel 
                                            title="Familienstand" 
                                            data={toDonut(marriage, { colors: CHART_COLORS.marriage })} 
                                            height={220}
                                        />
                                    </Grid.Col>
                                    <Grid.Col span={6}>
                                        <ChartPanel 
                                            title="Sexualität" 
                                            data={toDonut(sexuality, { colors: CHART_COLORS.sexuality })} 
                                            height={220}
                                        />
                                    </Grid.Col>
                                </Grid>
                            </Grid.Col>
                            {/* Rechte Spalte: Alterspyramide */}
                            <Grid.Col span={{ base: 12, lg: 7 }}>
                                <ChartPanel 
                                    title="Alterspyramide" 
                                    data={traces} 
                                    layout={{ 
                                        barmode: 'relative', 
                                        xaxis: { title: { text: 'Anzahl' }, tickformat: '', separatethousands: true }, 
                                        yaxis: { title: { text: 'Alter' } },
                                        bargap: 0.05,
                                        legend: { orientation: 'h', y: 1.1 },
                                    }} 
                                    height={500}
                                />
                            </Grid.Col>
                        </Grid>
                    </Card>

                    {/* Herkunft */}
                    <Card withBorder padding="lg" mb="lg">
                        <Group gap="sm" mb="md">
                            <IconWorld size={20} color="#15aabf" />
                            <Title order={4}>Herkunft & Migration</Title>
                        </Group>
                        <Grid>
                            <Grid.Col span={{ base: 12, md: 6 }}>
                                <ChartPanel 
                                    title="Herkunftsregion" 
                                    data={toDonut(originRegion, { colors: CHART_COLORS.region })} 
                                    height={300}
                                />
                            </Grid.Col>
                            <Grid.Col span={{ base: 12, md: 6 }}>
                                {migration.length > 0 ? (
                                    <ChartPanel 
                                        title="Migrationshintergrund" 
                                        data={toDonut(migration, { colors: ['#15aabf', '#fab005'], legendOnly: true })} 
                                        height={300}
                                    />
                                ) : (
                                    <div>
                                        <h3 style={{ marginBottom: 8, color: isDark ? '#c1c2c5' : '#212529' }}>Migrationshintergrund</h3>
                                        <Card withBorder padding="xl" style={{ 
                                            height: 260, 
                                            display: 'flex', 
                                            alignItems: 'center', 
                                            justifyContent: 'center',
                                            background: isDark ? 'rgba(134, 142, 150, 0.05)' : 'rgba(134, 142, 150, 0.03)'
                                        }}>
                                            <Text c="dimmed" ta="center">Keine Migrationsdaten verfügbar</Text>
                                        </Card>
                                    </div>
                                )}
                            </Grid.Col>
                        </Grid>
                        <div style={{ marginTop: 16 }}>
                            <ChartPanel 
                                title="Herkunftsländer (Top 15)" 
                                data={toBar(originCountry.slice(0, 15), { horizontal: true, color: '#15aabf' })} 
                                height={Math.max(280, originCountry.slice(0, 15).length * 26)}
                            />
                        </div>
                    </Card>

                    {/* Soziales */}
                    <Card withBorder padding="lg">
                        <Group gap="sm" mb="md">
                            <IconSchool size={20} color="#7950f2" />
                            <Title order={4}>Bildung & Religion</Title>
                        </Group>
                        <Grid>
                            <Grid.Col span={{ base: 12, md: 6 }}>
                                <ChartPanel 
                                    title="Bildungsabschluss" 
                                    data={toBar(education, { horizontal: true, color: '#12b886' })} 
                                    height={Math.max(250, education.length * 35)}
                                />
                            </Grid.Col>
                            <Grid.Col span={{ base: 12, md: 6 }}>
                                <ChartPanel 
                                    title="Religion" 
                                    data={toBar(religion, { horizontal: true, color: '#fab005' })} 
                                    height={Math.max(250, religion.length * 35)}
                                />
                            </Grid.Col>
                        </Grid>
                    </Card>
                </>
            )}
        </Card>
        <AttrGenModal
          opened={modalOpen}
          onClose={() => setModalOpen(false)}
          datasetId={idNum}
          availableModels={availableModels?.map(m => m.name)}
          onStarted={(rid) => setRunId(rid)}
        />
        {/* Benchmark Modal */}
        <BenchmarkModal
          opened={benchModalOpen}
          onClose={() => { setBenchModalOpen(false); setAttrgenRunForBenchmark(undefined); setBenchInitialModelName(undefined); }}
          datasetId={idNum}
          initialModelName={benchInitialModelName}
          attrgenRunId={attrgenRunForBenchmark}
          onStarted={(rid) => setBenchRunId(rid)}
        />
        </>
    );
}
