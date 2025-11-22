import { useQuery, useInfiniteQuery } from '@tanstack/react-query';
import { fetchDatasetPersonas, type PersonaQuery } from './api';

export function useDatasetPersonas(datasetId: number, params: PersonaQuery) {
  return useQuery({ queryKey: ['dataset-personas', datasetId, params], queryFn: () => fetchDatasetPersonas(datasetId, params), keepPreviousData: true });
}

export function useInfiniteDatasetPersonas(
  datasetId: number,
  baseParams: Omit<PersonaQuery, 'limit' | 'offset'>,
  pageSize: number = 50
) {
  return useInfiniteQuery({
    queryKey: ['dataset-personas-infinite', datasetId, baseParams],
    queryFn: ({ pageParam = 0 }) => fetchDatasetPersonas(datasetId, { ...baseParams, limit: pageSize, offset: pageParam }),
    getNextPageParam: (lastPage, allPages) => {
      const loadedCount = allPages.reduce((sum, page) => sum + (page.items?.length || 0), 0);
      return loadedCount < lastPage.total ? loadedCount : undefined;
    },
    keepPreviousData: true,
  });
}

