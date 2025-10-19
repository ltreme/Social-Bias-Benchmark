import { useEffect, useState } from 'react';
import { Modal, Group, Select, TextInput, Button } from '@mantine/core';
import { useAttrgenRuns, useStartAttrgen } from '../hooks';
import { NumericTextInput } from './NumericTextInput';

type Props = {
  opened: boolean;
  onClose: () => void;
  datasetId: number;
  availableModels?: string[];
  onStarted?: (runId: number) => void;
};

export function AttrGenModal({ opened, onClose, datasetId, availableModels, onStarted }: Props) {
  const runsList = useAttrgenRuns(datasetId);
  const startAttr = useStartAttrgen();

  const [llm, setLlm] = useState<'vllm' | 'fake'>('vllm');
  const [modelName, setModelName] = useState<string>('');
  const [resumeRunId, setResumeRunId] = useState<number | undefined>(undefined);

  const [batchSizeStr, setBatchSizeStr] = useState('8');
  const [maxNewStr, setMaxNewStr] = useState('192');
  const [maxAttemptsStr, setMaxAttemptsStr] = useState('3');
  const [batchSize, setBatchSize] = useState(8);
  const [maxNew, setMaxNew] = useState(192);
  const [maxAttempts, setMaxAttempts] = useState(3);

  const [systemPrompt, setSystemPrompt] = useState('');
  const [vllmBase, setVllmBase] = useState('http://host.docker.internal:8000');

  useEffect(() => {
    if (!opened) {
      // reset resume state when closing
      setResumeRunId(undefined);
    }
  }, [opened]);

  return (
    <Modal opened={opened} onClose={onClose} title="Additional Attributes generieren" size="lg">
      <Group grow mb="md">
        <Select label="Backend" data={[{ value: 'vllm', label: 'vLLM' }, { value: 'fake', label: 'Fake' }]} value={llm} onChange={(v) => setLlm((v as any) || 'vllm')} />
        <Select label="Model" data={availableModels || []} value={modelName} onChange={(v) => setModelName(v || '')} searchable placeholder="Model wählen" />
      </Group>
      <Group grow mb="md">
        <Select
          label="Run fortsetzen"
          data={(runsList.data?.runs || []).map((r) => ({ value: String(r.id), label: `#${r.id} · ${r.model_name ?? ''} · ${new Date(r.created_at).toLocaleString()} · ${Math.round(r.pct || 0)}%` }))}
          value={resumeRunId ? String(resumeRunId) : null}
          onChange={(v) => setResumeRunId(v ? Number(v) : undefined)}
          clearable
          placeholder="Optional"
        />
      </Group>
      {llm === 'vllm' ? <TextInput label="vLLM Base URL" value={vllmBase} onChange={(e) => setVllmBase(e.currentTarget.value)} /> : null}
      <Group grow mb="md">
        <NumericTextInput label="Batch Size" value={batchSizeStr} setValue={setBatchSizeStr} min={1} onCommit={setBatchSize} placeholder="z.B. 8" />
        <NumericTextInput label="Max New Tokens" value={maxNewStr} setValue={setMaxNewStr} min={32} onCommit={setMaxNew} placeholder="z.B. 192" />
        <NumericTextInput label="Max Attempts" value={maxAttemptsStr} setValue={setMaxAttemptsStr} min={1} onCommit={setMaxAttempts} placeholder="z.B. 3" />
      </Group>
      <TextInput label="System Prompt (optional)" value={systemPrompt} onChange={(e) => setSystemPrompt(e.currentTarget.value)} />
      <Group justify="right" mt="md">
        <Button variant="default" onClick={onClose}>
          Abbrechen
        </Button>
        <Button
          loading={startAttr.isPending}
          disabled={!modelName && !resumeRunId}
          onClick={async () => {
            try {
              // ensure committed
              const bs = Math.max(1, parseInt(batchSizeStr || String(batchSize), 10) || batchSize);
              const mn = Math.max(32, parseInt(maxNewStr || String(maxNew), 10) || maxNew);
              const ma = Math.max(1, parseInt(maxAttemptsStr || String(maxAttempts), 10) || maxAttempts);
              setBatchSize(bs);
              setBatchSizeStr(String(bs));
              setMaxNew(mn);
              setMaxNewStr(String(mn));
              setMaxAttempts(ma);
              setMaxAttemptsStr(String(ma));

              const r = await startAttr.mutateAsync({
                dataset_id: datasetId,
                model_name: modelName,
                llm,
                batch_size: bs,
                max_new_tokens: mn,
                max_attempts: ma,
                system_prompt: systemPrompt || undefined,
                vllm_base_url: llm === 'vllm' ? vllmBase : undefined,
                resume_run_id: resumeRunId,
              });
              onStarted?.(r.run_id);
              onClose();
            } catch (e) {
              /* no-op: notifications via interceptors */
            }
          }}
        >
          Starten
        </Button>
      </Group>
    </Modal>
  );
}

