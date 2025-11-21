import { ActionIcon, Group, Progress } from '@mantine/core';
import { Link } from '@tanstack/react-router';
import { DataTable } from '../../../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import type { Run } from '../api';
import { useDeleteRun } from '../../runs/hooks';
import { useQueryClient } from '@tanstack/react-query';
import { IconExternalLink, IconTrash } from '@tabler/icons-react';

type Props = {
  datasetId: number;
  runs: Run[];
};

export function DatasetRunsTable({ datasetId, runs }: Props) {
  const delRun = useDeleteRun();
  const qc = useQueryClient();

  const columns: ColumnDef<Run & { include_rationale: boolean }>[] = [
    { header: 'ID', accessorKey: 'id', cell: ({ row }) => <>#{row.original.id}</> },
    { header: 'Model', accessorKey: 'model_name' },
    { header: 'Rationale', accessorKey: 'include_rationale', cell: ({ row }) => (row.original.include_rationale ? 'Ja' : 'Nein') },
    { header: 'Erstellt', accessorKey: 'created_at', cell: ({ row }) => (row.original.created_at ? new Date(row.original.created_at).toLocaleString() : '') },
    {
      header: 'Status',
      accessorKey: 'status',
      cell: ({ row }) => {
        const r = row.original;
        const stateRaw = (r.status || 'done').toLowerCase();
        const isDone = ['done', 'failed', 'cancelled'].includes(stateRaw);
        return (
          <div style={{ minWidth: 160 }}>
            {isDone ? (
              <span style={{ color: stateRaw === 'failed' ? '#d32f2f' : '#2ca25f' }}>
                {stateRaw === 'failed' ? 'Fehlgeschlagen' : stateRaw === 'cancelled' ? 'Abgebrochen' : 'Fertig'}
              </span>
            ) : (
              <>
                <span>
                  {r.status || 'unknown'} {r.done ?? 0}/{r.total ?? 0}
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
    {
      header: 'Aktionen',
      accessorKey: 'actions',
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
            title="Run löschen"
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
          >
            <IconTrash size={16} />
          </ActionIcon>
        </Group>
      ),
    },
  ];

  return <DataTable data={runs} columns={columns} />;
}
