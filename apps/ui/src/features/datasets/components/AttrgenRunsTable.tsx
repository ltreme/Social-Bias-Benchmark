import { Group, ActionIcon, Badge } from '@mantine/core';
import { Link } from '@tanstack/react-router';
import { DataTable } from '../../../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import { IconPlayerPlay, IconUsers, IconTrash, IconCheck, IconX, IconLoader, IconClock } from '@tabler/icons-react';
import type { AttrgenRun } from '../api';
import { useDeleteAttrgenRun } from '../hooks';
import { useReadOnly } from '../../../contexts/ReadOnlyContext';

type Props = {
  datasetId: number;
  runs: AttrgenRun[];
  onRequestBenchmark: (modelName?: string | null, attrgenRunId?: number) => void;
};

export function AttrgenRunsTable({ datasetId, runs, onRequestBenchmark }: Props) {
  const { isReadOnly } = useReadOnly();
  const delAttrRun = useDeleteAttrgenRun(datasetId);

  const columns: ColumnDef<AttrgenRun>[] = [
    { header: 'ID', accessorKey: 'id', cell: ({ row }) => <>#{row.original.id}</>, size: 60 },
    { header: 'Model', accessorKey: 'model_name', cell: ({ row }) => row.original.model_name || '' },
    {
      header: 'Status',
      accessorKey: 'status',
      size: 140,
      cell: ({ row }) => {
        const r = row.original;
        const stateRaw = (r.status || '').toLowerCase();
        const isDone = stateRaw === 'done' || ((r.done ?? 0) > 0 && (r.total ?? 0) > 0 && r.done === r.total);
        
        if (stateRaw === 'failed') {
          return <Badge leftSection={<IconX size={12} />} variant="light" color="red" title={r.error || ''}>Fehlgeschlagen</Badge>;
        }
        if (isDone) {
          return <Badge leftSection={<IconCheck size={12} />} variant="light" color="green">Fertig</Badge>;
        }
        if (stateRaw === 'queued') {
          return <Badge leftSection={<IconClock size={12} />} variant="light" color="yellow">Wartend</Badge>;
        }
        
        // Running or other active states
        return (
          <Badge leftSection={<IconLoader size={12} className="spin" />} variant="light" color="blue">
            {r.done ?? 0}/{r.total ?? 0}
          </Badge>
        );
      },
    },
    { header: 'Erstellt', accessorKey: 'created_at', size: 160, cell: ({ row }) => (row.original.created_at ? new Date(row.original.created_at).toLocaleString() : '') },
    {
      header: 'Aktionen',
      accessorKey: 'actions',
      size: 120,
      cell: ({ row }) => {
        const r = row.original;
        const isDone = r.status === 'done' || ((r.done ?? 0) > 0 && (r.total ?? 0) > 0 && r.done === r.total);
        return (
          <Group gap="xs">
            <ActionIcon 
              title={isReadOnly ? "Nicht verfügbar im Read-Only-Modus" : "Benchmark starten"} 
              variant="light" 
              onClick={() => onRequestBenchmark(r.model_name, r.id)} 
              disabled={!isDone || isReadOnly}
            >
              <IconPlayerPlay size={16} />
            </ActionIcon>
            <ActionIcon title="Personas anzeigen" variant="light" component={Link as any} to={'/datasets/$datasetId/personas'} params={{ datasetId: String(datasetId) }} search={{ attrgenRunId: r.id }}>
              <IconUsers size={16} />
            </ActionIcon>
            <ActionIcon
              title={isReadOnly ? "Nicht verfügbar im Read-Only-Modus" : "Attr-Run löschen"}
              color="red"
              variant="subtle"
              onClick={async () => {
                if (!confirm(`AttrGen-Run #${r.id} wirklich löschen?`)) return;
                try {
                  await delAttrRun.mutateAsync(r.id);
                } catch (e) {
                  /* notification via interceptor */
                }
              }}
              disabled={isReadOnly}
            >
              <IconTrash size={16} />
            </ActionIcon>
          </Group>
        );
      },
    },
  ];

  return <DataTable data={runs} columns={columns} />;
}

