import { ActionIcon, Badge, Button, Card, Group, Menu, Progress, Stack, Text, Title, Tooltip } from '@mantine/core';
import { IconPlayerPause, IconPlayerPlay, IconPlayerStop, IconTrash, IconX, IconRefresh, IconRefreshAlert, IconUsers, IconChartBar, IconDatabase } from '@tabler/icons-react';
import { Link } from '@tanstack/react-router';
import { useCancelTask, usePauseQueue, useQueueStats, useQueueTasks, useRemoveTask, useResumeQueue, useRetryTask, useStartQueue, useStopQueue } from './hooks';
import type { QueueTask, TaskStatus } from './api';

function getStatusColor(status: TaskStatus): string {
  switch (status) {
    case 'queued': return 'blue';
    case 'waiting': return 'yellow';
    case 'running': return 'green';
    case 'done': return 'teal';
    case 'failed': return 'red';
    case 'cancelled': return 'gray';
    case 'skipped': return 'orange';
    default: return 'gray';
  }
}

function getStatusLabel(status: TaskStatus): string {
  switch (status) {
    case 'queued': return 'In Queue';
    case 'waiting': return 'Wartet';
    case 'running': return 'Läuft';
    case 'done': return 'Fertig';
    case 'failed': return 'Fehler';
    case 'cancelled': return 'Abgebrochen';
    case 'skipped': return 'Übersprungen';
    default: return status;
  }
}

function formatDuration(startedAt: string | null, finishedAt: string | null): string {
  if (!startedAt || !finishedAt) return '-';
  
  const start = new Date(startedAt).getTime();
  const end = new Date(finishedAt).getTime();
  const diffMs = end - start;
  
  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return `${seconds}s`;
  
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remainingSeconds}s`;
  
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}

function formatSmartDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  
  const dateDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  
  const timeStr = date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  
  if (dateDay.getTime() === today.getTime()) {
    return `Heute ${timeStr} Uhr`;
  } else if (dateDay.getTime() === yesterday.getTime()) {
    return `Gestern ${timeStr} Uhr`;
  } else {
    const day = date.getDate().toString().padStart(2, '0');
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const year = date.getFullYear();
    return `${day}.${month}.${year} ${timeStr}`;
  }
}

function getTaskIcon(type: string) {
  switch (type) {
    case 'attrgen': return <IconUsers size={14} />;
    case 'benchmark': return <IconChartBar size={14} />;
    case 'pool_gen': return <IconDatabase size={14} />;
    case 'balanced_gen': return <IconUsers size={14} />;
    default: return null;
  }
}

function getTaskColor(type: string) {
  switch (type) {
    case 'attrgen': return 'violet';
    case 'benchmark': return 'cyan';
    case 'pool_gen': return 'indigo';
    case 'balanced_gen': return 'grape';
    default: return 'gray';
  }
}

function TaskCard({ task }: { task: QueueTask }) {
  const removeTask = useRemoveTask();
  const cancelTask = useCancelTask();
  const retryTask = useRetryTask();
  
  const taskColor = getTaskColor(task.task_type);
  
  const canRemove = task.status === 'queued' || task.status === 'waiting';
  const canCancel = task.status === 'queued' || task.status === 'waiting' || task.status === 'running';
  const canRetry = task.status === 'failed' || task.status === 'cancelled';
  
  return (
    <Card withBorder padding="md" style={{ position: 'relative', borderLeft: `4px solid var(--mantine-color-${taskColor}-6)` }}>
      <Group justify="space-between" mb="xs">
        <Group gap="sm">
          <Badge color={getStatusColor(task.status)} variant="filled">
            {getStatusLabel(task.status)}
          </Badge>
          <Text size="sm" c="dimmed">#{task.id}</Text>
        </Group>
        
        <Group gap="xs">
          {canRetry && (
            <Menu withinPortal position="bottom-end">
              <Menu.Target>
                <Tooltip label="Task wiederholen">
                  <ActionIcon
                    color="blue"
                    variant="subtle"
                    loading={retryTask.isPending}
                  >
                    <IconRefresh size={18} />
                  </ActionIcon>
                </Tooltip>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Label>Wiederholungsmodus</Menu.Label>
                <Menu.Item
                  leftSection={<IconRefresh size={16} />}
                  onClick={() => retryTask.mutate({ taskId: task.id, deleteResults: false })}
                >
                  Fortsetzen (vorhandene Ergebnisse behalten)
                </Menu.Item>
                <Menu.Item
                  leftSection={<IconRefreshAlert size={16} />}
                  color="orange"
                  onClick={() => retryTask.mutate({ taskId: task.id, deleteResults: true })}
                >
                  Neu starten (Ergebnisse löschen)
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          )}
          {canCancel && (
            <Tooltip label="Task abbrechen">
              <ActionIcon
                color="orange"
                variant="subtle"
                onClick={() => cancelTask.mutate(task.id)}
                loading={cancelTask.isPending}
              >
                <IconX size={18} />
              </ActionIcon>
            </Tooltip>
          )}
          {canRemove && (
            <Tooltip label="Task entfernen">
              <ActionIcon
                color="red"
                variant="subtle"
                onClick={() => removeTask.mutate(task.id)}
                loading={removeTask.isPending}
              >
                <IconTrash size={18} />
              </ActionIcon>
            </Tooltip>
          )}
        </Group>
      </Group>
      
      <Stack gap="xs">
        <Group gap="sm">
          <Badge color={taskColor} variant="light" size="sm" leftSection={getTaskIcon(task.task_type)}>
            {task.task_type}
          </Badge>
          <Text size="sm" fw={500}>{task.label || `Task #${task.id}`}</Text>
        </Group>
        
        {task.depends_on && (
          <Text size="xs" c="dimmed">
            🔗 Abhängig von Task #{task.depends_on}
          </Text>
        )}
        
        {task.status === 'running' && task.progress && (
          <Stack gap={4}>
            <Group justify="space-between">
              <Text size="xs" c="dimmed">
                Fortschritt: {task.progress.done.toLocaleString()} / {task.progress.total.toLocaleString()}
              </Text>
              <Text size="xs" fw={500}>
                {task.progress.percent}%
              </Text>
            </Group>
            <Progress value={task.progress.percent} size="sm" animated />
          </Stack>
        )}
        
        {task.status === 'running' && !task.progress && (
          <Progress value={100} size="sm" animated striped />
        )}
        
        {task.error && (
          <Text size="xs" c="red" style={{ fontFamily: 'monospace' }}>
            {task.error.length > 100 ? task.error.substring(0, 100) + '...' : task.error}
          </Text>
        )}
        
        {task.status === 'done' && task.result_run_id && (
          <Group gap="xs">
            <Text size="xs" c="dimmed">Ergebnis:</Text>
            {task.result_run_type === 'benchmark' ? (
              <Link to="/runs/$runId" params={{ runId: String(task.result_run_id) }}>
                <Text size="xs" c="blue" td="underline">
                  Benchmark Run #{task.result_run_id}
                </Text>
              </Link>
            ) : (
              <Text size="xs">
                {task.result_run_type?.toUpperCase()} Run #{task.result_run_id}
              </Text>
            )}
          </Group>
        )}
        
        <Group gap="md">
          {task.started_at && (
            <Text size="xs" c="dimmed">
              Gestartet: {formatSmartDate(task.started_at)}
            </Text>
          )}
          {task.finished_at && (
            <Text size="xs" c="dimmed">
              Dauer: {formatDuration(task.started_at, task.finished_at)}
            </Text>
          )}
        </Group>
      </Stack>
    </Card>
  );
}

