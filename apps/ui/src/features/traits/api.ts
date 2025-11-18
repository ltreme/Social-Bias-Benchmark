import { api } from '../../lib/apiClient';

export type TraitItem = {
  id: string;
  adjective: string;
  case_template?: string | null;
  category?: string | null;
  valence?: -1 | 0 | 1 | null;
  is_active: boolean;
  linked_results_n: number;
};

export type TraitPayload = {
  adjective: string;
  case_template?: string | null;
  category?: string | null;
  valence?: -1 | 0 | 1 | null;
};

export async function fetchTraits(): Promise<TraitItem[]> {
  const res = await api.get<TraitItem[]>('/traits');
  return res.data;
}

export async function createTrait(body: TraitPayload): Promise<TraitItem> {
  const res = await api.post<TraitItem>('/traits', body);
  return res.data;
}

export async function updateTrait(id: string, body: TraitPayload): Promise<TraitItem> {
  const res = await api.put<TraitItem>(`/traits/${id}`, body);
  return res.data;
}

export async function deleteTrait(id: string): Promise<{ ok: boolean }> {
  const res = await api.delete<{ ok: boolean }>(`/traits/${id}`);
  return res.data;
}

export async function fetchTraitCategories(): Promise<string[]> {
  const res = await api.get<{ categories: string[] }>('/traits/categories');
  return res.data.categories ?? [];
}

export async function setTraitActive(id: string, is_active: boolean): Promise<TraitItem> {
  const res = await api.post<TraitItem>(`/traits/${id}/active`, { is_active });
  return res.data;
}

export async function exportTraitsCsv(): Promise<Blob> {
  const res = await api.get<Blob>('/traits/export', { responseType: 'blob' });
  return res.data;
}

export type TraitImportResult = { ok: boolean; inserted: number; updated: number; skipped: number; errors: string[] };

export async function importTraitsCsv(file: File): Promise<TraitImportResult> {
  const form = new FormData();
  form.append('file', file);
  const res = await api.post<TraitImportResult>('/traits/import', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}
