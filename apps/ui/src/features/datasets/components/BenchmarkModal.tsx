import { useEffect, useMemo, useState } from 'react';
import { Modal, Group, Select, Checkbox, Textarea, TextInput, Button, Radio } from '@mantine/core';
import { useAttrgenRuns, useDatasetRuns, useStartBenchmark } from '../hooks';
import { useAddTask, useQueueTasks } from '../../queue/hooks';
import { NumericTextInput } from './NumericTextInput';

type Props = {
  opened: boolean;
  onClose: () => void;
  datasetId: number;
  initialModelName?: string;
  attrgenRunId?: number;
  onStarted?: (runId: number) => void;
};

export function BenchmarkModal({ opened, onClose, datasetId, initialModelName, attrgenRunId, onStarted }: Props) {
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

  return (
    <Modal opened={opened} onClose={onClose} title="Benchmark starten" size="lg">
      <Radio.Group
        label="Ausführungsmodus"
        value={executionMode}
        onChange={(v) => setExecutionMode(v as 'immediate' | 'queue')}
        mb="md"
      >
        <Group mt="xs">
          <Radio value="immediate" label="Sofort starten" />
          <Radio value="queue" label="Zur Queue hinzufügen" />
        </Group>
      </Radio.Group>
      {executionMode === 'queue' && (
        <Select
          label="Warten auf AttrGen-Task (optional)"
          data={availableAttrGenTasks}
          value={dependsOn ? String(dependsOn) : null}
          onChange={(v) => setDependsOn(v ? Number(v) : undefined)}
          clearable
          placeholder={availableAttrGenTasks.length ? "Optional: AttrGen-Task auswählen" : "Keine wartenden AttrGen-Tasks"}
          description="Benchmark startet erst nach Abschluss des ausgewählten AttrGen-Tasks"
          mb="md"
        />
      )}
      <Group grow mb="md">
        <Select
          label="Model"
          data={completedModels}
          value={modelName}
          onChange={(v) => setModelName(v || '')}
          placeholder={completedModels.length ? "Model wählen" : "Keine Modelle verfügbar"}
          searchable
          disabled={!!resumeRunId || completedModels.length === 0}
          nothingFoundMessage="Kein Modell gefunden"
        />
        <NumericTextInput label="Batch Size" value={batchSizeStr} setValue={setBatchSizeStr} min={1} onCommit={setBatchSize} placeholder="z.B. 8" />
      </Group>
      <Group grow mb="md">
        <NumericTextInput label="Max New Tokens" value={maxNewStr} setValue={setMaxNewStr} min={32} onCommit={setMaxNew} placeholder="z.B. 192" />
        <NumericTextInput label="Max Attempts" value={maxAttemptsStr} setValue={setMaxAttemptsStr} min={1} onCommit={setMaxAttempts} placeholder="z.B. 3" />
      </Group>
      <Checkbox label="Rationale inkludieren" checked={includeRationale} onChange={(e) => setIncludeRationale(e.currentTarget.checked)} />
      <Select
        label="Likert-Reihenfolge"
        data={[{ value: 'in', label: 'in order' }, { value: 'rev', label: 'reversed order' }, { value: 'random50', label: '50/50 random' }]}
        value={scaleMode}
        onChange={(v) => setScaleMode((v as any) || 'in')}
        description="Steuert die Reihenfolge der Skala im Prompt"
        disabled={!!resumeRunId}
      />
      <Select
        label="Doppel-Befragung Anteil"
        data={[
          { value: '0', label: '0%' },
          { value: '0.1', label: '10%' },
          { value: '0.15', label: '15%' },
          { value: '0.2', label: '20%' },
        ]}
        value={String(dualFrac)}
        onChange={(v) => setDualFrac(Number(v || '0'))}
        description="Anteil der Paare, die in beiden Richtungen gefragt werden"
        disabled={!!resumeRunId}
      />
      <Textarea label="System Prompt (optional)" minRows={3} value={systemPrompt} onChange={(e) => setSystemPrompt(e.currentTarget.value)} />
      <Group grow mb="md" mt="md">
        <TextInput label="vLLM Base URL" value={vllmBase} onChange={(e) => setVllmBase(e.currentTarget.value)} />
        <TextInput label="vLLM API Key (optional)" value={vllmApiKey} onChange={(e) => setVllmApiKey(e.currentTarget.value)} placeholder="Nutze .env, falls leer" />
      </Group>
      <Group grow mb="md">
        <Select
          label="Run fortsetzen"
          data={(runs || []).map((r) => ({ value: String(r.id), label: `#${r.id} · ${r.model_name} · ${new Date(r.created_at).toLocaleString()}` }))}
          value={resumeRunId ? String(resumeRunId) : null}
          onChange={(v) => setResumeRunId(v ? Number(v) : undefined)}
          clearable
          placeholder="Optional"
        />
      </Group>
      <Group justify="right" mt="md">
        <Button variant="default" onClick={onClose}>
          Abbrechen
        </Button>
        <Button
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
    </Modal>
  );
}
