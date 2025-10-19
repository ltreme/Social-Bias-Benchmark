import { Group, ActionIcon, Progress } from '@mantine/core';
import { Link } from '@tanstack/react-router';
import { DataTable } from '../../../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import { IconPlayerPlay, IconUsers, IconTrash } from '@tabler/icons-react';
import type { AttrgenRun } from '../api';
import { useDeleteAttrgenRun } from '../hooks';

type Props = {
  datasetId: number;
  runs: AttrgenRun[];
  onRequestBenchmark: (modelName?: string | null, attrgenRunId?: number) => void;
};

export function AttrgenRunsTable({ datasetId, runs, onRequestBenchmark }: Props) {
  const delAttrRun = useDeleteAttrgenRun(datasetId);

  const columns: ColumnDef<AttrgenRun>[] = [
    { header: 'ID', accessorKey: 'id', cell: ({ row }) => <>#{row.original.id}</> },
    { header: 'Model', accessorKey: 'model_name', cell: ({ row }) => row.original.model_name || '' },
    {
      header: 'Status',
      accessorKey: 'status',
      cell: ({ row }) => {
        const r = row.original;
        const isDone = r.status === 'done' || ((r.done ?? 0) > 0 && (r.total ?? 0) > 0 && r.done === r.total);
        return (
          <div style={{ minWidth: 180 }}>
            {r.status === 'failed' ? (
              <span style={{ color: '#d32f2f' }} title={r.error || ''}>
                Fehlgeschlagen
              </span>
            ) : isDone ? (
              <span style={{ color: '#2ca25f' }}>Fertig</span>
            ) : (
              <>
                <span>
                  {r.status} {r.done ?? 0}/{r.total ?? 0}
                </span>
                <div style={{ width: 140 }}>
                  <Progress value={r.pct ?? 0} mt="xs" />
                </div>
              </>
            )}
          </div>
        );
      },
    },
    { header: 'Erstellt', accessorKey: 'created_at', cell: ({ row }) => (row.original.created_at ? new Date(row.original.created_at).toLocaleString() : '') },
    {
      header: 'Aktionen',
      accessorKey: 'actions',
      cell: ({ row }) => {
        const r = row.original;
        const isDone = r.status === 'done' || ((r.done ?? 0) > 0 && (r.total ?? 0) > 0 && r.done === r.total);
        return (
          <Group gap="xs">
            <ActionIcon title="Benchmark starten" variant="light" onClick={() => onRequestBenchmark(r.model_name, r.id)} disabled={!isDone}>
              <IconPlayerPlay size={16} />
            </ActionIcon>
            <ActionIcon title="Personas anzeigen" variant="light" component={Link as any} to={'/datasets/$datasetId/personas'} params={{ datasetId: String(datasetId) }} search={{ attrgenRunId: r.id }}>
              <IconUsers size={16} />
            </ActionIcon>
            <ActionIcon
              title="Attr-Run löschen"
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

