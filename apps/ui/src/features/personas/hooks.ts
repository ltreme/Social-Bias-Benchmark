import { useQuery, useInfiniteQuery, keepPreviousData } from '@tanstack/react-query';
import { fetchDatasetPersonas, type PersonaQuery, type PersonaItem } from './api';

type PersonaResponse = { ok: boolean; total: number; items: PersonaItem[] };

export function useDatasetPersonas(datasetId: number, params: PersonaQuery) {
  return useQuery({ queryKey: ['dataset-personas', datasetId, params], queryFn: () => fetchDatasetPersonas(datasetId, params), placeholderData: keepPreviousData });
}

export function useInfiniteDatasetPersonas(
  datasetId: number,
  baseParams: Omit<PersonaQuery, 'limit' | 'offset'>,
  pageSize: number = 50
) {
  return useInfiniteQuery<PersonaResponse, Error>({
    queryKey: ['dataset-personas-infinite', datasetId, baseParams],
    queryFn: ({ pageParam }) => fetchDatasetPersonas(datasetId, { ...baseParams, limit: pageSize, offset: pageParam as number }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      const loadedCount = allPages.reduce((sum, page) => sum + (page.items?.length || 0), 0);
      return loadedCount < lastPage.total ? loadedCount : undefined;
    },
  });
}

