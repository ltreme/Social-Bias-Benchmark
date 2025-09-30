import { api } from '../../lib/apiClient';

export type CaseItem = {
  id: string;
  adjective: string;
  case_template?: string | null;
  linked_results_n: number;
};

export async function fetchCases(): Promise<CaseItem[]> {
  const res = await api.get<CaseItem[]>('/cases');
  return res.data;
}

export async function createCase(body: { adjective: string; case_template?: string | null }): Promise<CaseItem> {
  const res = await api.post<CaseItem>('/cases', body);
  return res.data;
}

export async function updateCase(id: string, body: { adjective: string; case_template?: string | null }): Promise<CaseItem> {
  const res = await api.put<CaseItem>(`/cases/${id}`, body);
  return res.data;
}

export async function deleteCase(id: string): Promise<{ ok: boolean }> {
  const res = await api.delete<{ ok: boolean }>(`/cases/${id}`);
  return res.data;
}

