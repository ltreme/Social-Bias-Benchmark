import { api } from '../../lib/apiClient';

export type PersonaItem = {
  uuid: string;
  created_at?: string | null;
  age?: number | null;
  gender?: string | null;
  education?: string | null;
  occupation?: string | null;
  marriage_status?: string | null;
  migration_status?: string | null;
  religion?: string | null;
  sexuality?: string | null;
  origin_country?: string | null;
  origin_region?: string | null;
  origin_subregion?: string | null;
  additional_attributes?: Record<string, string> | null;
};

export type PersonaQuery = {
  limit?: number; offset?: number; sort?: string; order?: 'asc'|'desc';
  gender?: string; religion?: string; sexuality?: string; education?: string;
  marriage_status?: string; migration_status?: string; origin_subregion?: string;
  min_age?: number; max_age?: number;
};

export async function fetchDatasetPersonas(datasetId: number, params: PersonaQuery) {
  const res = await api.get<{ ok: boolean; total: number; items: PersonaItem[] }>(`/datasets/${datasetId}/personas`, { params });
  return res.data;
}

