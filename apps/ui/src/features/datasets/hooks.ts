import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchDatasets, fetchDatasetComposition, fetchDataset, fetchRunsByDataset, createPool, buildBalanced, sampleReality, buildCounterfactuals, startAttrGen, fetchAttrgenStatus, fetchLatestAttrgen, fetchAttrgenRuns, startBenchmark, fetchBenchmarkStatus, deleteDataset, deleteAttrgenRun, fetchPoolStatus, fetchBalancedStatus, fetchDeleteStatus, cancelBenchmark, fetchActiveBenchmark } from './api';

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

export function usePoolStatus(jobId?: number) {
    return useQuery({ queryKey: ['pool-status', jobId], queryFn: () => fetchPoolStatus(jobId as number), enabled: Number.isFinite(jobId || NaN), refetchInterval: 1000 });
}

export function useBuildBalanced() {
    return useMutation({ mutationFn: buildBalanced });
}

export function useBalancedStatus(jobId?: number) {
    return useQuery({ queryKey: ['balanced-status', jobId], queryFn: () => fetchBalancedStatus(jobId as number), enabled: Number.isFinite(jobId || NaN), refetchInterval: 1000 });
}

export function useSampleReality() {
    return useMutation({ mutationFn: sampleReality });
}

export function useBuildCounterfactuals() {
    return useMutation({ mutationFn: buildCounterfactuals });
}

export function useStartAttrgen() {
    return useMutation({ mutationFn: startAttrGen });
}

export function useAttrgenStatus(runId?: number) {
    return useQuery({ queryKey: ['attrgen-status', runId], queryFn: () => fetchAttrgenStatus(runId!), enabled: !!runId, refetchInterval: 2000 });
}

export function useLatestAttrgen(datasetId?: number) {
    return useQuery({ queryKey: ['attrgen-latest', datasetId], queryFn: () => fetchLatestAttrgen(datasetId!), enabled: Number.isFinite(datasetId || NaN), refetchInterval: 5000 });
}

export function useAttrgenRuns(datasetId?: number) {
    return useQuery({ queryKey: ['attrgen-runs', datasetId], queryFn: () => fetchAttrgenRuns(datasetId!), enabled: Number.isFinite(datasetId || NaN), refetchInterval: 10000 });
}

export function useStartBenchmark() {
    return useMutation({ mutationFn: startBenchmark });
}

export function useBenchmarkStatus(runId?: number) {
    return useQuery({
        queryKey: ['bench-status', runId],
        queryFn: () => fetchBenchmarkStatus(runId!),
        enabled: !!runId,
        refetchInterval: (data) => {
            const status = (data?.status || '').toLowerCase();
            return ['queued', 'running', 'partial', 'cancelling'].includes(status) ? 2000 : false;
        },
    });
}

export function useCancelBenchmark() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (runId: number) => cancelBenchmark(runId),
        onSuccess: (_res, runId) => {
            qc.invalidateQueries({ queryKey: ['bench-status', runId] });
            qc.invalidateQueries({ queryKey: ['bench-active'] });
        },
    });
}

export function useActiveBenchmark(datasetId?: number) {
    return useQuery({
        queryKey: ['bench-active', datasetId],
        queryFn: () => fetchActiveBenchmark(datasetId!),
        enabled: Number.isFinite(datasetId || NaN),
        refetchInterval: 2000,
    });
}

export function useDeleteDataset() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (datasetId: number) => deleteDataset(datasetId),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['datasets'] });
        },
    });
}

export function useDeleteStatus(jobId?: number) {
    return useQuery({ queryKey: ['delete-status', jobId], queryFn: () => fetchDeleteStatus(jobId as number), enabled: Number.isFinite(jobId || NaN), refetchInterval: 1000 });
}

export function useDeleteAttrgenRun(datasetId: number) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (runId: number) => deleteAttrgenRun(runId),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['attrgen-runs', datasetId] });
            qc.invalidateQueries({ queryKey: ['attrgen-latest', datasetId] });
        },
    });
}
