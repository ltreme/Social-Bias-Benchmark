import { Badge, Button, Card, Divider, Group, Modal, NumberInput, Progress, SegmentedControl, Stack, Text, TextInput, ThemeIcon } from '@mantine/core';
import { useEffect, useMemo, useState } from 'react';
import { useBuildBalanced, useBuildCounterfactuals, useCreatePool, useSampleReality, usePoolStatus } from './hooks';
import { IconDatabase, IconScale, IconArrowsExchange, IconUsers } from '@tabler/icons-react';
import { useThemedColor } from '../../lib/useThemeColors';
import { useReadOnly } from '../../contexts/ReadOnlyContext';

type Props = {
  opened: boolean;
  onClose: () => void;
  defaultMode?: 'pool' | 'balanced' | 'reality' | 'counterfactuals';
  datasetId?: number;
  onCreated?: (id: number) => void;
};

const modeDescriptions: Record<string, { icon: React.ReactNode; title: string; desc: string; color: string }> = {
  pool: {
    icon: <IconDatabase size={20} />,
    title: 'Persona-Pool',
    desc: 'Generiert neue synthetische Personas mit demografischen Attributen.',
    color: 'blue',
  },
  balanced: {
    icon: <IconScale size={20} />,
    title: 'Balanced Subset',
    desc: 'Erstellt ein ausgewogenes Subset mit gleicher Verteilung über Attribute.',
    color: 'green',
  },
  reality: {
    icon: <IconUsers size={20} />,
    title: 'Reality Subset',
    desc: 'Zufälliges Subset, das die Originalverteilung beibehält.',
    color: 'orange',
  },
  counterfactuals: {
    icon: <IconArrowsExchange size={20} />,
    title: 'Counterfactuals',
    desc: 'Erzeugt Varianten mit getauschten Attributen für Bias-Analyse.',
    color: 'violet',
  },
};

