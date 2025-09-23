import { z } from 'zod';

export const DatasetSchema = z.object({ id: z.string(), name: z.string(), size: z.number(), created_at: z.string() });
export type Dataset = z.infer<typeof DatasetSchema>;

export const RunSchema = z.object({
    id: z.string(),
    model_name: z.string(),
    dataset_id: z.string(),
    status: z.enum(['queued', 'running', 'done', 'failed']),
    created_at: z.string(),
});
export type Run = z.infer<typeof RunSchema>;