export function QueuePage() {
  const { data: tasks = [], isLoading } = useQueueTasks(true, 50);
  const { data: stats } = useQueueStats();
  
  const startQueue = useStartQueue();
  const pauseQueue = usePauseQueue();
  const resumeQueue = useResumeQueue();
  const stopQueue = useStopQueue();
  
  const activeTasks = tasks.filter(t => !['done', 'failed', 'cancelled', 'skipped'].includes(t.status));
  const completedTasks = tasks.filter(t => ['done', 'failed', 'cancelled', 'skipped'].includes(t.status));
  
  return (
    <Stack gap="md">
      <Card>
        <Group justify="space-between" mb="md">
          <Title order={2}>Task Queue</Title>
          
          <Group gap="sm">
            {stats?.executor_running ? (
              <>
                {stats.executor_paused ? (
                  <Button
                    leftSection={<IconPlayerPlay size={16} />}
                    onClick={() => resumeQueue.mutate()}
                    loading={resumeQueue.isPending}
                    color="green"
                  >
                    Fortsetzen
                  </Button>
                ) : (
                  <Button
                    leftSection={<IconPlayerPause size={16} />}
                    onClick={() => pauseQueue.mutate()}
                    loading={pauseQueue.isPending}
                    color="orange"
                  >
                    Pausieren
                  </Button>
                )}
                <Button
                  leftSection={<IconPlayerStop size={16} />}
                  onClick={() => stopQueue.mutate()}
                  loading={stopQueue.isPending}
                  color="red"
                  variant="light"
                >
                  Stoppen
                </Button>
              </>
            ) : (
              <Button
                leftSection={<IconPlayerPlay size={16} />}
                onClick={() => startQueue.mutate()}
                loading={startQueue.isPending}
                color="green"
              >
                Queue starten
              </Button>
            )}
          </Group>
        </Group>
        
        {stats && (
          <Group gap="md">
            <Badge color="blue" variant="light">Queued: {stats.queued}</Badge>
            <Badge color="yellow" variant="light">Waiting: {stats.waiting}</Badge>
            <Badge color="green" variant="light">Running: {stats.running}</Badge>
            <Badge color="teal" variant="light">Done: {stats.done}</Badge>
            <Badge color="red" variant="light">Failed: {stats.failed}</Badge>
            <Badge color="gray" variant="light">Cancelled: {stats.cancelled}</Badge>
            <Badge color="gray" variant="light">Total: {stats.total}</Badge>
          </Group>
        )}
      </Card>
      
      {isLoading ? (
        <Card withBorder padding="lg">
          <Text c="dimmed">Lade Tasks...</Text>
        </Card>
      ) : (
        <>
          {activeTasks.length > 0 && (
            <div>
              <Title order={3} mb="sm">Aktive Tasks</Title>
              <Stack gap="sm">
                {activeTasks.map(task => (
                  <TaskCard key={task.id} task={task} />
                ))}
              </Stack>
            </div>
          )}
          
          {completedTasks.length > 0 && (
            <div>
              <Title order={3} mb="sm">Abgeschlossene Tasks</Title>
              <Stack gap="sm">
                {completedTasks.map(task => (
                  <TaskCard key={task.id} task={task} />
                ))}
              </Stack>
            </div>
          )}
          
          {tasks.length === 0 && (
            <Card withBorder padding="lg">
              <Text c="dimmed" ta="center">
                Keine Tasks in der Queue. Füge Tasks über die Benchmark- oder AttrGen-Modals hinzu.
              </Text>
            </Card>
          )}
        </>
      )}
    </Stack>
  );
}
