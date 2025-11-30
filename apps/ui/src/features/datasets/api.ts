import { api } from '../../lib/apiClient';

export type Dataset = {
    id: number;
    name: string;
    kind: string;
    size: number;
    created_at?: string;
    seed?: number;
    config_json?: Record<string, any>;
    enriched_percentage?: number;
};

export type Run = {
    id: number;
    model_name: string;
    include_rationale: boolean;
    system_prompt?: string | null;
    created_at: string;
    status?: string;
    done?: number;
    total?: number;
    pct?: number;
}

export async function fetchDatasets(params?: { q?: string }) {
    const res = await api.get<Dataset[]>('/datasets', { params });
    return res.data;
}

export type DistributionItem = { value: string; count: number; share: number };

export type DatasetComposition = {
    ok: boolean;
    n: number;
    attributes: Record<string, DistributionItem[]>;
    age: { bins: string[]; male: number[]; female: number[]; other: number[] };
};

export async function fetchDatasetComposition(datasetId: number) {
    const res = await api.get<DatasetComposition>(`/datasets/${datasetId}/composition`);
    return res.data;
}

export async function fetchDataset(datasetId: number) {
    const res = await api.get<Dataset>(`/datasets/${datasetId}`);
    return res.data;
}

export async function fetchRunsByDataset(datasetId: number) {
    const res = await api.get<Run[]>(`/datasets/${datasetId}/runs`);
    return res.data;
}

export type CreateDatasetResponse = { id: number; name: string };

export async function createPool(body: { n: number; temperature: number; age_from: number; age_to: number; name?: string }) {
    const res = await api.post<{ ok: boolean; job_id: number }>('/datasets/pool/start', body);
    return res.data as any;
}
export type PoolStatus = { ok: boolean; status: string; done?: number; total?: number; pct?: number; eta_sec?: number; phase?: string; dataset_id?: number; error?: string };
export async function fetchPoolStatus(jobId: number) {
    const res = await api.get<PoolStatus>(`/datasets/pool/${jobId}/status`);
    return res.data;
}

export async function buildBalanced(body: { dataset_id: number; n: number; seed?: number; name?: string }) {
    const res = await api.post<{ ok: boolean; job_id: number }>('/datasets/balanced/start', body);
    return res.data as any;
}

export async function sampleReality(body: { dataset_id: number; n: number; seed?: number; name?: string }) {
    const res = await api.post<CreateDatasetResponse>('/datasets/sample-reality', body);
    return res.data;
}

export async function buildCounterfactuals(body: { dataset_id: number; seed?: number; name?: string }) {
    const res = await api.post<CreateDatasetResponse>('/datasets/build-counterfactuals', body);
    return res.data;
}

export async function deleteDataset(datasetId: number) {
    const res = await api.post<{ ok: boolean; job_id: number }>(`/datasets/${datasetId}/delete/start`);
    return res.data as any;
}

export type BalancedStatus = { ok: boolean; status: string; done?: number; total?: number; pct?: number; eta_sec?: number; dataset_id?: number; error?: string };
export async function fetchBalancedStatus(jobId: number) {
    const res = await api.get<BalancedStatus>(`/datasets/balanced/${jobId}/status`);
    return res.data;
}
export type DeleteStatus = { ok: boolean; status: string; done?: number; pct?: number; error?: string };
export async function fetchDeleteStatus(jobId: number) {
    const res = await api.get<DeleteStatus>(`/datasets/delete/${jobId}/status`);
    return res.data;
}

export type AttrgenStartResponse = { ok: boolean; run_id: number };
export type AttrgenStatus = { ok: boolean; status: string; total?: number; done?: number; pct?: number; error?: string };

export async function startAttrGen(body: { dataset_id: number; model_name: string; llm?: 'hf'|'vllm'|'fake'; batch_size?: number; max_new_tokens?: number; max_attempts?: number; system_prompt?: string; vllm_base_url?: string }) {
    const res = await api.post<AttrgenStartResponse>('/attrgen/start', body);
    return res.data;
}

export async function fetchAttrgenStatus(runId: number) {
    const res = await api.get<AttrgenStatus>(`/attrgen/${runId}/status`);
    return res.data;
}

export async function fetchLatestAttrgen(datasetId: number) {
    const res = await api.get<{ ok: boolean; found: boolean; run_id?: number; status?: string; total?: number; done?: number; pct?: number; error?: string }>(`/datasets/${datasetId}/attrgen/latest`);
    return res.data;
}

export type AttrgenRun = { id: number; created_at: string; model_name?: string | null; status?: string; done?: number; total?: number; pct?: number; error?: string };
export async function fetchAttrgenRuns(datasetId: number) {
    const res = await api.get<{ ok: boolean; runs: AttrgenRun[] }>(`/datasets/${datasetId}/attrgen/runs`);
    return res.data;
}

export async function deleteAttrgenRun(runId: number) {
    const res = await api.delete<{ ok: boolean; deleted_attributes?: number }>(`/attrgen/${runId}`);
    return res.data;
}

export type BenchStartResponse = { ok: boolean; run_id: number };
export type BenchStatus = { ok: boolean; status: string; done?: number; total?: number; pct?: number; error?: string };
export async function startBenchmark(body: { dataset_id: number; model_name?: string; include_rationale?: boolean; llm?: 'vllm'|'hf'|'fake'; batch_size?: number; vllm_base_url?: string; vllm_api_key?: string; max_new_tokens?: number; max_attempts?: number; system_prompt?: string; resume_run_id?: number; scale_mode?: 'in'|'rev'|'random50'; dual_fraction?: number; attrgen_run_id?: number }) {
    const res = await api.post<BenchStartResponse>('/benchmarks/start', body);
    return res.data;
}
export async function fetchBenchmarkStatus(runId: number) {
    const res = await api.get<BenchStatus>(`/benchmarks/${runId}/status`);
    return res.data;
}

export type ActiveBenchmark = { ok: boolean; active: boolean; run_id?: number; status?: string; done?: number; total?: number; pct?: number; error?: string };
export async function fetchActiveBenchmark(datasetId: number) {
    const res = await api.get<ActiveBenchmark>(`/datasets/${datasetId}/benchmarks/active`);
    return res.data;
}

export async function cancelBenchmark(runId: number) {
    const res = await api.post<{ ok: boolean }>(`/benchmarks/${runId}/cancel`, {});
    return res.data;
}
