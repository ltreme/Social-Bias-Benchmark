import { useQuery } from '@tanstack/react-query';
import { fetchDatasets } from './api';

export function useDatasets(q?: string) {
    return useQuery({ queryKey: ['datasets', q], queryFn: () => fetchDatasets(q ? { q } : undefined) });
}