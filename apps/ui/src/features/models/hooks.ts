import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchModelsAdmin, createModel, updateModel, deleteModel } from './api';

export function useModelsAdmin() {
  return useQuery({ queryKey: ['admin-models'], queryFn: fetchModelsAdmin, refetchInterval: 10000 });
}

export function useCreateModel() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: createModel, onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-models'] }) });
}

export function useUpdateModel() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: ({ id, body }: { id: number; body: { name?: string; min_vram?: number; vllm_serve_cmd?: string } }) => updateModel(id, body), onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-models'] }) });
}

export function useDeleteModel() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (id: number) => deleteModel(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-models'] }) });
}

