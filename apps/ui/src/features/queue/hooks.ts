import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { notifications } from '@mantine/notifications';
import * as queueApi from './api';

const QUEUE_QUERY_KEY = ['queue'];
const QUEUE_STATS_KEY = ['queue', 'stats'];

export function useQueueTasks(includeDone = false, limit?: number) {
  return useQuery({
    queryKey: [...QUEUE_QUERY_KEY, 'list', includeDone, limit],
    queryFn: () => queueApi.fetchQueueTasks(includeDone, limit),
    refetchInterval: 3000, // Poll every 3 seconds
  });
}

export function useQueueTask(taskId: number) {
  return useQuery({
    queryKey: [...QUEUE_QUERY_KEY, 'task', taskId],
    queryFn: () => queueApi.fetchQueueTask(taskId),
    enabled: !!taskId,
  });
}

export function useQueueStats() {
  return useQuery({
    queryKey: QUEUE_STATS_KEY,
    queryFn: queueApi.fetchQueueStats,
    refetchInterval: 2000, // Poll every 2 seconds
  });
}

export function useAddTask() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: queueApi.addTaskToQueue,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUEUE_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: QUEUE_STATS_KEY });
      notifications.show({
        color: 'green',
        title: 'Task zur Queue hinzugefügt',
        message: 'Der Task wurde erfolgreich zur Queue hinzugefügt',
      });
    },
    onError: (error: any) => {
      notifications.show({
        color: 'red',
        title: 'Fehler',
        message: error.response?.data?.detail || 'Task konnte nicht hinzugefügt werden',
      });
    },
  });
}

export function useRemoveTask() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: queueApi.removeTaskFromQueue,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUEUE_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: QUEUE_STATS_KEY });
      notifications.show({
        color: 'green',
        title: 'Task entfernt',
        message: 'Der Task wurde aus der Queue entfernt',
      });
    },
    onError: (error: any) => {
      notifications.show({
        color: 'red',
        title: 'Fehler',
        message: error.response?.data?.detail || 'Task konnte nicht entfernt werden',
      });
    },
  });
}

export function useCancelTask() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: queueApi.cancelTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUEUE_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: QUEUE_STATS_KEY });
      notifications.show({
        color: 'orange',
        title: 'Task abgebrochen',
        message: 'Der Task wurde abgebrochen',
      });
    },
    onError: (error: any) => {
      notifications.show({
        color: 'red',
        title: 'Fehler',
        message: error.response?.data?.detail || 'Task konnte nicht abgebrochen werden',
      });
    },
  });
}

export function useStartQueue() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: queueApi.startQueue,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUEUE_STATS_KEY });
      notifications.show({
        color: 'green',
        title: 'Queue gestartet',
        message: 'Die Queue-Verarbeitung wurde gestartet',
      });
    },
    onError: (error: any) => {
      notifications.show({
        color: 'red',
        title: 'Fehler',
        message: error.response?.data?.detail || 'Queue konnte nicht gestartet werden',
      });
    },
  });
}

export function usePauseQueue() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: queueApi.pauseQueue,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUEUE_STATS_KEY });
      notifications.show({
        color: 'orange',
        title: 'Queue pausiert',
        message: 'Die Queue-Verarbeitung wurde pausiert',
      });
    },
    onError: (error: any) => {
      notifications.show({
        color: 'red',
        title: 'Fehler',
        message: error.response?.data?.detail || 'Queue konnte nicht pausiert werden',
      });
    },
  });
}

export function useResumeQueue() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: queueApi.resumeQueue,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUEUE_STATS_KEY });
      notifications.show({
        color: 'green',
        title: 'Queue fortgesetzt',
        message: 'Die Queue-Verarbeitung wurde fortgesetzt',
      });
    },
    onError: (error: any) => {
      notifications.show({
        color: 'red',
        title: 'Fehler',
        message: error.response?.data?.detail || 'Queue konnte nicht fortgesetzt werden',
      });
    },
  });
}

export function useStopQueue() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: queueApi.stopQueue,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUEUE_STATS_KEY });
      notifications.show({
        color: 'red',
        title: 'Queue gestoppt',
        message: 'Die Queue-Verarbeitung wurde gestoppt',
      });
    },
    onError: (error: any) => {
      notifications.show({
        color: 'red',
        title: 'Fehler',
        message: error.response?.data?.detail || 'Queue konnte nicht gestoppt werden',
      });
    },
  });
}
