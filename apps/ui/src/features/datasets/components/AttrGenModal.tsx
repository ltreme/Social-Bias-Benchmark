import { useEffect, useState } from 'react';
import { Modal, Group, Select, TextInput, Button, Radio, Stack, Card, Text, ThemeIcon, Divider, SimpleGrid, Textarea } from '@mantine/core';
import { IconPlayerPlay, IconClockPlay, IconCpu, IconSettings, IconTerminal, IconRefresh } from '@tabler/icons-react';
import { useAttrgenRuns, useStartAttrgen } from '../hooks';
import { useAddTask } from '../../queue/hooks';
import { NumericTextInput } from './NumericTextInput';
import { useThemedColor } from '../../../lib/useThemeColors';

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
  const addTask = useAddTask();

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

  const [executionMode, setExecutionMode] = useState<'immediate' | 'queue'>('queue');

  useEffect(() => {
    if (!opened) {
      // reset resume state when closing
      setResumeRunId(undefined);
    }
  }, [opened]);

  const runs = runsList.data?.runs || [];
  const getColor = useThemedColor();

  return (
    <Modal opened={opened} onClose={onClose} title="Attribute generieren" size="lg">
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
                  : 'Task wird zur Warteschlange hinzugefügt'}
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

        <Divider label="Modell & Konfiguration" labelPosition="center" />

        {/* Model Selection */}
        <Card withBorder p="md">
          <Group gap="sm" mb="md">
            <ThemeIcon size="lg" radius="md" color="violet" variant="light">
              <IconCpu size={20} />
            </ThemeIcon>
            <div>
              <Text fw={500}>Modell</Text>
              <Text size="sm" c="dimmed">Wähle das Modell für die Attribut-Generierung</Text>
            </div>
          </Group>
          <SimpleGrid cols={2} spacing="md">
            <Select 
              label="Backend" 
              data={[{ value: 'vllm', label: 'vLLM' }, { value: 'fake', label: 'Fake' }]} 
              value={llm} 
              onChange={(v) => setLlm((v as any) || 'vllm')} 
            />
            <Select 
              label="Model" 
              data={availableModels || []} 
              value={modelName} 
              onChange={(v) => setModelName(v || '')} 
              searchable 
              placeholder="Model wählen"
              disabled={!!resumeRunId}
              nothingFoundMessage="Kein Modell gefunden"
            />
          </SimpleGrid>
        </Card>

        {/* Generation Parameters */}
        <Card withBorder p="md">
          <Group gap="sm" mb="md">
            <ThemeIcon size="lg" radius="md" color="teal" variant="light">
              <IconSettings size={20} />
            </ThemeIcon>
            <div>
              <Text fw={500}>Generierungs-Parameter</Text>
              <Text size="sm" c="dimmed">Einstellungen für die Attribut-Generierung</Text>
            </div>
          </Group>
          <Textarea 
            label="System Prompt" 
            description="Optionaler System-Prompt für das LLM"
            minRows={2} 
            value={systemPrompt} 
            onChange={(e) => setSystemPrompt(e.currentTarget.value)} 
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
          <TextInput 
            label="Base URL" 
            value={vllmBase} 
            onChange={(e) => setVllmBase(e.currentTarget.value)} 
            mb="md"
          />
          <SimpleGrid cols={3} spacing="md">
            <NumericTextInput label="Batch Size" value={batchSizeStr} setValue={setBatchSizeStr} min={1} onCommit={setBatchSize} placeholder="z.B. 8" />
            <NumericTextInput label="Max Tokens" value={maxNewStr} setValue={setMaxNewStr} min={32} onCommit={setMaxNew} placeholder="z.B. 192" />
            <NumericTextInput label="Max Attempts" value={maxAttemptsStr} setValue={setMaxAttemptsStr} min={1} onCommit={setMaxAttempts} placeholder="z.B. 3" />
          </SimpleGrid>
        </Card>

        {/* Resume Run */}
        {runs.length > 0 && (
          <Card withBorder p="md">
            <Group gap="sm" mb="md">
              <ThemeIcon size="lg" radius="md" color="orange" variant="light">
                <IconRefresh size={20} />
              </ThemeIcon>
              <div>
                <Text fw={500}>Run fortsetzen</Text>
                <Text size="sm" c="dimmed">Einen abgebrochenen Run fortsetzen</Text>
              </div>
            </Group>
            <Select
              data={runs.map((r) => ({ 
                value: String(r.id), 
                label: `#${r.id} · ${r.model_name ?? ''} · ${new Date(r.created_at).toLocaleString()} · ${Math.round(r.pct || 0)}%` 
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
            loading={startAttr.isPending || addTask.isPending}
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

              const config = {
                dataset_id: datasetId,
                model_name: modelName,
                llm,
                batch_size: bs,
                max_new_tokens: mn,
                max_attempts: ma,
                system_prompt: systemPrompt || undefined,
                vllm_base_url: llm === 'vllm' ? vllmBase : undefined,
                resume_run_id: resumeRunId,
              };

              if (executionMode === 'immediate') {
                const r = await startAttr.mutateAsync(config);
                onStarted?.(r.run_id);
              } else {
                await addTask.mutateAsync({
                  task_type: 'attrgen',
                  config,
                  depends_on: undefined,
                });
              }
              onClose();
            } catch (e) {
              /* no-op: notifications via interceptors */
            }
          }}
        >
          {executionMode === 'immediate' ? 'Starten' : 'Zur Queue hinzufügen'}
        </Button>
      </Group>
      </Stack>
    </Modal>
  );
}

