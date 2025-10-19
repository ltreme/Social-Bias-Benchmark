import { api } from '../../lib/apiClient';

export type ModelRow = { id: number; name: string; min_vram?: number | null; vllm_serve_cmd?: string | null; created_at?: string };

export async function fetchModelsAdmin() {
  const res = await api.get<ModelRow[]>('/admin/models');
  return res.data;
}

export async function createModel(body: { name: string; min_vram?: number; vllm_serve_cmd?: string }) {
  const res = await api.post<ModelRow>('/admin/models', body);
  return res.data;
}

export async function updateModel(id: number, body: { name?: string; min_vram?: number; vllm_serve_cmd?: string }) {
  const res = await api.put<ModelRow>(`/admin/models/${id}`, body);
  return res.data;
}

export async function deleteModel(id: number) {
  const res = await api.delete<{ ok: boolean; deleted?: number; error?: string }>(`/admin/models/${id}`);
  return res.data;
}

