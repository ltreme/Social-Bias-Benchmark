import { useEffect, useRef } from 'react';
import { useMutation, useQuery, useQueryClient, useQueries } from '@tanstack/react-query';
import { fetchRunDeltas, fetchRunForest, fetchRunMetrics, fetchRuns, startRun, fetchRun, deleteRun as apiDeleteRun, fetchRunMissing, fetchRunOrderMetrics, fetchRunMeans, startRunWarmup, fetchRunWarmupStatus } from './api';

export function useRuns(status?: string) {
    return useQuery({ queryKey: ['runs'], queryFn: () => fetchRuns(), refetchInterval: 10000 });
}

export function useRun(runId: number) {
    return useQuery({ queryKey: ['run', runId], queryFn: () => fetchRun(runId), enabled: Number.isFinite(runId), staleTime: 60 * 60 * 1000 });
}

export function useStartRun() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: startRun,
        onSuccess: () => qc.invalidateQueries({ queryKey: ['runs'] }),
    });
}

export function useRunMetrics(runId: number, opts?: { enabled?: boolean }) {
    const enabled = Number.isFinite(runId) && (opts?.enabled ?? true);
    return useQuery({ queryKey: ['run-metrics', runId], queryFn: () => fetchRunMetrics(runId), enabled, staleTime: 60 * 60 * 1000 });
}

export function useRunDeltas(runId: number, attribute: string, baseline?: string, opts?: { enabled?: boolean }) {
    const enabled = Number.isFinite(runId) && !!attribute && (opts?.enabled ?? true);
    return useQuery({ queryKey: ['run-deltas', runId, attribute, baseline], queryFn: () => fetchRunDeltas(runId, { attribute, baseline }), enabled, staleTime: 60 * 60 * 1000 });
}

export function useRunForest(runId: number, attribute: string, baseline?: string, target?: string, opts?: { enabled?: boolean }) {
    const enabled = Number.isFinite(runId) && !!attribute && !!target && (opts?.enabled ?? true);
    return useQuery({ queryKey: ['run-forest', runId, attribute, baseline, target], queryFn: () => fetchRunForest(runId, { attribute, baseline, target, min_n: 1 }), enabled, staleTime: 60 * 60 * 1000 });
}

export function useRunForests(runId: number, attribute: string, baseline: string | undefined, targets: string[], opts?: { enabled?: boolean }) {
    const ready = Number.isFinite(runId) && !!attribute && (opts?.enabled ?? true);
    const queries = useQueries({
        queries: (targets || []).map((t) => ({
            queryKey: ['run-forest', runId, attribute, baseline, t],
            queryFn: () => fetchRunForest(runId, { attribute, baseline, target: t, min_n: 1 }),
            enabled: ready && !!t,
            staleTime: 60 * 60 * 1000,
        })),
    });
    return queries;
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

export function useRunMissing(runId: number, opts?: { enabled?: boolean }) {
    // Missing paare ändern sich nur wenn der Run noch läuft – hier nicht refetchen
    const enabled = Number.isFinite(runId) && (opts?.enabled ?? true);
    return useQuery({ queryKey: ['run-missing', runId], queryFn: () => fetchRunMissing(runId), enabled, staleTime: 60 * 60 * 1000 });
}

export function useRunOrderMetrics(runId: number, opts?: { enabled?: boolean }) {
    const enabled = Number.isFinite(runId) && (opts?.enabled ?? true);
    return useQuery({ queryKey: ['run-order-metrics', runId], queryFn: () => fetchRunOrderMetrics(runId), enabled, staleTime: 60 * 60 * 1000 });
}

export function useRunMeans(runId: number, attribute: string, topN?: number, opts?: { enabled?: boolean }) {
    const enabled = Number.isFinite(runId) && !!attribute && (opts?.enabled ?? true);
    return useQuery({ queryKey: ['run-means', runId, attribute, topN], queryFn: () => fetchRunMeans(runId, attribute, topN), enabled, staleTime: 60 * 60 * 1000 });
}

export function useRunWarmup(runId: number) {
    const startedRef = useRef<number | null>(null);
    const start = useMutation({
        mutationFn: (rid: number) => startRunWarmup(rid),
    });
    const status = useQuery({
        queryKey: ['run-warmup', runId],
        queryFn: () => fetchRunWarmupStatus(runId),
        enabled: Number.isFinite(runId),
        refetchInterval: (data) =>
            !data || data.status === 'running' || data.status === 'idle' ? 2000 : false,
        refetchIntervalInBackground: true,
    });
    const triggerWarmup = start.mutate;
    useEffect(() => {
        if (!Number.isFinite(runId)) return;
        if (startedRef.current === runId) return;
        triggerWarmup(runId);
        startedRef.current = runId;
    }, [runId, triggerWarmup]);
    return { start, status };
}
