import { Button, Group, Modal, NumberInput, Select, TextInput } from '@mantine/core';
import { useEffect, useMemo, useState } from 'react';
import { useBuildBalanced, useBuildCounterfactuals, useCreatePool, useSampleReality } from './hooks';

type Props = {
  opened: boolean;
  onClose: () => void;
  defaultMode?: 'pool' | 'balanced' | 'reality' | 'counterfactuals';
  datasetId?: number;
  onCreated?: (id: number) => void;
};

export function DatasetBuilderModal({ opened, onClose, defaultMode = 'pool', datasetId, onCreated }: Props) {
  const [mode, setMode] = useState<Props['defaultMode']>(defaultMode);
  useEffect(() => { setMode(defaultMode); }, [defaultMode]);

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

  const creating = createPool.isPending || buildBalanced.isPending || buildCF.isPending || sampleReal.isPending;

  const canSubmit = useMemo(() => {
    if (mode === 'pool') return n > 0;
    if (mode === 'counterfactuals') return !!datasetId;
    if (mode === 'balanced' || mode === 'reality') return !!datasetId && n > 0;
    return false;
  }, [mode, datasetId, n]);

  async function handleCreate() {
    try {
      if (mode === 'pool') {
        const r = await createPool.mutateAsync({ n, temperature, age_from: ageFrom, age_to: ageTo, name: name || undefined });
        onCreated?.(r.id); onClose();
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

  return (
    <Modal opened={opened} onClose={onClose} title="Dataset erstellen" size="lg">
      <Group grow mb="md">
        <Select label="Modus" data={[
          { value: 'pool', label: 'Persona-Pool generieren' },
          { value: 'balanced', label: 'Balanced aus Dataset' },
          { value: 'reality', label: 'Random Subset (Reality)' },
          { value: 'counterfactuals', label: 'Counterfactuals aus Dataset' },
        ]} value={mode} onChange={(v) => setMode((v as any) || 'pool')} />
        <TextInput label="Name (optional)" value={name} onChange={(e) => setName(e.currentTarget.value)} />
      </Group>

      {mode === 'pool' && (
        <>
          <Group grow mb="md">
            <NumberInput label="Anzahl n" value={n} onChange={(v) => setN(Number(v || 0))} min={1} />
            <NumberInput label="Temperature" value={temperature} onChange={(v) => setTemperature(Number(v || 0))} step={0.05} precision={2} min={0} max={2} />
          </Group>
          <Group grow mb="md">
            <NumberInput label="Alter von" value={ageFrom} onChange={(v) => setAgeFrom(Number(v || 0))} min={0} />
            <NumberInput label="Alter bis" value={ageTo} onChange={(v) => setAgeTo(Number(v || 0))} min={ageFrom} />
          </Group>
        </>
      )}

      {(mode === 'balanced' || mode === 'reality') && (
        <Group grow mb="md">
          <NumberInput label="n" value={n} onChange={(v) => setN(Number(v || 0))} min={1} />
          <NumberInput label="Seed" value={seed} onChange={(v) => setSeed(Number(v || 0))} />
        </Group>
      )}

      {mode === 'counterfactuals' && (
        <Group grow mb="md">
          <NumberInput label="Seed" value={seed} onChange={(v) => setSeed(Number(v || 0))} />
        </Group>
      )}

      <Group justify="right">
        <Button variant="default" onClick={onClose}>Abbrechen</Button>
        <Button onClick={handleCreate} disabled={!canSubmit} loading={creating}>Datensatz erstellen</Button>
      </Group>
    </Modal>
  );
}

