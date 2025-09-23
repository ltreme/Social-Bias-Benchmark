import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchRuns, startRun } from './api';

export function useRuns(status?: string) {
    return useQuery({ queryKey: ['runs', status], queryFn: () => fetchRuns(status ? { status } : undefined), refetchInterval: 5000 });
}

export function useStartRun() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: startRun,
        onSuccess: () => qc.invalidateQueries({ queryKey: ['runs'] }),
    });
}