import { Text, Stack } from '@mantine/core';
import { AsyncContent } from '../../../components/AsyncContent';
import { OrderMetricsCard } from './OrderMetricsCard';
import type { OrderMetrics } from '../api';

type OrderConsistencyTabProps = {
    orderMetrics?: OrderMetrics | null;
    isLoadingOrder: boolean;
    orderError?: any;
};

export function OrderConsistencyTab({
    orderMetrics,
    isLoadingOrder,
    orderError,
}: OrderConsistencyTabProps) {
    return (
        <Stack gap="md">
            <AsyncContent isLoading={isLoadingOrder} isError={!!orderError} error={orderError}>
                <OrderMetricsCard data={orderMetrics} />
            </AsyncContent>
        </Stack>
    );
}
