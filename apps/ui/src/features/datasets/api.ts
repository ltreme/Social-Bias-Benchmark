import { api } from '../../lib/apiClient';

export type Dataset = {
    id: string;
    name: string;
    size: number;
    created_at: string;
};

export async function fetchDatasets(params?: { q?: string }) {
    const res = await api.get<Dataset[]>('/datasets', { params });
    return res.data;
}