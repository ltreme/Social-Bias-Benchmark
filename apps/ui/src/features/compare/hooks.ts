import { useQuery } from '@tanstack/react-query';
import { fetchMetrics } from './api';

export function useMetrics(models: string[], datasets: string[]) {
    const datasetIds = datasets.length > 0 ? datasets.map(Number) : undefined;
    const modelNames = models.length > 0 ? models : undefined;
    return useQuery({ queryKey: ['metrics', { dataset_ids: datasetIds, models: modelNames, case_ids: [], rationale: false }], queryFn: () => fetchMetrics({ dataset_ids: datasetIds, models: modelNames, case_ids: [], rationale: false }), enabled: true });
}