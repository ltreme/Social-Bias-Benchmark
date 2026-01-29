import { ActionIcon, Badge, Group, Popover, Progress, Text, Tooltip } from '@mantine/core';
import { Link } from '@tanstack/react-router';
import { DataTable } from '../../../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import type { Run } from '../api';
import { useDeleteRun } from '../../runs/hooks';
import { useQueryClient } from '@tanstack/react-query';
import { IconExternalLink, IconMessage, IconMessageCog, IconTrash, IconCheck, IconX, IconPlayerStop, IconLoader, IconClock } from '@tabler/icons-react';
import { useReadOnly } from '../../../contexts/ReadOnlyContext';

type Props = {
  datasetId: number;
  runs: Run[];
};

export function DatasetRunsTable({ datasetId, runs }: Props) {
  const { isReadOnly } = useReadOnly();
  const delRun = useDeleteRun();
  const qc = useQueryClient();

  const columns: ColumnDef<Run>[] = [
    { header: 'ID', accessorKey: 'id', size: 60, cell: ({ row }) => <>#{row.original.id}</> },
    { header: 'Model', accessorKey: 'model_name' },
    {
      header: 'Optionen',
      accessorKey: 'options',
      size: 80,
      cell: ({ row }) => (
        <Group gap={6} wrap="nowrap">
          {row.original.include_rationale && (
            <Tooltip label="Mit Begründungen" withArrow>
              <IconMessage size={18} color="#228be6" />
            </Tooltip>
          )}
          {row.original.system_prompt && (
            <Popover width={400} position="bottom" withArrow shadow="md">
              <Popover.Target>
                <ActionIcon variant="transparent" size="sm" color="orange" style={{ cursor: 'pointer' }}>
                  <IconMessageCog size={18} />
                </ActionIcon>
              </Popover.Target>
              <Popover.Dropdown>
                <Text size="xs" fw={600} mb={4}>Custom System Prompt:</Text>
                <Text size="xs" style={{ whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto' }}>
                  {row.original.system_prompt}
                </Text>
              </Popover.Dropdown>
            </Popover>
          )}
        </Group>
      ),
    },
    {
      header: 'Status',
      accessorKey: 'status',
      size: 140,
      cell: ({ row }) => {
        const r = row.original;
        const stateRaw = (r.status || 'done').toLowerCase();
        const isDone = ['done', 'failed', 'cancelled'].includes(stateRaw);
        
        if (stateRaw === 'done') {
          return <Badge leftSection={<IconCheck size={12} />} variant="light" color="green">Fertig</Badge>;
        }
        if (stateRaw === 'failed') {
          return <Badge leftSection={<IconX size={12} />} variant="light" color="red">Fehlgeschlagen</Badge>;
        }
        if (stateRaw === 'cancelled') {
          return <Badge leftSection={<IconPlayerStop size={12} />} variant="light" color="gray">Abgebrochen</Badge>;
        }
        if (stateRaw === 'queued') {
          return <Badge leftSection={<IconClock size={12} />} variant="light" color="yellow">Wartend</Badge>;
        }
        
        // Running or other active states
        return (
          <div style={{ minWidth: 140 }}>
            <Badge leftSection={<IconLoader size={12} className="spin" />} variant="light" color="blue" mb={4}>
              {r.done ?? 0}/{r.total ?? 0}
            </Badge>
            <Progress value={r.pct ?? 0} size="sm" color="blue" />
          </div>
        );
      },
    },
    { header: 'Erstellt', accessorKey: 'created_at', size: 160, cell: ({ row }) => (row.original.created_at ? new Date(row.original.created_at).toLocaleString() : '') },
    {
      header: 'Aktionen',
      accessorKey: 'actions',
      size: 80,
      cell: ({ row }) => (
        <Group gap="xs">
          {(() => {
            const state = (row.original.status || '').toLowerCase();
            const isActive = ['queued', 'running', 'partial', 'cancelling'].includes(state);
            return (
            <ActionIcon
              title="Run ansehen"
              variant="light"
              component={isActive ? undefined : (Link as any)}
              to={isActive ? undefined : `/runs/${row.original.id}`}
              disabled={isActive}
            >
              <IconExternalLink size={16} />
            </ActionIcon>
            );
          })()}
          <ActionIcon
            variant="subtle"
            color="red"
            title={isReadOnly ? "Nicht verfügbar im Read-Only-Modus" : "Run löschen"}
            onClick={async (e) => {
              e.preventDefault();
              if (!confirm(`Run #${row.original.id} wirklich löschen?`)) return;
              try {
                await delRun.mutateAsync(row.original.id);
                qc.invalidateQueries({ queryKey: ['dataset-runs', datasetId] });
              } catch (err) {
                /* no-op */
              }
            }}
            disabled={isReadOnly}
          >
            <IconTrash size={16} />
          </ActionIcon>
        </Group>
      ),
    },
  ];

  return <DataTable data={runs} columns={columns} />;
}
