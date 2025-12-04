import { ActionIcon, Badge, Button, Card, Group, Menu, Progress, RingProgress, Stack, Text, Title, Tooltip, useComputedColorScheme } from '@mantine/core';
import { IconPlayerPause, IconPlayerPlay, IconPlayerStop, IconTrash, IconX, IconRefresh, IconRefreshAlert, IconUsers, IconChartBar, IconDatabase, IconListCheck, IconClock, IconCheck, IconAlertTriangle, IconBan, IconHourglass, IconRocket } from '@tabler/icons-react';
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

function getStatusIcon(status: TaskStatus) {
  switch (status) {
    case 'queued': return <IconHourglass size={14} />;
    case 'waiting': return <IconClock size={14} />;
    case 'running': return <IconRocket size={14} />;
    case 'done': return <IconCheck size={14} />;
    case 'failed': return <IconAlertTriangle size={14} />;
    case 'cancelled': return <IconBan size={14} />;
    case 'skipped': return <IconBan size={14} />;
    default: return null;
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
  const colorScheme = useComputedColorScheme('light');
  const isDark = colorScheme === 'dark';
  
  const taskColor = getTaskColor(task.task_type);
  const statusColor = getStatusColor(task.status);
  
  const canRemove = task.status === 'queued' || task.status === 'waiting';
  const canCancel = task.status === 'queued' || task.status === 'waiting' || task.status === 'running';
  const canRetry = task.status === 'failed' || task.status === 'cancelled';
  
  // Background colors based on status
  const getCardBackground = () => {
    if (task.status === 'running') {
      return isDark ? 'rgba(34, 197, 94, 0.08)' : 'rgba(34, 197, 94, 0.04)';
    }
    if (task.status === 'failed') {
      return isDark ? 'rgba(239, 68, 68, 0.08)' : 'rgba(239, 68, 68, 0.04)';
    }
    return undefined;
  };
  
  return (
    <Card 
      withBorder 
      padding="md" 
      style={{ 
        position: 'relative', 
        borderLeft: `4px solid var(--mantine-color-${statusColor}-6)`,
        background: getCardBackground(),
      }}
    >
      {/* Main row with grid layout */}
      <Group justify="space-between" wrap="nowrap" gap="xl">
        {/* Left section: Status + ID + Type */}
        <Group gap="md" wrap="nowrap" style={{ minWidth: 200 }}>
          <Badge 
            color={statusColor} 
            variant="filled" 
            size="sm"
            leftSection={getStatusIcon(task.status)}
          >
            {getStatusLabel(task.status)}
          </Badge>
          <Text size="sm" c="dimmed" fw={500}>#{task.id}</Text>
          <Badge color={taskColor} variant="light" size="sm" leftSection={getTaskIcon(task.task_type)}>
            {task.task_type.toUpperCase()}
          </Badge>
        </Group>
        
        {/* Center section: Task label/description - takes up remaining space */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <Text size="sm" fw={600} truncate>
            {task.label || `Task #${task.id}`}
          </Text>
          {task.depends_on && (
            <Text size="xs" c="dimmed">
              🔗 Abhängig von Task #{task.depends_on}
            </Text>
          )}
        </div>
        
        {/* Right section: Result link (for completed tasks) */}
        <div style={{ minWidth: 180, textAlign: 'center' }}>
          {task.status === 'done' && task.result_run_id ? (
            task.result_run_type === 'benchmark' ? (
              <Link to="/runs/$runId" params={{ runId: String(task.result_run_id) }}>
                <Badge variant="light" color="blue" size="sm" style={{ cursor: 'pointer' }}>
                  → Run #{task.result_run_id}
                </Badge>
              </Link>
            ) : (
              <Badge variant="light" color="gray" size="sm">
                {task.result_run_type?.toUpperCase()} #{task.result_run_id}
              </Badge>
            )
          ) : task.error ? (
            <Tooltip label={task.error} multiline w={300}>
              <Badge variant="light" color="red" size="sm" style={{ cursor: 'help' }}>
                Fehler
              </Badge>
            </Tooltip>
          ) : null}
        </div>
        
        {/* Time section */}
        <Stack gap={2} style={{ minWidth: 140 }} align="flex-end">
          {task.started_at && (
            <Text size="xs" c="dimmed">
              {formatSmartDate(task.started_at)}
            </Text>
          )}
          {task.finished_at && (
            <Group gap={4}>
              <IconClock size={12} color={isDark ? '#909296' : '#868e96'} />
              <Text size="xs" c="dimmed">
                {formatDuration(task.started_at, task.finished_at)}
              </Text>
            </Group>
          )}
        </Stack>
        
        {/* Actions section */}
        <Group gap="xs" wrap="nowrap" style={{ minWidth: 90 }} justify="flex-end">
          {canRetry && (
            <Menu withinPortal position="bottom-end">
              <Menu.Target>
                <Tooltip label="Task wiederholen">
                  <ActionIcon
                    color="blue"
                    variant="light"
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
                variant="light"
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
                variant="light"
                onClick={() => removeTask.mutate(task.id)}
                loading={removeTask.isPending}
              >
                <IconTrash size={18} />
              </ActionIcon>
            </Tooltip>
          )}
          {/* Empty placeholder for completed tasks without actions */}
          {!canRetry && !canCancel && !canRemove && (
            <div style={{ width: 32 }} />
          )}
        </Group>
      </Group>
      
      {/* Progress bar for running tasks - full width below */}
      {task.status === 'running' && (
        <div style={{ marginTop: 12 }}>
          {task.progress ? (
            <Stack gap={4}>
              <Group justify="space-between">
                <Text size="xs" c="dimmed">
                  {task.progress.done.toLocaleString()} / {task.progress.total.toLocaleString()}
                </Text>
                <Text size="xs" fw={600} c="green">
                  {task.progress.percent}%
                </Text>
              </Group>
              <Progress value={task.progress.percent} size="sm" animated color="green" radius="xl" />
            </Stack>
          ) : (
            <Progress value={100} size="sm" animated striped color="green" radius="xl" />
          )}
        </div>
      )}
    </Card>
  );
}

export function QueuePage() {
  const { data: tasks = [], isLoading } = useQueueTasks(true, 50);
  const { data: stats } = useQueueStats();
  const colorScheme = useComputedColorScheme('light');
  const isDark = colorScheme === 'dark';
  
  const startQueue = useStartQueue();
  const pauseQueue = usePauseQueue();
  const resumeQueue = useResumeQueue();
  const stopQueue = useStopQueue();
  
  const activeTasks = tasks.filter(t => !['done', 'failed', 'cancelled', 'skipped'].includes(t.status));
  const completedTasks = tasks.filter(t => ['done', 'failed', 'cancelled', 'skipped'].includes(t.status));
  
  // Calculate completion percentage
  const completionPercent = stats && stats.total > 0 
    ? Math.round((stats.done / stats.total) * 100) 
    : 0;
  
  return (
    <Stack gap="md">
      <Card>
        <Group justify="space-between" mb="lg">
          <Group gap="sm">
            <IconListCheck size={28} color="#12b886" />
            <Title order={2}>Task Queue</Title>
          </Group>
          
          <Group gap="sm">
            {stats?.executor_running ? (
              <>
                {stats.executor_paused ? (
                  <Button
                    leftSection={<IconPlayerPlay size={16} />}
                    onClick={() => resumeQueue.mutate()}
                    loading={resumeQueue.isPending}
                    color="green"
                    variant="filled"
                  >
                    Fortsetzen
                  </Button>
                ) : (
                  <Button
                    leftSection={<IconPlayerPause size={16} />}
                    onClick={() => pauseQueue.mutate()}
                    loading={pauseQueue.isPending}
                    color="orange"
                    variant="filled"
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
                size="md"
              >
                Queue starten
              </Button>
            )}
          </Group>
        </Group>
        
        {stats && (
          <Group gap="lg" align="flex-start">
            {/* Stats Badges */}
            <Group gap="sm" style={{ flex: 1 }}>
              <Tooltip label="In der Warteschlange" withArrow>
                <Badge color="blue" variant="light" size="lg" leftSection={<IconHourglass size={14} />}>
                  {stats.queued}
                </Badge>
              </Tooltip>
              <Tooltip label="Warten auf Abhängigkeiten" withArrow>
                <Badge color="yellow" variant="light" size="lg" leftSection={<IconClock size={14} />}>
                  {stats.waiting}
                </Badge>
              </Tooltip>
              <Tooltip label="Wird ausgeführt" withArrow>
                <Badge color="green" variant="light" size="lg" leftSection={<IconRocket size={14} />}>
                  {stats.running}
                </Badge>
              </Tooltip>
              <Tooltip label="Erfolgreich abgeschlossen" withArrow>
                <Badge color="teal" variant="light" size="lg" leftSection={<IconCheck size={14} />}>
                  {stats.done}
                </Badge>
              </Tooltip>
              <Tooltip label="Fehlgeschlagen" withArrow>
                <Badge color="red" variant="light" size="lg" leftSection={<IconAlertTriangle size={14} />}>
                  {stats.failed}
                </Badge>
              </Tooltip>
              <Tooltip label="Abgebrochen" withArrow>
                <Badge color="gray" variant="light" size="lg" leftSection={<IconBan size={14} />}>
                  {stats.cancelled}
                </Badge>
              </Tooltip>
            </Group>
            
            {/* Completion Ring */}
            {stats.total > 0 && (
              <Group gap="xs" align="center">
                <RingProgress
                  size={60}
                  thickness={6}
                  roundCaps
                  sections={[
                    { value: (stats.done / stats.total) * 100, color: 'teal' },
                    { value: (stats.failed / stats.total) * 100, color: 'red' },
                    { value: (stats.running / stats.total) * 100, color: 'green' },
                  ]}
                  label={
                    <Text ta="center" size="xs" fw={700}>
                      {completionPercent}%
                    </Text>
                  }
                />
                <Stack gap={0}>
                  <Text size="xs" c="dimmed">Gesamt</Text>
                  <Text fw={600}>{stats.total}</Text>
                </Stack>
              </Group>
            )}
          </Group>
        )}
      </Card>
      
      {isLoading ? (
        <Card withBorder padding="xl">
          <Stack align="center" gap="md">
            <IconListCheck size={48} color={isDark ? '#5c5f66' : '#adb5bd'} />
            <Text c="dimmed">Tasks werden geladen...</Text>
          </Stack>
        </Card>
      ) : (
        <>
          {activeTasks.length > 0 && (
            <div>
              <Group gap="sm" mb="sm">
                <IconRocket size={20} color="#22c55e" />
                <Title order={3}>Aktive Tasks</Title>
                <Badge color="green" variant="light" size="sm">{activeTasks.length}</Badge>
              </Group>
              <Stack gap="sm">
                {activeTasks.map(task => (
                  <TaskCard key={task.id} task={task} />
                ))}
              </Stack>
            </div>
          )}
          
          {completedTasks.length > 0 && (
            <div>
              <Group gap="sm" mb="sm">
                <IconCheck size={20} color="#14b8a6" />
                <Title order={3}>Abgeschlossene Tasks</Title>
                <Badge color="gray" variant="light" size="sm">{completedTasks.length}</Badge>
              </Group>
              <Stack gap="sm">
                {completedTasks.map(task => (
                  <TaskCard key={task.id} task={task} />
                ))}
              </Stack>
            </div>
          )}
          
          {tasks.length === 0 && (
            <Card withBorder padding="xl">
              <Stack align="center" gap="md">
                <IconListCheck size={48} color={isDark ? '#5c5f66' : '#adb5bd'} />
                <Text c="dimmed" ta="center">
                  Keine Tasks in der Queue.
                </Text>
                <Text c="dimmed" ta="center" size="sm">
                  Füge Tasks über die Benchmark- oder AttrGen-Modals hinzu.
                </Text>
              </Stack>
            </Card>
          )}
        </>
      )}
    </Stack>
  );
}
