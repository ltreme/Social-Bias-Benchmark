import { api } from '../../lib/apiClient';

export type Run = {
    id: number;
    model_name: string;
    include_rationale: boolean;
    dataset_id?: number | null;
    created_at: string;
};

export type RunDetail = {
    id: number;
    model_name: string;
    include_rationale: boolean;
    dataset?: {
        id: number | null;
        name: string | null;
        kind: string | null;
    };
    created_at: string;
};

export async function fetchRuns() {
    const res = await api.get<Run[]>('/runs');
    return res.data;
}

export async function fetchRun(runId: number) {
    const res = await api.get<RunDetail>(`/runs/${runId}`);
    return res.data;
}

// Optional: unused unless backend supports starting runs
export async function startRun(body: { model_name: string; dataset_id: string }) {
    const res = await api.post<Run>('/runs', body);
    return res.data;
}

export type RunMetrics = {
    ok: boolean;
    n: number;
    hist: { bins: number[]; shares: number[] };
    attributes: Record<string, { baseline: string | null; categories: Array<{ category: string; count: number; mean: number }> }>;
};

export async function fetchRunMetrics(runId: number) {
    const res = await api.get<RunMetrics>(`/runs/${runId}/metrics`);
    return res.data;
}

export type RunDeltas = {
    ok: boolean;
    n: number;
    baseline?: string | null;
    rows: Array<{ category: string; count: number; mean: number; delta: number; p_value: number; significant: boolean; baseline: string }>;
};

export async function fetchRunDeltas(runId: number, params: { attribute: string; baseline?: string; n_perm?: number; alpha?: number }) {
    const res = await api.get<RunDeltas>(`/runs/${runId}/deltas`, { params });
    return res.data;
}

export type RunForest = {
    ok: boolean;
    n: number;
    rows: Array<{ case_id: string; label?: string; category: string; baseline: string; n_base: number; n_cat: number; delta: number; se: number | null; ci_low: number | null; ci_high: number | null }>;
    overall: { mean: number | null; ci_low: number | null; ci_high: number | null };
};

export async function fetchRunForest(runId: number, params: { attribute: string; baseline?: string; target?: string; min_n?: number }) {
    const res = await api.get<RunForest>(`/runs/${runId}/forest`, { params });
    return res.data;
}
