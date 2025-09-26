import { useMutation, useQuery } from '@tanstack/react-query';
import { fetchDatasets, fetchDatasetComposition, fetchDataset, fetchRunsByDataset, createPool, buildBalanced, sampleReality, buildCounterfactuals } from './api';

export function useDatasets(q?: string) {
    return useQuery({ queryKey: ['datasets', q], queryFn: () => fetchDatasets(q ? { q } : undefined) });
}

export function useDataset(datasetId: number) {
    return useQuery({ queryKey: ['dataset', datasetId], queryFn: () => fetchDataset(datasetId), enabled: Number.isFinite(datasetId) });
}

export function useDatasetComposition(datasetId: number) {
    return useQuery({ queryKey: ['dataset-composition', datasetId], queryFn: () => fetchDatasetComposition(datasetId), enabled: Number.isFinite(datasetId) });
}

export function useDatasetRuns(datasetId: number) {
    return useQuery({ queryKey: ['dataset-runs', datasetId], queryFn: () => fetchRunsByDataset(datasetId), enabled: Number.isFinite(datasetId) });
}

export function useCreatePool() {
    return useMutation({ mutationFn: createPool });
}

export function useBuildBalanced() {
    return useMutation({ mutationFn: buildBalanced });
}

export function useSampleReality() {
    return useMutation({ mutationFn: sampleReality });
}

export function useBuildCounterfactuals() {
    return useMutation({ mutationFn: buildCounterfactuals });
}
