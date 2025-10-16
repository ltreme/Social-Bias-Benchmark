import { ActionIcon } from '@mantine/core';
import { Link } from '@tanstack/react-router';
import { DataTable } from '../../../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import type { Run } from '../api';
import { useDeleteRun } from '../../runs/hooks';
import { useQueryClient } from '@tanstack/react-query';

type Props = {
  datasetId: number;
  runs: Array<{ id: number; model_name: string; include_rationale: boolean; created_at: string }>;
};

export function DatasetRunsTable({ datasetId, runs }: Props) {
  const delRun = useDeleteRun();
  const qc = useQueryClient();

  const columns: ColumnDef<Run & { include_rationale: boolean }>[] = [
    { header: 'ID', accessorKey: 'id', cell: ({ row }) => <Link to={`/runs/${row.original.id}`}>#{row.original.id}</Link> },
    { header: 'Model', accessorKey: 'model_name' },
    { header: 'Rationale', accessorKey: 'include_rationale', cell: ({ row }) => (row.original.include_rationale ? 'Ja' : 'Nein') },
    { header: 'Erstellt', accessorKey: 'created_at', cell: ({ row }) => (row.original.created_at ? new Date(row.original.created_at).toLocaleString() : '') },
    {
      header: '',
      accessorKey: 'actions',
      cell: ({ row }) => (
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
          🗑️
        </ActionIcon>
      ),
    },
  ];

  return <DataTable data={runs} columns={columns} />;
}

