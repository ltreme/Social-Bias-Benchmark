import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchCases, createCase, updateCase, deleteCase, type CaseItem } from './api';

export function useCases() {
  return useQuery({ queryKey: ['cases'], queryFn: fetchCases });
}

export function useCreateCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { adjective: string; case_template?: string | null }) => createCase(body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['cases'] }); },
  });
}

export function useUpdateCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: { id: string; adjective: string; case_template?: string | null }) => updateCase(p.id, { adjective: p.adjective, case_template: p.case_template }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['cases'] }); },
  });
}

export function useDeleteCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteCase(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['cases'] }); },
  });
}

export type { CaseItem };

