import { Card, Text, Title, Button, Group, Stack, Badge, Alert } from '@mantine/core';
import { IconRefresh, IconCheck, IconClock, IconAlertCircle } from '@tabler/icons-react';
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
            <Card withBorder padding="md">
                <Group justify="space-between" align="center">
                    <div>
                        <Title order={4}>Order-Consistency Analyse</Title>
                        <Text size="sm" c="dimmed" mt={4}>
                            Vollständige Berechnung aller Metriken für Dual-Paare (in/rev Scale-Order)
                        </Text>
                    </div>
                    <Group gap="sm">
                        {getAnalysisStatusBadge(status)}
                        <Button
                            leftSection={<IconRefresh size={16} />}
                            onClick={onRequestAnalysis}
                            loading={isRequestingAnalysis || isRunning}
                            disabled={isRunning}
                            variant={status === 'completed' ? 'light' : 'filled'}
                        >
                            {status === 'completed' ? 'Neu berechnen' : 'Analysieren'}
                        </Button>
                    </Group>
                </Group>
                {orderAnalysis?.error && (
                    <Alert color="red" title="Fehler" mt="sm">
                        {orderAnalysis.error}
                    </Alert>
                )}
                {orderAnalysis?.duration_ms && status === 'completed' && (
                    <Text size="xs" c="dimmed" mt="sm">
                        Berechnet am {new Date(orderAnalysis.completed_at! + 'Z').toLocaleString()} 
                        ({(orderAnalysis.duration_ms / 1000).toFixed(1)}s)
                    </Text>
                )}
            </Card>

            {/* Full Order Metrics from warm-cache (existing) */}
            <AsyncContent isLoading={isLoadingOrder} isError={!!orderError} error={orderError}>
                <OrderMetricsCard data={orderMetrics} />
            </AsyncContent>

            {/* Deep Analysis Results (when available) */}
            {summary && (
                <Card withBorder padding="md">
                    <Title order={4} mb="sm">Deep-Analysis Ergebnisse</Title>
                    <Text size="sm" c="dimmed" mb="md">
                        Vollständige Analyse über alle {summary.n_dual_pairs?.toLocaleString()} Dual-Paare
                    </Text>
                    
                    {/* Per-Case Breakdown */}
                    {summary.per_case && summary.per_case.length > 0 && (
                        <div style={{ overflowX: 'auto' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                                <thead>
                                    <tr style={{ borderBottom: '2px solid var(--mantine-color-gray-3)' }}>
                                        <th style={{ textAlign: 'left', padding: '8px 4px' }}>Case</th>
                                        <th style={{ textAlign: 'left', padding: '8px 4px' }}>Adjektiv</th>
                                        <th style={{ textAlign: 'right', padding: '8px 4px' }}>n Paare</th>
                                        <th style={{ textAlign: 'right', padding: '8px 4px' }}>RMA</th>
                                        <th style={{ textAlign: 'right', padding: '8px 4px' }}>MAE</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {summary.per_case.slice(0, 20).map((row: any, idx: number) => (
                                        <tr key={row.case_id || idx} style={{ borderBottom: '1px solid var(--mantine-color-gray-2)' }}>
                                            <td style={{ padding: '8px 4px' }}>{row.case_id}</td>
                                            <td style={{ padding: '8px 4px' }}>{row.adjective || '–'}</td>
                                            <td style={{ textAlign: 'right', padding: '8px 4px' }}>{row.n_pairs}</td>
                                            <td style={{ textAlign: 'right', padding: '8px 4px' }}>
                                                {row.exact_rate != null ? row.exact_rate.toFixed(3) : '–'}
                                            </td>
                                            <td style={{ textAlign: 'right', padding: '8px 4px' }}>
                                                {row.mae != null ? row.mae.toFixed(3) : '–'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                            {summary.per_case.length > 20 && (
                                <Text size="xs" c="dimmed" mt="xs">
                                    ... und {summary.per_case.length - 20} weitere Cases
                                </Text>
                            )}
                        </div>
                    )}
                </Card>
            )}
        </Stack>
    );
}
