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