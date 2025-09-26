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
    created_at: string;
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
    const res = await api.post<CreateDatasetResponse>('/datasets/generate-pool', body);
    return res.data;
}

export async function buildBalanced(body: { dataset_id: number; n: number; seed?: number; name?: string }) {
    const res = await api.post<CreateDatasetResponse>('/datasets/build-balanced', body);
    return res.data;
}

export async function sampleReality(body: { dataset_id: number; n: number; seed?: number; name?: string }) {
    const res = await api.post<CreateDatasetResponse>('/datasets/sample-reality', body);
    return res.data;
}

export async function buildCounterfactuals(body: { dataset_id: number; seed?: number; name?: string }) {
    const res = await api.post<CreateDatasetResponse>('/datasets/build-counterfactuals', body);
    return res.data;
}
