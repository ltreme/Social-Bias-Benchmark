import { useEffect, useMemo, useState } from 'react';
import { Modal, Group, Select, Checkbox, Textarea, TextInput, Button, Radio, Stack, Card, Text, ThemeIcon, Divider, SimpleGrid } from '@mantine/core';
import { useAttrgenRuns, useDatasetRuns, useStartBenchmark } from '../hooks';
import { useAddTask, useQueueTasks } from '../../queue/hooks';
import { NumericTextInput } from './NumericTextInput';
import { IconPlayerPlay, IconClockPlay, IconCpu, IconSettings, IconTerminal, IconRefresh } from '@tabler/icons-react';
import { useThemedColor } from '../../../lib/useThemeColors';
import { useReadOnly } from '../../../contexts/ReadOnlyContext';

type Props = {
  opened: boolean;
  onClose: () => void;
  datasetId: number;
  initialModelName?: string;
  attrgenRunId?: number;
  onStarted?: (runId: number) => void;
};

export function BenchmarkModal({ opened, onClose, datasetId, initialModelName, attrgenRunId, onStarted }: Props) {
  const { isReadOnly } = useReadOnly();
  const runsList = useAttrgenRuns(datasetId);
  const startBench = useStartBenchmark();
  const addTask = useAddTask();
  const { data: runs } = useDatasetRuns(datasetId);
  const { data: queueTasks } = useQueueTasks(false);

  const completedModels = useMemo(() => {
    const runs = runsList.data?.runs || [];
    const stats: Record<string, { total: number; completed: number }> = {};
    for (const run of runs) {
      const name = run.model_name || '';
      if (!name) continue;
      const total = run.total ?? 0;
      const done = run.done ?? 0;
      if (!stats[name]) {
        stats[name] = { total: 0, completed: 0 };
      }
      stats[name].total += total;
      stats[name].completed += done;
    }
    
    // Add models from queued AttrGen tasks
    const queuedAttrGenModels = new Set<string>();
    if (queueTasks) {
      for (const task of queueTasks) {
        if (task.task_type === 'attrgen' && task.config?.model_name) {
          queuedAttrGenModels.add(task.config.model_name);
        }
      }
    }
    
    const completedEntries = Object.entries(stats)
      .map(([name, s]) => {
        const percentage = s.total > 0 ? s.completed / s.total : 0;
        return { value: name, label: `${name} (${Math.round(percentage * 100)}%)`, ready: percentage >= 0.99 };
      })
      .filter((entry) => entry.ready);
    
    // Add queued models
    const queuedEntries = Array.from(queuedAttrGenModels)
      .filter(name => !stats[name] || stats[name].completed < stats[name].total * 0.99)
      .map(name => ({ value: name, label: `${name} (in Queue)` }));
    
    return [...completedEntries, ...queuedEntries];
  }, [runsList.data?.runs, queueTasks]);

  const [modelName, setModelName] = useState<string>(initialModelName || '');
  const [resumeRunId, setResumeRunId] = useState<number | undefined>(undefined);

  const [batchSizeStr, setBatchSizeStr] = useState('20');
  const [maxNewStr, setMaxNewStr] = useState('192');
  const [maxAttemptsStr, setMaxAttemptsStr] = useState('3');
  const [batchSize, setBatchSize] = useState(20);
  const [maxNew, setMaxNew] = useState(192);
  const [maxAttempts, setMaxAttempts] = useState(3);

  const [includeRationale, setIncludeRationale] = useState(false);
  const [scaleMode, setScaleMode] = useState<'in' | 'rev' | 'random50'>('random50');
  const [dualFrac, setDualFrac] = useState<number>(0.2);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [vllmBase, setVllmBase] = useState('http://host.docker.internal:8000');
  const [vllmApiKey, setVllmApiKey] = useState('');

  const [executionMode, setExecutionMode] = useState<'immediate' | 'queue'>('queue');
  const [dependsOn, setDependsOn] = useState<number | undefined>(undefined);

  // Filter queued/waiting AttrGen tasks for dependency selection
  const availableAttrGenTasks = useMemo(() => {
    if (!queueTasks) return [];
    return queueTasks
      .filter(t => t.task_type === 'attrgen' && (t.status === 'queued' || t.status === 'waiting'))
      .map(t => ({
        value: String(t.id),
        label: t.label || `AttrGen Task #${t.id}`,
      }));
  }, [queueTasks]);

  // Auto-select model when AttrGen task is selected
  useEffect(() => {
    if (dependsOn && queueTasks) {
      const selectedTask = queueTasks.find(t => t.id === dependsOn);
      if (selectedTask?.config?.model_name) {
        setModelName(selectedTask.config.model_name);
      }
    }
  }, [dependsOn, queueTasks]);

  const getColor = useThemedColor();

  return (
    <Modal opened={opened} onClose={onClose} title="Benchmark starten" size="lg">
      <Stack gap="md">
        {/* Execution Mode */}
        <Card withBorder p="md" bg={executionMode === 'immediate' ? getColor('gray').bg : getColor('blue').bg}>
          <Group gap="sm" mb="sm">
            <ThemeIcon size="lg" radius="md" color={executionMode === 'immediate' ? 'gray' : 'blue'} variant="light">
              {executionMode === 'immediate' ? <IconPlayerPlay size={20} /> : <IconClockPlay size={20} />}
            </ThemeIcon>
            <div style={{ flex: 1 }}>
              <Text fw={500}>{executionMode === 'immediate' ? 'Sofort starten' : 'Zur Queue hinzufügen'}</Text>
              <Text size="sm" c="dimmed">
                {executionMode === 'immediate' 
                  ? 'Nicht empfohlen – kann zu Überlastung führen' 
                  : 'Benchmark wird zur Warteschlange hinzugefügt'}
              </Text>
            </div>
          </Group>
          <Radio.Group
            value={executionMode}
            onChange={(v) => setExecutionMode(v as 'immediate' | 'queue')}
          >
            <Group>
              <Radio value="queue" label="Queue (empfohlen)" />
              <Radio value="immediate" label="Sofort (deprecated)" c="dimmed" />
            </Group>
          </Radio.Group>
        </Card>

        {executionMode === 'queue' && availableAttrGenTasks.length > 0 && (
          <Select
            label="Warten auf AttrGen-Task"
            data={availableAttrGenTasks}
            value={dependsOn ? String(dependsOn) : null}
            onChange={(v) => setDependsOn(v ? Number(v) : undefined)}
            clearable
            placeholder="Optional: AttrGen-Task auswählen"
            description="Benchmark startet erst nach Abschluss des ausgewählten AttrGen-Tasks"
          />
        )}

        <Divider label="Modell & Konfiguration" labelPosition="center" />

        {/* Model Selection */}
        <Card withBorder p="md">
          <Group gap="sm" mb="md">
            <ThemeIcon size="lg" radius="md" color="violet" variant="light">
              <IconCpu size={20} />
            </ThemeIcon>
            <div>
              <Text fw={500}>Modell</Text>
              <Text size="sm" c="dimmed">Wähle das Modell für den Benchmark</Text>
            </div>
          </Group>
          <Select
            data={completedModels}
            value={modelName}
            onChange={(v) => setModelName(v || '')}
            placeholder={completedModels.length ? "Model wählen" : "Keine Modelle verfügbar"}
            searchable
            disabled={!!resumeRunId || completedModels.length === 0}
            nothingFoundMessage="Kein Modell gefunden"
          />
        </Card>

        {/* Benchmark Parameters */}
        <Card withBorder p="md">
          <Group gap="sm" mb="md">
            <ThemeIcon size="lg" radius="md" color="teal" variant="light">
              <IconSettings size={20} />
            </ThemeIcon>
            <div>
              <Text fw={500}>Benchmark Parameter</Text>
              <Text size="sm" c="dimmed">Einstellungen für die Befragung</Text>
            </div>
          </Group>
          <SimpleGrid cols={2} spacing="md">
            <Select
              label="Likert-Reihenfolge"
              data={[
                { value: 'in', label: 'In Reihenfolge' }, 
                { value: 'rev', label: 'Umgekehrt' }, 
                { value: 'random50', label: '50/50 Zufall' }
              ]}
              value={scaleMode}
              onChange={(v) => setScaleMode((v as any) || 'in')}
              description="Reihenfolge der Skala im Prompt"
              disabled={!!resumeRunId}
            />
            <Select
              label="Doppel-Befragung"
              data={[
                { value: '0', label: '0% (keine)' },
                { value: '0.1', label: '10%' },
                { value: '0.15', label: '15%' },
                { value: '0.2', label: '20%' },
              ]}
              value={String(dualFrac)}
              onChange={(v) => setDualFrac(Number(v || '0'))}
              description="Anteil in beiden Richtungen"
              disabled={!!resumeRunId}
            />
          </SimpleGrid>
          <Checkbox 
            label="Rationale inkludieren" 
            description="LLM soll Begründung für die Antwort generieren"
            checked={includeRationale} 
            onChange={(e) => setIncludeRationale(e.currentTarget.checked)} 
            mt="md"
          />
          <Textarea 
            label="System Prompt" 
            description="Optionaler System-Prompt für das LLM"
            minRows={2} 
            value={systemPrompt} 
            onChange={(e) => setSystemPrompt(e.currentTarget.value)} 
            mt="md"
          />
        </Card>

        {/* vLLM Settings */}
        <Card withBorder p="md">
          <Group gap="sm" mb="md">
            <ThemeIcon size="lg" radius="md" color="gray" variant="light">
              <IconTerminal size={20} />
            </ThemeIcon>
            <div>
              <Text fw={500}>vLLM Verbindung</Text>
              <Text size="sm" c="dimmed">Einstellungen für den vLLM-Server</Text>
            </div>
          </Group>
          <SimpleGrid cols={2} spacing="md" mb="md">
            <TextInput 
              label="Base URL" 
              value={vllmBase} 
              onChange={(e) => setVllmBase(e.currentTarget.value)} 
            />
            <TextInput 
              label="API Key" 
              value={vllmApiKey} 
              onChange={(e) => setVllmApiKey(e.currentTarget.value)} 
              placeholder="Nutze .env, falls leer" 
            />
          </SimpleGrid>
          <SimpleGrid cols={3} spacing="md">
            <NumericTextInput label="Batch Size" value={batchSizeStr} setValue={setBatchSizeStr} min={1} onCommit={setBatchSize} placeholder="z.B. 8" />
            <NumericTextInput label="Max Tokens" value={maxNewStr} setValue={setMaxNewStr} min={32} onCommit={setMaxNew} placeholder="z.B. 192" />
            <NumericTextInput label="Max Attempts" value={maxAttemptsStr} setValue={setMaxAttemptsStr} min={1} onCommit={setMaxAttempts} placeholder="z.B. 3" />
          </SimpleGrid>
        </Card>

        {/* Resume Run */}
        {runs && runs.length > 0 && (
          <Card withBorder p="md">
            <Group gap="sm" mb="md">
              <ThemeIcon size="lg" radius="md" color="orange" variant="light">
                <IconRefresh size={20} />
              </ThemeIcon>
              <div>
                <Text fw={500}>Run fortsetzen</Text>
                <Text size="sm" c="dimmed">Einen abgebrochenen Benchmark-Run fortsetzen</Text>
              </div>
            </Group>
            <Select
              data={(runs || []).map((r) => ({ 
                value: String(r.id), 
                label: `#${r.id} · ${r.model_name} · ${new Date(r.created_at).toLocaleString()}` 
              }))}
              value={resumeRunId ? String(resumeRunId) : null}
              onChange={(v) => setResumeRunId(v ? Number(v) : undefined)}
              clearable
              placeholder="Optional: Run zum Fortsetzen wählen"
            />
          </Card>
        )}

        <Divider />

        {/* Action Buttons */}
        <Group justify="right">
          <Button variant="default" onClick={onClose}>
            Abbrechen
          </Button>
          <Button
            leftSection={executionMode === 'immediate' ? <IconPlayerPlay size={16} /> : <IconClockPlay size={16} />}
            color={executionMode === 'immediate' ? 'green' : 'blue'}
            loading={startBench.isPending || addTask.isPending}
            disabled={!modelName && !resumeRunId}
            onClick={async () => {
              try {
                const bs = Math.max(1, parseInt(batchSizeStr || String(batchSize), 10) || batchSize);
                const mn = Math.max(32, parseInt(maxNewStr || String(maxNew), 10) || maxNew);
                const ma = Math.max(1, parseInt(maxAttemptsStr || String(maxAttempts), 10) || maxAttempts);

                const config = {
                  dataset_id: datasetId,
                  model_name: modelName || undefined,
                  include_rationale: includeRationale,
                  llm: 'vllm' as const,
                  batch_size: bs,
                  max_new_tokens: mn,
                  max_attempts: ma,
                  system_prompt: systemPrompt || undefined,
                  vllm_base_url: vllmBase,
                  vllm_api_key: vllmApiKey || undefined,
                  resume_run_id: resumeRunId,
                  scale_mode: resumeRunId ? undefined : scaleMode,
                  dual_fraction: resumeRunId ? undefined : dualFrac,
                  attrgen_run_id: attrgenRunId,
                };

                if (executionMode === 'immediate') {
                  const rs = await startBench.mutateAsync(config);
                  onStarted?.(rs.run_id);
                } else {
                  await addTask.mutateAsync({
                    task_type: 'benchmark',
                    config,
                    depends_on: dependsOn,
                  });
                }
                onClose();
              } catch (e) {
                /* no-op */
              }
            }}
          >
            {executionMode === 'immediate' ? 'Benchmark starten' : 'Zur Queue hinzufügen'}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
