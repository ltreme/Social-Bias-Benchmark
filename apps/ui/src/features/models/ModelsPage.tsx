import { useState } from 'react';
import { ActionIcon, Badge, Button, Card, Group, NumberInput, Table, Text, TextInput, Title, Tooltip, useComputedColorScheme } from '@mantine/core';
import { useCreateModel, useDeleteModel, useModelsAdmin, useUpdateModel } from './hooks';
import { IconCpu, IconPlus, IconTrash, IconDeviceSdCard, IconTerminal2, IconCalendar } from '@tabler/icons-react';
import { useReadOnly } from '../../contexts/ReadOnlyContext';

// Helper to format date nicely
function formatDate(dateStr?: string | null): string {
  if (!dateStr) return '–';
  const d = new Date(dateStr);
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function ModelsPage() {
  const { isReadOnly } = useReadOnly();
  const { data = [], isLoading } = useModelsAdmin();
  const create = useCreateModel();
  const update = useUpdateModel();
  const del = useDeleteModel();
  const [name, setName] = useState('');
  const [minVram, setMinVram] = useState<number | undefined>(undefined);
  const [serveCmd, setServeCmd] = useState('');
  const colorScheme = useComputedColorScheme('light');
  const isDark = colorScheme === 'dark';

  async function handleCreate() {
    if (!name.trim()) return;
    try {
      await create.mutateAsync({ name: name.trim(), min_vram: minVram, vllm_serve_cmd: serveCmd || undefined });
      setName(''); setMinVram(undefined); setServeCmd('');
    } catch (e) { /* handled globally */ }
  }

  return (
    <Card>
      <Group justify="space-between" mb="lg">
        <Group gap="sm">
          <IconCpu size={28} color="#228be6" />
          <Title order={2}>Modelle</Title>
          <Badge variant="light" color="blue" size="lg">{data.length}</Badge>
        </Group>
      </Group>

      {/* Create Form */}
      <Card 
        withBorder 
        mb="lg" 
        padding="lg" 
        style={{ 
          background: isDark ? 'rgba(34, 139, 230, 0.08)' : 'rgba(34, 139, 230, 0.05)',
          borderColor: isDark ? 'rgba(34, 139, 230, 0.3)' : 'rgba(34, 139, 230, 0.2)'
        }}
      >
        <Group gap="xs" mb="md">
          <IconPlus size={18} color="#228be6" />
          <Text fw={600} c="blue">Neues Modell hinzufügen</Text>
        </Group>
        <Group grow align="flex-end">
          <TextInput 
            label="Modellname" 
            placeholder="z.B. Qwen/Qwen3-4B-Instruct-2507-FP8" 
            value={name} 
            onChange={(e) => setName(e.currentTarget.value)}
            leftSection={<IconCpu size={16} />}
          />
          <NumberInput 
            label="min VRAM (GB)" 
            placeholder="z.B. 16"
            value={minVram} 
            onChange={(v) => setMinVram(v as number | undefined)} 
            min={0}
            leftSection={<IconDeviceSdCard size={16} />}
          />
          <TextInput 
            label="vLLM Serve Command" 
            placeholder="vllm serve model-name --dtype auto ..." 
            value={serveCmd} 
            onChange={(e) => setServeCmd(e.currentTarget.value)}
            leftSection={<IconTerminal2 size={16} />}
          />
          <Button 
            onClick={handleCreate} 
            loading={create.isPending} 
            disabled={!name.trim() || isReadOnly}
            leftSection={<IconPlus size={16} />}
            color="blue"
            title={isReadOnly ? 'Nicht verfügbar im Read-Only-Modus' : undefined}
          >
            Anlegen
          </Button>
        </Group>
      </Card>

      {isLoading ? (
        <Text c="dimmed" ta="center" py="xl">Modelle werden geladen…</Text>
      ) : data.length === 0 ? (
        <Text c="dimmed" ta="center" py="xl">Keine Modelle vorhanden. Lege ein neues Modell an!</Text>
      ) : (
        <Table striped withTableBorder highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th style={{ width: 60 }}>ID</Table.Th>
              <Table.Th style={{ width: 320 }}>
                <Group gap={6}>
                  <IconCpu size={14} />
                  Name
                </Group>
              </Table.Th>
              <Table.Th style={{ width: 120 }}>
                <Group gap={6}>
                  <IconDeviceSdCard size={14} />
                  VRAM (GB)
                </Group>
              </Table.Th>
              <Table.Th>
                <Group gap={6}>
                  <IconTerminal2 size={14} />
                  vLLM Serve Command
                </Group>
              </Table.Th>
              <Table.Th style={{ width: 160 }}>
                <Group gap={6}>
                  <IconCalendar size={14} />
                  Erstellt
                </Group>
              </Table.Th>
              <Table.Th style={{ width: 60 }}></Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data.map((m) => (
              <Table.Tr key={m.id}>
                <Table.Td>
                  <Badge variant="light" color="gray" size="sm">#{m.id}</Badge>
                </Table.Td>
                <Table.Td>
                  <TextInput 
                    value={m.name} 
                    variant="filled"
                    size="sm"
                    onChange={async (e) => {
                      const v = e.currentTarget.value;
                      await update.mutateAsync({ id: m.id, body: { name: v } });
                    }}
                    disabled={isReadOnly}
                  />
                </Table.Td>
                <Table.Td>
                  <NumberInput 
                    value={m.min_vram ?? undefined} 
                    variant="filled"
                    size="sm"
                    placeholder="–"
                    onChange={async (v) => { 
                      await update.mutateAsync({ id: m.id, body: { min_vram: (v as number | undefined) } }); 
                    }} 
                    min={0}
                    suffix=" GB"
                    disabled={isReadOnly}
                  />
                </Table.Td>
                <Table.Td>
                  <TextInput 
                    value={m.vllm_serve_cmd || ''} 
                    variant="filled"
                    size="sm"
                    placeholder="–"
                    onChange={async (e) => { 
                      await update.mutateAsync({ id: m.id, body: { vllm_serve_cmd: e.currentTarget.value } }); 
                    }}
                    disabled={isReadOnly}
                  />
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c={isDark ? 'gray.4' : 'gray.6'}>
                    {formatDate(m.created_at)}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Tooltip label={isReadOnly ? 'Nicht verfügbar im Read-Only-Modus' : 'Modell löschen'} withArrow>
                    <ActionIcon 
                      color="red" 
                      variant="light" 
                      size="md"
                      onClick={async () => {
                        if (!confirm(`Modell #${m.id} (${m.name}) wirklich löschen?`)) return;
                        await del.mutateAsync(m.id);
                      }}
                      disabled={isReadOnly}
                    >
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Tooltip>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Card>
  );
}

