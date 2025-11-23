import { api } from '../../lib/apiClient';

export type TaskType = 'benchmark' | 'attrgen' | 'pool_gen' | 'balanced_gen';
export type TaskStatus = 'queued' | 'waiting' | 'running' | 'done' | 'failed' | 'cancelled' | 'skipped';

export type QueueTask = {
  id: number;
  task_type: TaskType;
  status: TaskStatus;
  position: number;
  label: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  depends_on: number | null;
  result_run_id: number | null;
  result_run_type: string | null;
  config: Record<string, any>;
};

export type QueueStats = {
  total: number;
  queued: number;
  waiting: number;
  running: number;
  done: number;
  failed: number;
  cancelled: number;
  skipped: number;
  executor_running: boolean;
  executor_paused: boolean;
};

export type AddTaskPayload = {
  task_type: TaskType;
  config: Record<string, any>;
  label?: string;
  depends_on?: number;
};

export async function addTaskToQueue(payload: AddTaskPayload) {
  const res = await api.post<{ task_id: number }>('/queue/add', payload);
  return res.data;
}

export async function fetchQueueTasks(includeDone = false, limit?: number) {
  const params = new URLSearchParams();
  if (includeDone) params.set('include_done', 'true');
  if (limit) params.set('limit', String(limit));
  
  const res = await api.get<QueueTask[]>(`/queue?${params}`);
  return res.data;
}

export async function fetchQueueTask(taskId: number) {
  const res = await api.get<QueueTask>(`/queue/${taskId}`);
  return res.data;
}

export async function removeTaskFromQueue(taskId: number) {
  const res = await api.delete<{ ok: boolean; message?: string }>(`/queue/${taskId}`);
  return res.data;
}

export async function cancelTask(taskId: number) {
  const res = await api.post<{ ok: boolean; message?: string }>(`/queue/${taskId}/cancel`);
  return res.data;
}

export async function startQueue() {
  const res = await api.post<{ ok: boolean; message?: string }>('/queue/start');
  return res.data;
}

export async function stopQueue() {
  const res = await api.post<{ ok: boolean; message?: string }>('/queue/stop');
  return res.data;
}

export async function pauseQueue() {
  const res = await api.post<{ ok: boolean; message?: string }>('/queue/pause');
  return res.data;
}

export async function resumeQueue() {
  const res = await api.post<{ ok: boolean; message?: string }>('/queue/resume');
  return res.data;
}

export async function fetchQueueStats() {
  const res = await api.get<QueueStats>('/queue/stats');
  return res.data;
}
