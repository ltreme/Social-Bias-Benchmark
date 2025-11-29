import { api } from '../../lib/apiClient';

export type Run = {
    id: number;
    model_name: string;
    include_rationale: boolean;
    system_prompt?: string | null;
    dataset_id?: number | null;
    created_at: string;
    n_results: number;
};

export type RunDetail = {
    id: number;
    model_name: string;
    include_rationale: boolean;
    system_prompt?: string | null;
    n_results: number;
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
    hist: { bins: string[]; shares: number[]; counts?: number[] };
    trait_categories?: {
        histograms: Array<{ category: string; bins: string[]; counts: number[]; shares: number[] }>;
        summary: Array<{ category: string; count: number; mean: number; std?: number | null }>;
    };
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
    rows: Array<{
        category: string;
        count: number;
        mean: number;
        delta: number;
        p_value: number;
        significant: boolean;
        baseline: string;
        q_value?: number | null;
        cliffs_delta?: number | null;
        // Added spread/CI
        n_base?: number; sd_base?: number | null; mean_base?: number | null;
        n_cat?: number; sd_cat?: number | null; mean_cat?: number | null;
        se_delta?: number | null; ci_low?: number | null; ci_high?: number | null;
    }>;
};

export async function fetchRunDeltas(runId: number, params: { attribute: string; baseline?: string; n_perm?: number; alpha?: number; trait_category?: string }) {
    const query: Record<string, any> = { attribute: params.attribute };
    if (params.baseline) query.baseline = params.baseline;
    if (typeof params.n_perm === 'number') query.n_perm = params.n_perm;
    if (typeof params.alpha === 'number') query.alpha = params.alpha;
    if (params.trait_category) query.trait_category = params.trait_category;
    const res = await api.get<RunDeltas>(`/runs/${runId}/deltas`, { params: query });
    return res.data;
}

export type RunForest = {
    ok: boolean;
    n: number;
    rows: Array<{ case_id: string; label?: string; category: string; trait_category?: string; baseline: string; n_base: number; n_cat: number; delta: number; se: number | null; ci_low: number | null; ci_high: number | null }>;
    overall: { mean: number | null; ci_low: number | null; ci_high: number | null };
};

export async function fetchRunForest(runId: number, params: { attribute: string; baseline?: string; target?: string; min_n?: number; trait_category?: string }) {
    const query: Record<string, any> = { attribute: params.attribute };
    if (params.baseline) query.baseline = params.baseline;
    if (params.target) query.target = params.target;
    if (typeof params.min_n === 'number') query.min_n = params.min_n;
    if (params.trait_category) query.trait_category = params.trait_category;
    const res = await api.get<RunForest>(`/runs/${runId}/forest`, { params: query });
    return res.data;
}

export async function deleteRun(runId: number) {
    const res = await api.delete<{ ok: boolean; deleted?: number; error?: string }>(`/runs/${runId}`);
    return res.data;
}

export type RunMissing = { ok: boolean; dataset_id?: number; total?: number; done?: number; missing?: number; failed?: number; samples?: Array<{ persona_uuid: string; case_id: string; adjective?: string | null }> };
export async function fetchRunMissing(runId: number) {
    const res = await api.get<RunMissing>(`/runs/${runId}/missing`);
    return res.data;
}

export type OrderMetrics = {
    ok: boolean;
    n_pairs: number;
    rma: { exact_rate?: number; mae?: number; cliffs_delta?: number };
    obe: { mean_diff?: number; ci_low?: number; ci_high?: number; sd?: number };
    usage: { eei?: number; mni?: number; sv?: number };
    test_retest: { within1_rate?: number; mean_abs_diff?: number };
    correlation: { pearson?: number; spearman?: number; kendall?: number };
    by_case: Array<{ case_id: string; adjective?: string | null; trait_category?: string | null; n_pairs: number; exact_rate: number; mae: number }>;
    by_trait_category?: Array<{ trait_category: string; n_pairs: number; exact_rate?: number; mae?: number }>;
};

export async function fetchRunOrderMetrics(runId: number) {
    const res = await api.get<OrderMetrics>(`/runs/${runId}/order-metrics`);
    return res.data;
}

export type MeansRow = { category: string; count: number; mean: number };
export async function fetchRunMeans(runId: number, attribute: string, top_n?: number, trait_category?: string) {
    const params: Record<string, any> = { attribute };
    if (typeof top_n === 'number') params.top_n = top_n;
    if (trait_category) params.trait_category = trait_category;
    const res = await api.get<{ ok: boolean; rows: MeansRow[] }>(`/runs/${runId}/means`, { params });
    return res.data;
}

export async function fetchRunAllMeans(runId: number) {
    const res = await api.get<{ ok: boolean; data: Record<string, MeansRow[]> }>(`/runs/${runId}/means/all`);
    return res.data;
}

export async function fetchRunAllDeltas(runId: number) {
    const res = await api.get<{ ok: boolean; data: Record<string, RunDeltas> }>(`/runs/${runId}/deltas/all`);
    return res.data;
}

export type WarmCacheStep = {
    name: string;
    status: 'running' | 'done' | 'error';
    ok?: boolean | null;
    duration_ms?: number | null;
    started_at?: string | null;
    finished_at?: string | null;
    error?: string | null;
};
export type RunWarmupStatus = {
    ok: boolean;
    run_id?: number;
    status: 'idle' | 'running' | 'done' | 'done_with_errors' | 'error';
    started_at?: string | null;
    updated_at?: string | null;
    finished_at?: string | null;
    duration_ms?: number | null;
    current_step?: string | null;
    steps: WarmCacheStep[];
    had_errors?: boolean;
    error?: string | null;
};
export async function startRunWarmup(runId: number) {
    const res = await api.post<RunWarmupStatus>(`/runs/${runId}/warm-cache`);
    return res.data;
}
export async function fetchRunWarmupStatus(runId: number) {
    const res = await api.get<RunWarmupStatus>(`/runs/${runId}/warm-cache`);
    return res.data;
}

// ============================================================================
// Analysis API (Queue-based)
// ============================================================================

export type AnalysisStatus = {
    run_id: number;
    analyses: Record<string, {
        status: 'pending' | 'running' | 'completed' | 'failed';
        created_at: string | null;
        completed_at: string | null;
        duration_ms: number | null;
        error: string | null;
        summary: Record<string, any> | null;
    }>;
};

export type QuickAnalysis = {
    run_id: number;
    total_results: number;
    total_rated: number;
    error_count: number;
    error_rate: number;
    rating_distribution: Record<string, number>;
    order_consistency_sample: {
        n_pairs: number;
        rma: number | null;
        mae: number | null;
        is_sample: boolean;
    };
    computed_at: string;
};

export type AnalyzeRequest = {
    type: 'order' | 'bias' | 'export';
    attribute?: string;  // required for bias
    format?: string;     // for export
    force?: boolean;     // force re-run even if completed
};

export type AnalyzeResponse = {
    job_id: number;
    task_id?: number;
    status: 'pending' | 'running' | 'completed';
    message: string;
};

export async function fetchAnalysisStatus(runId: number) {
    const res = await api.get<AnalysisStatus>(`/runs/${runId}/analysis`);
    return res.data;
}

export async function fetchQuickAnalysis(runId: number) {
    const res = await api.get<QuickAnalysis>(`/runs/${runId}/analysis/quick`);
    return res.data;
}

export async function requestAnalysis(runId: number, request: AnalyzeRequest) {
    const res = await api.post<AnalyzeResponse>(`/runs/${runId}/analyze`, request);
    return res.data;
}
