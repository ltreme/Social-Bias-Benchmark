import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchRunDeltas, fetchRunForest, fetchRunMetrics, fetchRuns, startRun, fetchRun, deleteRun as apiDeleteRun, fetchRunMissing, fetchRunOrderMetrics } from './api';

export function useRuns(status?: string) {
    return useQuery({ queryKey: ['runs'], queryFn: () => fetchRuns(), refetchInterval: 10000 });
}

export function useRun(runId: number) {
    return useQuery({ queryKey: ['run', runId], queryFn: () => fetchRun(runId), enabled: Number.isFinite(runId) });
}

export function useStartRun() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: startRun,
        onSuccess: () => qc.invalidateQueries({ queryKey: ['runs'] }),
    });
}

export function useRunMetrics(runId: number) {
    return useQuery({ queryKey: ['run-metrics', runId], queryFn: () => fetchRunMetrics(runId), enabled: Number.isFinite(runId) });
}

export function useRunDeltas(runId: number, attribute: string, baseline?: string) {
    return useQuery({ queryKey: ['run-deltas', runId, attribute, baseline], queryFn: () => fetchRunDeltas(runId, { attribute, baseline }), enabled: Number.isFinite(runId) && !!attribute });
}

export function useRunForest(runId: number, attribute: string, baseline?: string, target?: string) {
    return useQuery({ queryKey: ['run-forest', runId, attribute, baseline, target], queryFn: () => fetchRunForest(runId, { attribute, baseline, target, min_n: 1 }), enabled: Number.isFinite(runId) && !!attribute && !!target });
}

export function useDeleteRun() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (runId: number) => apiDeleteRun(runId),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['runs'] });
            // dataset-runs queries have key ['dataset-runs', datasetId]; callers can optionally invalidate explicitly
        },
    });
}

export function useRunMissing(runId: number) {
    return useQuery({ queryKey: ['run-missing', runId], queryFn: () => fetchRunMissing(runId), enabled: Number.isFinite(runId), refetchInterval: 10000 });
}

export function useRunOrderMetrics(runId: number) {
    return useQuery({ queryKey: ['run-order-metrics', runId], queryFn: () => fetchRunOrderMetrics(runId), enabled: Number.isFinite(runId) });
}
