import { Text, Title, Button, Group, Stack, Badge, Alert, Paper, ThemeIcon, Table, ScrollArea } from '@mantine/core';
import { IconRefresh, IconCheck, IconClock, IconAlertCircle, IconAnalyze } from '@tabler/icons-react';
import { AsyncContent } from '../../../components/AsyncContent';
import { OrderMetricsCard } from './OrderMetricsCard';
import type { OrderMetrics, AnalysisStatus } from '../api';

type OrderConsistencyTabProps = {
    orderMetrics?: OrderMetrics | null;
    isLoadingOrder: boolean;
    orderError?: any;
    analysisStatus?: AnalysisStatus | null;
    onRequestAnalysis: () => void;
    isRequestingAnalysis: boolean;
};

function getAnalysisStatusBadge(status?: string) {
    switch (status) {
        case 'completed':
            return <Badge color="green" leftSection={<IconCheck size={12} />}>Fertig</Badge>;
        case 'running':
            return <Badge color="blue" leftSection={<IconClock size={12} />}>Läuft...</Badge>;
        case 'pending':
            return <Badge color="yellow" leftSection={<IconClock size={12} />}>In Warteschlange</Badge>;
        case 'failed':
            return <Badge color="red" leftSection={<IconAlertCircle size={12} />}>Fehlgeschlagen</Badge>;
        default:
            return <Badge color="gray">Nicht berechnet</Badge>;
    }
}

export function OrderConsistencyTab({
    orderMetrics,
    isLoadingOrder,
    orderError,
    analysisStatus,
    onRequestAnalysis,
    isRequestingAnalysis,
}: OrderConsistencyTabProps) {
    const orderAnalysis = analysisStatus?.analyses?.['order'];
    const status = orderAnalysis?.status;
    const isRunning = status === 'running' || status === 'pending';
    const summary = orderAnalysis?.summary;

    return (
        <Stack gap="md">
            {/* Analysis Status & Request Button */}
            <Paper p="md" withBorder radius="md">
                <Group justify="space-between" align="flex-start">
                    <Group gap="sm">
                        <ThemeIcon size={44} radius="md" variant="light" color="indigo">
                            <IconAnalyze size={24} />
                        </ThemeIcon>
                        <div>
                            <Title order={4}>Order-Consistency Analyse</Title>
                            <Text size="sm" c="dimmed">
                                Vollständige Berechnung aller Metriken für Dual-Paare
                            </Text>
                        </div>
                    </Group>
                    <Stack gap="xs" align="flex-end">
                        <Group gap="sm">
                            {getAnalysisStatusBadge(status)}
                            <Button
                                leftSection={<IconRefresh size={16} />}
                                onClick={onRequestAnalysis}
                                loading={isRequestingAnalysis || isRunning}
                                disabled={isRunning}
                                variant={status === 'completed' ? 'light' : 'filled'}
                                size="sm"
                            >
                                {status === 'completed' ? 'Neu berechnen' : 'Analysieren'}
                            </Button>
                        </Group>
                        {orderAnalysis?.duration_ms && status === 'completed' && (
                            <Text size="xs" c="dimmed">
                                Berechnet am {new Date(orderAnalysis.completed_at! + 'Z').toLocaleString('de-DE')} 
                                ({(orderAnalysis.duration_ms / 1000).toFixed(1)}s)
                            </Text>
                        )}
                    </Stack>
                </Group>
                {orderAnalysis?.error && (
                    <Alert color="red" title="Fehler" mt="md">
                        {orderAnalysis.error}
                    </Alert>
                )}
            </Paper>

            {/* Full Order Metrics from warm-cache (existing) */}
            <AsyncContent isLoading={isLoadingOrder} isError={!!orderError} error={orderError}>
                <OrderMetricsCard data={orderMetrics} />
            </AsyncContent>

            {/* Deep Analysis Results (when available) */}
            {summary && (
                <Paper p="md" withBorder radius="md">
                    <Group gap="sm" mb="md">
                        <ThemeIcon size="lg" radius="md" variant="light" color="cyan">
                            <IconAnalyze size={20} />
                        </ThemeIcon>
                        <div>
                            <Title order={4}>Deep-Analysis Ergebnisse</Title>
                            <Text size="sm" c="dimmed">
                                Vollständige Analyse über alle {summary.n_dual_pairs?.toLocaleString('de-DE')} Dual-Paare
                            </Text>
                        </div>
                    </Group>
                    
                    {/* Per-Trait Breakdown */}
                    {summary.per_case && summary.per_case.length > 0 && (
                        <ScrollArea>
                            <Table striped highlightOnHover withTableBorder>
                                <Table.Thead>
                                    <Table.Tr>
                                        <Table.Th>Trait</Table.Th>
                                        <Table.Th ta="right">n Paare</Table.Th>
                                        <Table.Th ta="right">RMA</Table.Th>
                                        <Table.Th ta="right">MAE</Table.Th>
                                    </Table.Tr>
                                </Table.Thead>
                                <Table.Tbody>
                                    {summary.per_case.map((row: any, idx: number) => (
                                        <Table.Tr key={row.case_id || idx}>
                                            <Table.Td>{row.adjective || row.case_id}{row.case_id ? ` (${row.case_id})` : ''}</Table.Td>
                                            <Table.Td ta="right">{row.n_pairs}</Table.Td>
                                            <Table.Td ta="right">
                                                <Text 
                                                    size="sm" 
                                                    c={row.exact_rate >= 0.8 ? 'teal' : row.exact_rate >= 0.6 ? 'yellow.7' : 'red'}
                                                    fw={500}
                                                >
                                                    {row.exact_rate != null ? row.exact_rate.toFixed(3) : '–'}
                                                </Text>
                                            </Table.Td>
                                            <Table.Td ta="right">
                                                <Text 
                                                    size="sm" 
                                                    c={row.mae <= 0.3 ? 'teal' : row.mae <= 0.6 ? 'yellow.7' : 'red'}
                                                    fw={500}
                                                >
                                                    {row.mae != null ? row.mae.toFixed(3) : '–'}
                                                </Text>
                                            </Table.Td>
                                        </Table.Tr>
                                    ))}
                                </Table.Tbody>
                            </Table>
                        </ScrollArea>
                    )}
                </Paper>
            )}
        </Stack>
    );
}
