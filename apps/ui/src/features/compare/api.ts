import { api } from '../../lib/apiClient';

export type BenchmarkDistribution = {
    ok: boolean;
    n: number;
    hist: { bins: number[]; shares: number[] };
    per_category: Record<string, Array<{ category: string; count: number; mean: number }>>;
};

export async function fetchMetrics(params: { dataset_ids?: number[]; models?: string[]; case_ids?: string[], rationale?: boolean }) {
    const res = await api.get<BenchmarkDistribution>('/metrics/benchmark-distribution', { params });
    return res.data;
}

export async function fetchModels() {
    const res = await api.get<string[]>('/models');
    return res.data;
}

export type Dataset = {
    id: number;
    name: string;
    kind: string;
    size: number;
    created_at?: string;
    seed?: number;
    config_json?: Record<string, any>;
};

export async function fetchDatasets() {
    const res = await api.get<Dataset[]>('/datasets');
    return res.data;
}