export function DatasetBuilderModal({ opened, onClose, defaultMode = 'pool', datasetId, onCreated }: Props) {
  const { isReadOnly } = useReadOnly();
  const getColor = useThemedColor();
  const [mode, setMode] = useState<Props['defaultMode']>(defaultMode);

  const [name, setName] = useState<string>('');
  const [n, setN] = useState<number>(2000);
  const [seed, setSeed] = useState<number>(42);
  const [temperature, setTemperature] = useState<number>(0.1);
  const [ageFrom, setAgeFrom] = useState<number>(0);
  const [ageTo, setAgeTo] = useState<number>(100);

  const createPool = useCreatePool();
  const buildBalanced = useBuildBalanced();
  const buildCF = useBuildCounterfactuals();
  const sampleReal = useSampleReality();
  const [poolJobId, setPoolJobId] = useState<number | undefined>(undefined);
  const pool = usePoolStatus(poolJobId);
  const creating = !!poolJobId || createPool.isPending || buildBalanced.isPending || buildCF.isPending || sampleReal.isPending;

  const canSubmit = useMemo(() => {
    if (mode === 'pool') return n > 0;
    if (mode === 'counterfactuals') return !!datasetId;
    if (mode === 'balanced' || mode === 'reality') return !!datasetId && n > 0;
    return false;
  }, [mode, datasetId, n]);

  async function handleCreate() {
    try {
      if (mode === 'pool') {
        const r = await createPool.mutateAsync({ n, temperature, age_from: ageFrom, age_to: ageTo, name: name || undefined }) as any;
        setPoolJobId(Number(r.job_id));
        return;
      } else if (mode === 'balanced') {
        if (!datasetId) return; const r = await buildBalanced.mutateAsync({ dataset_id: datasetId, n, seed, name: name || undefined });
        onCreated?.(r.id); onClose();
      } else if (mode === 'reality') {
        if (!datasetId) return; const r = await sampleReal.mutateAsync({ dataset_id: datasetId, n, seed, name: name || undefined });
        onCreated?.(r.id); onClose();
      } else if (mode === 'counterfactuals') {
        if (!datasetId) return; const r = await buildCF.mutateAsync({ dataset_id: datasetId, seed, name: name || undefined });
        onCreated?.(r.id); onClose();
      }
    } catch (e) {
      // notifications are handled by interceptor
    }
  }

  // Auto-complete when pool job finishes
  useEffect(() => {
    if (poolJobId && pool.data?.status === 'done' && pool.data?.dataset_id) {
      setPoolJobId(undefined);
      onCreated?.(pool.data.dataset_id);
      onClose();
    }
  }, [poolJobId, pool.data?.status, pool.data?.dataset_id]);

  // If no datasetId, only pool mode is available
  const isPoolOnly = !datasetId;
  const availableModes = isPoolOnly 
    ? [{ value: 'pool', label: 'Pool' }]
    : [
        { value: 'balanced', label: 'Balanced' },
        { value: 'reality', label: 'Reality' },
      ];

  // Reset mode when modal opens based on context
  useEffect(() => {
    if (opened) {
      setMode(isPoolOnly ? 'pool' : defaultMode !== 'pool' ? defaultMode : 'balanced');
    }
  }, [opened, isPoolOnly, defaultMode]);

  return (
    <Modal 
      opened={opened} 
      onClose={onClose} 
      title={isPoolOnly ? 'Neuen Persona-Pool erstellen' : 'Subset erstellen'} 
      size="lg"
    >
      {poolJobId ? (
        <Stack gap="md">
          <Card withBorder p="lg">
            <Group gap="md" mb="md">
              <ThemeIcon size="xl" radius="md" color="blue" variant="light">
                <IconDatabase size={24} />
              </ThemeIcon>
              <div>
                <Text fw={600} size="lg">Persona-Pool Generierung</Text>
                <Text size="sm" c="dimmed">
                  {pool.data?.phase === 'sampling' ? 'Personas werden generiert…' : 
                   pool.data?.phase === 'persisting' ? 'Daten werden gespeichert…' : 
                   'Initialisierung…'}
                </Text>
              </div>
            </Group>
            
            <Progress 
              value={pool.data?.pct ?? 0} 
              size="lg" 
              radius="md"
              animated={pool.data?.status === 'running'}
              color={pool.data?.status === 'failed' ? 'red' : 'blue'}
            />
            
            <Group justify="space-between" mt="sm">
              <Text size="sm" c="dimmed">
                {pool.data?.done ?? 0} / {pool.data?.total ?? 0} Personas
              </Text>
              <Text size="sm" c="dimmed">
                {Number.isFinite(pool.data?.eta_sec as number) && (pool.data?.eta_sec as number) > 0
                  ? `~${Math.max(1, Math.round((pool.data?.eta_sec as number)/60))} min verbleibend`
                  : ''}
              </Text>
            </Group>
          </Card>
          
          {pool.data?.status === 'failed' && (
            <Card withBorder p="md" bg={getColor('red').bg}>
              <Text c="red" fw={500}>Fehler: {String(pool.data?.error || 'Unbekannter Fehler')}</Text>
            </Card>
          )}
        </Stack>
      ) : (
      <Stack gap="md">
        {/* Mode Selection - only show if multiple modes available */}
        {!isPoolOnly && (
          <SegmentedControl
            fullWidth
            value={mode}
            onChange={(v) => setMode(v as any)}
            data={availableModes}
          />
        )}
        
        {/* Mode Description Card */}
        {mode && (
          <Card withBorder p="md" bg={getColor(modeDescriptions[mode].color as any).bg}>
            <Group gap="sm">
              <ThemeIcon size="lg" radius="md" color={modeDescriptions[mode].color} variant="light">
                {modeDescriptions[mode].icon}
              </ThemeIcon>
              <div style={{ flex: 1 }}>
                <Text fw={500}>{modeDescriptions[mode].title}</Text>
                <Text size="sm" c="dimmed">{modeDescriptions[mode].desc}</Text>
              </div>
            </Group>
          </Card>
        )}

        <Divider />

        {/* Common: Name */}
        <TextInput 
          label="Dataset-Name" 
          description="Optional – wird automatisch generiert wenn leer"
          placeholder="z.B. balanced-1k-experiment"
          value={name} 
          onChange={(e) => setName(e.currentTarget.value)} 
        />

        {/* Pool-specific options */}
        {mode === 'pool' && (
          <>
            <Group grow>
              <NumberInput 
                label="Anzahl Personas" 
                description="Wie viele Personas sollen generiert werden?"
                value={n} 
                onChange={(v) => setN(Number(v || 0))} 
                min={1}
                thousandSeparator="."
                decimalSeparator=","
              />
              <NumberInput 
                label="Temperature" 
                description="Höher = mehr Variation"
                value={temperature} 
                onChange={(v) => setTemperature(Number(v || 0))} 
                step={0.05} 
                decimalScale={2} 
                min={0} 
                max={2} 
              />
            </Group>
            <Group grow>
              <NumberInput 
                label="Mindestalter" 
                value={ageFrom} 
                onChange={(v) => setAgeFrom(Number(v || 0))} 
                min={0} 
                max={ageTo}
              />
              <NumberInput 
                label="Höchstalter" 
                value={ageTo} 
                onChange={(v) => setAgeTo(Number(v || 0))} 
                min={ageFrom} 
                max={120}
              />
            </Group>
          </>
        )}

        {/* Balanced/Reality options */}
        {(mode === 'balanced' || mode === 'reality') && (
          <Group grow>
            <NumberInput 
              label="Anzahl Personas" 
              description="Größe des Subsets"
              value={n} 
              onChange={(v) => setN(Number(v || 0))} 
              min={1}
              thousandSeparator="."
              decimalSeparator=","
            />
            <NumberInput 
              label="Seed" 
              description="Für Reproduzierbarkeit"
              value={seed} 
              onChange={(v) => setSeed(Number(v || 0))} 
            />
          </Group>
        )}

        {/* Counterfactuals options */}
        {mode === 'counterfactuals' && (
          <NumberInput 
            label="Seed" 
            description="Für Reproduzierbarkeit"
            value={seed} 
            onChange={(v) => setSeed(Number(v || 0))} 
          />
        )}

        {/* Source Dataset Info */}
        {datasetId && mode !== 'pool' && (
          <Card withBorder p="sm" bg={getColor('gray').bg}>
            <Group gap="xs">
              <Badge variant="light" color="gray">Quelle</Badge>
              <Text size="sm">Dataset #{datasetId}</Text>
            </Group>
          </Card>
        )}
      </Stack>
      )}

      <Divider my="md" />

      <Group justify="right">
        <Button variant="default" onClick={onClose}>Abbrechen</Button>
        {!poolJobId && (
          <Button 
            onClick={handleCreate} 
            disabled={!canSubmit || isReadOnly} 
            loading={creating}
            leftSection={mode && modeDescriptions[mode]?.icon}
            title={isReadOnly ? 'Nicht verfügbar im Read-Only-Modus' : undefined}
          >
            Dataset erstellen
          </Button>
        )}
      </Group>
    </Modal>
  );
}
