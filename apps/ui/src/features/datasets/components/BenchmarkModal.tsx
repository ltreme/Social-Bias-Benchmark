import { useMemo, useState } from 'react';
import { Modal, Group, Select, Checkbox, Textarea, TextInput, Button } from '@mantine/core';
import { useAttrgenRuns, useDatasetRuns, useStartBenchmark } from '../hooks';
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
  const { data: runs } = useDatasetRuns(datasetId);

  const completedModels = useMemo(() => {
    return Array.from(
      new Set(
        (runsList.data?.runs || [])
          .filter((r) => (r.done ?? 0) > 0 && (r.total ?? 0) > 0 && r.done === r.total)
          .map((r) => r.model_name || '')
      )
    ).filter(Boolean) as string[];
  }, [runsList.data?.runs]);

  const [modelName, setModelName] = useState<string>(initialModelName || '');
  const [resumeRunId, setResumeRunId] = useState<number | undefined>(undefined);

  const [batchSizeStr, setBatchSizeStr] = useState('8');
  const [maxNewStr, setMaxNewStr] = useState('192');
  const [maxAttemptsStr, setMaxAttemptsStr] = useState('3');
  const [batchSize, setBatchSize] = useState(8);
  const [maxNew, setMaxNew] = useState(192);
  const [maxAttempts, setMaxAttempts] = useState(3);

  const [includeRationale, setIncludeRationale] = useState(false);
  const [scaleMode, setScaleMode] = useState<'in' | 'rev' | 'random50'>('in');
  const [dualFrac, setDualFrac] = useState<number>(0.15);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [vllmBase, setVllmBase] = useState('http://host.docker.internal:8000');
  const [vllmApiKey, setVllmApiKey] = useState('');

  return (
    <Modal opened={opened} onClose={onClose} title="Benchmark starten" size="lg">
      <Group grow mb="md">
        <Select
          label="Model (aus fertigen AttrGen-Runs)"
          data={completedModels}
          value={modelName}
          onChange={(v) => setModelName(v || '')}
          placeholder="Model wählen"
          searchable
          disabled={!!resumeRunId}
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
          loading={startBench.isPending}
          disabled={!modelName && !resumeRunId}
          onClick={async () => {
            try {
              const bs = Math.max(1, parseInt(batchSizeStr || String(batchSize), 10) || batchSize);
              const mn = Math.max(32, parseInt(maxNewStr || String(maxNew), 10) || maxNew);
              const ma = Math.max(1, parseInt(maxAttemptsStr || String(maxAttempts), 10) || maxAttempts);

              const rs = await startBench.mutateAsync({
                dataset_id: datasetId,
                model_name: modelName || undefined,
                include_rationale: includeRationale,
                llm: 'vllm',
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
              });
              onStarted?.(rs.run_id);
              onClose();
            } catch (e) {
              /* no-op */
            }
          }}
        >
          Benchmark starten
        </Button>
      </Group>
    </Modal>
  );
}
