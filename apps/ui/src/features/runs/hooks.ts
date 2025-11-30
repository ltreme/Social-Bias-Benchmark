import { useEffect, useRef } from 'react';
import { useMutation, useQuery, useQueryClient, useQueries } from '@tanstack/react-query';
import { fetchRunDeltas, fetchRunForest, fetchRunMetrics, fetchRuns, startRun, fetchRun, deleteRun as apiDeleteRun, fetchRunMissing, fetchRunOrderMetrics, fetchRunMeans, startRunWarmup, fetchRunWarmupStatus, fetchAnalysisStatus, fetchQuickAnalysis, requestAnalysis, type AnalyzeRequest } from './api';

export function useRuns() {
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

export function useRunDeltas(runId: number, attribute: string, baseline?: string, opts?: { enabled?: boolean; traitCategory?: string }) {
    const enabled = Number.isFinite(runId) && !!attribute && (opts?.enabled ?? true);
    const traitCategory = opts?.traitCategory;
    return useQuery({
        queryKey: ['run-deltas', runId, attribute, baseline, traitCategory],
        queryFn: () => fetchRunDeltas(runId, { attribute, baseline, trait_category: traitCategory }),
        enabled,
        staleTime: 60 * 60 * 1000,
    });
}

export function useRunForest(runId: number, attribute: string, baseline?: string, target?: string, opts?: { enabled?: boolean; traitCategory?: string }) {
    const enabled = Number.isFinite(runId) && !!attribute && !!target && (opts?.enabled ?? true);
    const traitCategory = opts?.traitCategory;
    return useQuery({
        queryKey: ['run-forest', runId, attribute, baseline, target, traitCategory],
        queryFn: () => fetchRunForest(runId, { attribute, baseline, target, min_n: 1, trait_category: traitCategory }),
        enabled,
        staleTime: 60 * 60 * 1000,
    });
}

export function useRunForests(runId: number, attribute: string, baseline: string | undefined, targets: string[], opts?: { enabled?: boolean; traitCategory?: string }) {
    const ready = Number.isFinite(runId) && !!attribute && (opts?.enabled ?? true);
    const traitCategory = opts?.traitCategory;
    const queries = useQueries({
        queries: (targets || []).map((t) => ({
            queryKey: ['run-forest', runId, attribute, baseline, t, traitCategory],
            queryFn: () => fetchRunForest(runId, { attribute, baseline, target: t, min_n: 1, trait_category: traitCategory }),
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

export function useRunMeans(runId: number, attribute: string, topN?: number, opts?: { enabled?: boolean; traitCategory?: string }) {
    const enabled = Number.isFinite(runId) && !!attribute && (opts?.enabled ?? true);
    const traitCategory = opts?.traitCategory;
    return useQuery({
        queryKey: ['run-means', runId, attribute, topN, traitCategory],
        queryFn: () => fetchRunMeans(runId, attribute, topN, traitCategory),
        enabled,
        staleTime: 60 * 60 * 1000,
    });
}

export function useRunAllMeans(runId: number, opts?: { enabled?: boolean }) {
    const enabled = Number.isFinite(runId) && (opts?.enabled ?? true);
    return useQuery({
        queryKey: ['run-means-all', runId],
        queryFn: () => import('./api').then(m => m.fetchRunAllMeans(runId)),
        enabled,
        staleTime: 60 * 60 * 1000,
    });
}

export function useRunAllDeltas(runId: number, opts?: { enabled?: boolean }) {
    const enabled = Number.isFinite(runId) && (opts?.enabled ?? true);
    return useQuery({
        queryKey: ['run-deltas-all', runId],
        queryFn: () => import('./api').then(m => m.fetchRunAllDeltas(runId)),
        enabled,
        staleTime: 60 * 60 * 1000,
    });
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
        refetchInterval: (query) => {
            const s = (query.state.data?.status || '').toLowerCase();
            // Only poll while warmup is actually running (not partial - that's a benchmark status)
            return (!query.state.data || ['idle', 'queued', 'running'].includes(s)) ? 2000 : false;
        },
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

// ============================================================================
// Analysis Hooks (Queue-based)
// ============================================================================

export function useAnalysisStatus(runId: number, opts?: { enabled?: boolean; polling?: boolean }) {
    const enabled = Number.isFinite(runId) && (opts?.enabled ?? true);
    const polling = opts?.polling ?? false;
    return useQuery({
        queryKey: ['analysis-status', runId],
        queryFn: () => fetchAnalysisStatus(runId),
        enabled,
        staleTime: polling ? 0 : 30 * 1000,
        refetchInterval: polling ? 10000 : false, // Reduced from 3s to avoid DB exhaustion
    });
}

export function useQuickAnalysis(runId: number, opts?: { enabled?: boolean }) {
    const enabled = Number.isFinite(runId) && (opts?.enabled ?? true);
    return useQuery({
        queryKey: ['quick-analysis', runId],
        queryFn: () => fetchQuickAnalysis(runId),
        enabled,
        staleTime: 60 * 60 * 1000, // 1 hour - quick analysis rarely changes
    });
}

export function useRequestAnalysis() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ runId, request }: { runId: number; request: AnalyzeRequest }) =>
            requestAnalysis(runId, request),
        onSuccess: (_, { runId }) => {
            // Invalidate analysis status to trigger refetch
            qc.invalidateQueries({ queryKey: ['analysis-status', runId] });
        },
    });
}
