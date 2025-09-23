import { api } from '../../lib/apiClient';

export type Run = {
    id: string;
    model_name: string;
    dataset_id: string;
    status: 'queued' | 'running' | 'done' | 'failed';
    created_at: string;
};

export async function fetchRuns(params?: { status?: string }) {
    const res = await api.get<Run[]>('/runs', { params });
    return res.data;
}

export async function startRun(body: { model_name: string; dataset_id: string; params?: Record<string, unknown> }) {
    const res = await api.post<Run>('/runs', body);
    return res.data;
}

export async function streamRunStatus(runId: string, onMsg: (s: MessageEvent) => void) {
    const url = `${api.defaults.baseURL}/runs/${runId}/events`;
    const es = new EventSource(url);
    es.onmessage = onMsg;
    return () => es.close();
}