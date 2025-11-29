import { Card, Grid, Group, MultiSelect, Select, Stack, Text, Title, Button, Badge } from '@mantine/core';
import { IconRefresh, IconCheck, IconClock, IconAlertCircle } from '@tabler/icons-react';
import { AsyncContent } from '../../../components/AsyncContent';
import { AttributeBaselineSelector } from './AttributeBaselineSelector';
import { DeltaBarsPanel } from './DeltaBarsPanel';
import { MultiForestPlotPanel } from './MultiForestPlotPanel';
import { SignificanceTable } from './SignificanceTable';
import { MeansSummary } from './MeansSummary';
import type { RunDeltas, AnalysisStatus } from '../api';

const ATTRS = [
    { value: 'gender', label: 'Geschlecht' },
    { value: 'religion', label: 'Religion' },
    { value: 'sexuality', label: 'Sexualität' },
    { value: 'marriage_status', label: 'Familienstand' },
    { value: 'education', label: 'Bildung' },
    { value: 'origin_subregion', label: 'Herkunft-Subregion' },
    { value: 'migration_status', label: 'Migrationshintergrund' },
];

type BiasTabProps = {
    // Attribute selection
    attribute: string;
    onAttributeChange: (attr: string) => void;
    availableCategories: Array<{ category: string; count: number; mean: number }>;
    baseline?: string;
    defaultBaseline?: string;
    onBaselineChange: (baseline: string | null) => void;
    targets: string[];
    onTargetsChange: (targets: string[]) => void;
    // Trait category filter
    traitCategoryOptions: string[];
    traitCategory: string;
    onTraitCategoryChange: (cat: string) => void;
    // Data
    deltas?: RunDeltas;
    isLoadingDeltas: boolean;
    deltasError?: any;
    forestsQueries: Array<{ data?: any; isLoading: boolean; isError: boolean; error?: any }>;
    // All means & deltas for summary
    meansData: Array<{ a: string; q: { data?: { rows: any[] }; isLoading: boolean; isError: boolean; error?: any } }>;
    deltasData: Array<{ a: string; q: { data?: RunDeltas; isLoading: boolean; isError: boolean; error?: any } }>;
    // Analysis status
    analysisStatus?: AnalysisStatus | null;
    onRequestBiasAnalysis: (attribute: string) => void;
    isRequestingAnalysis: boolean;
};

function getAnalysisStatusBadge(status?: string) {
    switch (status) {
        case 'completed':
            return <Badge color="green" size="xs" leftSection={<IconCheck size={10} />}>Fertig</Badge>;
        case 'running':
            return <Badge color="blue" size="xs" leftSection={<IconClock size={10} />}>Läuft</Badge>;
        case 'pending':
            return <Badge color="yellow" size="xs" leftSection={<IconClock size={10} />}>Warteschlange</Badge>;
        case 'failed':
            return <Badge color="red" size="xs" leftSection={<IconAlertCircle size={10} />}>Fehler</Badge>;
        default:
            return null;
    }
}

