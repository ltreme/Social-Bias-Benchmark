import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchTraits, createTrait, updateTrait, deleteTrait, fetchTraitCategories, setTraitActive, exportTraitsCsv, exportFilteredTraitsCsv, importTraitsCsv, type TraitItem, type TraitPayload, type TraitImportResult } from './api';

export function useTraits() {
  return useQuery({ queryKey: ['traits'], queryFn: fetchTraits });
}

export function useCreateTrait() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TraitPayload) => createTrait(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['traits'] });
      qc.invalidateQueries({ queryKey: ['trait-categories'] });
    },
  });
}

export function useUpdateTrait() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: { id: string } & TraitPayload) => updateTrait(p.id, {
      adjective: p.adjective,
      case_template: p.case_template,
      category: p.category,
      valence: p.valence,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['traits'] });
      qc.invalidateQueries({ queryKey: ['trait-categories'] });
    },
  });
}

export function useDeleteTrait() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteTrait(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['traits'] });
      qc.invalidateQueries({ queryKey: ['trait-categories'] });
    },
  });
}

export type { TraitItem };

export function useTraitCategories() {
  return useQuery({ queryKey: ['trait-categories'], queryFn: fetchTraitCategories });
}

export function useToggleTraitActive() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { id: string; is_active: boolean }) => setTraitActive(vars.id, vars.is_active),
    onMutate: async (vars) => {
      await qc.cancelQueries({ queryKey: ['traits'] });
      const previous = qc.getQueryData<TraitItem[]>(['traits']);
      if (previous) {
        qc.setQueryData<TraitItem[]>(['traits'], previous.map((item) => (
          item.id === vars.id ? { ...item, is_active: vars.is_active } : item
        )));
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        qc.setQueryData(['traits'], context.previous);
      }
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['traits'] });
    },
  });
}

export function useImportTraitsCsv() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => importTraitsCsv(file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['traits'] });
      qc.invalidateQueries({ queryKey: ['trait-categories'] });
    },
  });
}

export async function triggerTraitsExport(): Promise<void> {
  const response = await exportTraitsCsv();
  const blob = response.blob;
  const filename = response.filename || 'traits.csv';
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function triggerFilteredTraitsExport(traitIds: string[]): Promise<void> {
  const response = await exportFilteredTraitsCsv(traitIds);
  const blob = response.blob;
  const filename = response.filename || 'traits_filtered.csv';
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export type { TraitImportResult };
