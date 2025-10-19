import { useQuery } from '@tanstack/react-query';
import { fetchDatasetPersonas, type PersonaQuery } from './api';

export function useDatasetPersonas(datasetId: number, params: PersonaQuery) {
  return useQuery({ queryKey: ['dataset-personas', datasetId, params], queryFn: () => fetchDatasetPersonas(datasetId, params), keepPreviousData: true });
}