export function BiasTab({
    attribute,
    onAttributeChange,
    availableCategories,
    baseline,
    defaultBaseline,
    onBaselineChange,
    targets,
    onTargetsChange,
    traitCategoryOptions,
    traitCategory,
    onTraitCategoryChange,
    deltas,
    isLoadingDeltas,
    deltasError,
    forestsQueries,
    meansData,
    deltasData,
    analysisStatus,
    onRequestBiasAnalysis,
    isRequestingAnalysis,
}: BiasTabProps) {
    const loadingForest = forestsQueries.length > 0 ? forestsQueries.some((q) => q.isLoading) : false;
    const errorForest = forestsQueries.length > 0 ? forestsQueries.some((q) => q.isError) : false;
    const forestError = forestsQueries.find((q) => q.isError)?.error;
    const attrLabel = ATTRS.find((x) => x.value === attribute)?.label || attribute;

    // Check analysis status for current attribute
    const biasAnalysisKey = `bias:${attribute}`;
    const biasAnalysis = analysisStatus?.analyses?.[biasAnalysisKey];
    const biasStatus = biasAnalysis?.status;
    const isBiasRunning = biasStatus === 'running' || biasStatus === 'pending';

    return (
        <Stack gap="md">
            {/* Attribute & Filter Selection */}
            <Card withBorder padding="md">
                <Group align="end" mb="sm" wrap="wrap">
                    <AttributeBaselineSelector
                        attributes={ATTRS}
                        attribute={attribute}
                        onAttributeChange={(v) => {
                            onAttributeChange(v);
                            onBaselineChange(null);
                            onTargetsChange([]);
                        }}
                        categories={availableCategories.map((c) => c.category)}
                        baseline={baseline}
                        defaultBaseline={defaultBaseline}
                        onBaselineChange={onBaselineChange}
                    />
                    <Select
                        label="Trait-Kategorie"
                        data={[{ value: '__all', label: 'Alle Kategorien' }, ...traitCategoryOptions.map((c) => ({ value: c, label: c }))]}
                        value={traitCategory}
                        onChange={(val) => onTraitCategoryChange(val ?? '__all')}
                        style={{ minWidth: 220 }}
                    />
                    <MultiSelect
                        label="Forest: Kategorien"
                        data={availableCategories.map(c => ({ value: c.category, label: c.category })).filter(c => c.value !== (baseline || defaultBaseline))}
                        value={targets}
                        onChange={(vals) => onTargetsChange(vals)}
                        placeholder="Kategorien wählen"
                        searchable
                        style={{ minWidth: 280 }}
                        maxDropdownHeight={240}
                    />
                </Group>
                <Text size="sm" className="print-only" c="dimmed">
                    Einstellungen: Merkmal {attrLabel}; Baseline {baseline || defaultBaseline || 'auto'}; Kategorien: {targets.join(', ') || '—'}
                </Text>
            </Card>

            {/* Delta Bars & Forest Plot */}
            <Grid>
                <Grid.Col span={{ base: 12, md: 6 }}>
                    <AsyncContent isLoading={isLoadingDeltas} isError={!!deltasError} error={deltasError}>
                        <DeltaBarsPanel 
                            deltas={deltas as any} 
                            title={`Delta vs. Baseline (${baseline || defaultBaseline || 'auto'})`} 
                        />
                    </AsyncContent>
                </Grid.Col>
                <Grid.Col span={{ base: 12, md: 6 }}>
                    {targets.length > 0 ? (
                        <AsyncContent isLoading={loadingForest} isError={errorForest} error={forestError}>
                            <MultiForestPlotPanel
                                datasets={forestsQueries.map((q, i) => ({ 
                                    target: targets[i], 
                                    rows: (q.data as any)?.rows || [], 
                                    overall: (q.data as any)?.overall 
                                }))}
                                attr={attribute}
                                baseline={baseline}
                                defaultBaseline={defaultBaseline}
                            />
                        </AsyncContent>
                    ) : (
                        <Card withBorder padding="md" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <Text c="dimmed">Bitte Kategorie(n) für Forest wählen.</Text>
                        </Card>
                    )}
                </Grid.Col>
            </Grid>

            {/* Means Summary */}
            <Card withBorder padding="md">
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

            {/* Significance Tables */}
            <Card withBorder padding="md">
                <Group justify="space-between" align="center" mb="md">
                    <Title order={4}>Signifikanz-Tabellen (p, q, Cliff's δ)</Title>
                    <Group gap="sm">
                        {getAnalysisStatusBadge(biasStatus)}
                        <Button
                            size="xs"
                            leftSection={<IconRefresh size={14} />}
                            onClick={() => onRequestBiasAnalysis(attribute)}
                            loading={isRequestingAnalysis || isBiasRunning}
                            disabled={isBiasRunning}
                            variant="light"
                        >
                            Deep-Analyse
                        </Button>
                    </Group>
                </Group>
                {deltasData.map(({ a, q }) => (
                    <div key={a} style={{ marginTop: 12 }}>
                        <b>{ATTRS.find(x => x.value === a)?.label || a}</b>
                        <AsyncContent isLoading={q.isLoading} isError={q.isError} error={q.error}>
                            <SignificanceTable rows={q.data?.rows || []} />
                        </AsyncContent>
                    </div>
                ))}
            </Card>
        </Stack>
    );
}
