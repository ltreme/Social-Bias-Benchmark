import { useState } from 'react';
import { Button, Card, Group, NumberInput, Table, TextInput, Title } from '@mantine/core';
import { useCreateModel, useDeleteModel, useModelsAdmin, useUpdateModel } from './hooks';

export function ModelsPage() {
  const { data = [], isLoading } = useModelsAdmin();
  const create = useCreateModel();
  const update = useUpdateModel();
  const del = useDeleteModel();
  const [name, setName] = useState('');
  const [minVram, setMinVram] = useState<number | undefined>(undefined);
  const [serveCmd, setServeCmd] = useState('');

  async function handleCreate() {
    if (!name.trim()) return;
    try {
      await create.mutateAsync({ name: name.trim(), min_vram: minVram, vllm_serve_cmd: serveCmd || undefined });
      setName(''); setMinVram(undefined); setServeCmd('');
    } catch (e) { /* handled globally */ }
  }

  return (
    <Card>
      <Group justify="space-between" mb="md">
        <Title order={2}>Modelle</Title>
      </Group>

      <Card withBorder mb="md" padding="md">
        <Group grow>
          <TextInput label="Name" placeholder="z.B. mistral-7b-instruct" value={name} onChange={(e) => setName(e.currentTarget.value)} />
          <NumberInput label="min VRAM (GB)" value={minVram} onChange={(v) => setMinVram(v as number | undefined)} min={0} />
          <TextInput label="vLLM Serve Cmd" placeholder="python -m vllm.entrypoints.openai.api_server --model ..." value={serveCmd} onChange={(e) => setServeCmd(e.currentTarget.value)} />
        </Group>
        <Group justify="right" mt="sm">
          <Button onClick={handleCreate} loading={create.isPending} disabled={!name.trim()}>Neu anlegen</Button>
        </Group>
      </Card>

      {isLoading ? 'Laden…' : (
        <Table striped withTableBorder>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>ID</Table.Th>
              <Table.Th>Name</Table.Th>
              <Table.Th>min VRAM</Table.Th>
              <Table.Th>vLLM Serve Cmd</Table.Th>
              <Table.Th>Erstellt</Table.Th>
              <Table.Th></Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data.map((m) => (
              <Table.Tr key={m.id}>
                <Table.Td>#{m.id}</Table.Td>
                <Table.Td>
                  <TextInput value={m.name} onChange={async (e) => {
                    const v = e.currentTarget.value;
                    await update.mutateAsync({ id: m.id, body: { name: v } });
                  }} />
                </Table.Td>
                <Table.Td>
                  <NumberInput value={m.min_vram ?? undefined} onChange={async (v) => { await update.mutateAsync({ id: m.id, body: { min_vram: (v as number | undefined) } }); }} min={0} />
                </Table.Td>
                <Table.Td>
                  <TextInput value={m.vllm_serve_cmd || ''} onChange={async (e) => { await update.mutateAsync({ id: m.id, body: { vllm_serve_cmd: e.currentTarget.value } }); }} />
                </Table.Td>
                <Table.Td>{m.created_at || ''}</Table.Td>
                <Table.Td>
                  <Button color="red" variant="light" size="xs" onClick={async () => {
                    if (!confirm(`Modell #${m.id} (${m.name}) löschen?`)) return;
                    await del.mutateAsync(m.id);
                  }}>Löschen</Button>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Card>
  );
}

