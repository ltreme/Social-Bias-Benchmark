import { api } from '../../lib/apiClient';

export type Run = {
    id: number;
    model_name: string;
    include_rationale: boolean;
    dataset_id?: number | null;
    created_at: string;
    n_results: number;
};

export type RunDetail = {
    id: number;
    model_name: string;
    include_rationale: boolean;
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
    hist: { bins: number[]; shares: number[]; counts?: number[] };
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

export async function deleteRun(runId: number) {
    const res = await api.delete<{ ok: boolean; deleted?: number; error?: string }>(`/runs/${runId}`);
    return res.data;
}

export type RunMissing = { ok: boolean; dataset_id?: number; total?: number; done?: number; missing?: number; samples?: Array<{ persona_uuid: string; case_id: string; adjective?: string | null }> };
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
  by_case: Array<{ case_id: string; adjective?: string | null; n_pairs: number; exact_rate: number; mae: number }>;
};

export async function fetchRunOrderMetrics(runId: number) {
  const res = await api.get<OrderMetrics>(`/runs/${runId}/order-metrics`);
  return res.data;
}

export type MeansRow = { category: string; count: number; mean: number };
export async function fetchRunMeans(runId: number, attribute: string, top_n?: number) {
  const res = await api.get<{ ok: boolean; rows: MeansRow[] }>(`/runs/${runId}/means`, { params: { attribute, top_n } });
  return res.data;
}
