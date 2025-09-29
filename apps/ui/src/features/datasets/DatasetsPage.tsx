import { useState } from 'react';
import { ActionIcon, Button, Card, Group, Menu, Title } from '@mantine/core';
import { Link, useNavigate } from '@tanstack/react-router';
import { useDatasets, useDeleteDataset } from './hooks';
import { DataTable } from '../../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import type { Dataset } from './api';
import { DatasetBuilderModal } from './DatasetBuilderModal';

export function DatasetsPage() {
    const [q, setQ] = useState<string | undefined>();
    const { data = [], isLoading } = useDatasets(q);
    const [builderOpen, setBuilderOpen] = useState(false);
    const [rowBuilder, setRowBuilder] = useState<{ mode: 'balanced' | 'reality' | 'counterfactuals'; id: number } | null>(null);
    const navigate = useNavigate();
    const delDs = useDeleteDataset();

    const columns: ColumnDef<Dataset>[] = [
        { header: 'ID', accessorKey: 'id' },
        { header: 'Name', accessorKey: 'name', cell: ({ row }) => (
            <Link to="/datasets/$datasetId" params={{ datasetId: String(row.original.id) }}>{row.original.name}</Link>
        ) },
        { header: 'Size', accessorKey: 'size' },
        { header: 'Art', accessorKey: 'kind' },
        { header: 'Erstellt', accessorKey: 'created_at' },
        { header: 'Seed', accessorKey: 'seed' },
        { header: '', accessorKey: 'actions', cell: ({ row }) => (
            <Menu withinPortal position="bottom-end">
              <Menu.Target>
                <ActionIcon variant="subtle">⋯</ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Label>Aktionen</Menu.Label>
                <Menu.Item onClick={() => setRowBuilder({ mode: 'balanced', id: row.original.id })}>Balanced erstellen…</Menu.Item>
                <Menu.Item onClick={() => setRowBuilder({ mode: 'reality', id: row.original.id })}>Subset erstellen…</Menu.Item>
                <Menu.Item onClick={() => setRowBuilder({ mode: 'counterfactuals', id: row.original.id })}>Counterfactuals…</Menu.Item>
                <Menu.Divider />
                <Menu.Item color="red" onClick={async () => {
                  if (!confirm(`Dataset "${row.original.name}" (#${row.original.id}) wirklich löschen?`)) return;
                  try {
                    await delDs.mutateAsync(row.original.id);
                  } catch (e) { /* handled globally */ }
                }}>Löschen…</Menu.Item>
              </Menu.Dropdown>
            </Menu>
        ) },
    ];

    return (
        <Card>
        <Group justify="space-between" mb="md">
          <Title order={2}>Datasets</Title>
          <Button onClick={() => setBuilderOpen(true)}>Neues Dataset</Button>
        </Group>
        {/* simple input instead of Filters for brevity */}
        <input placeholder="Search…" onChange={(e) => setQ(e.target.value)} />
        {isLoading ? 'Laden…' : <DataTable data={data} columns={columns} />}
        <DatasetBuilderModal
          opened={builderOpen}
          onClose={() => setBuilderOpen(false)}
          defaultMode='pool'
          onCreated={(id) => navigate({ to: '/datasets/$datasetId', params: { datasetId: String(id) } })}
        />
        {rowBuilder && (
          <DatasetBuilderModal
            opened={!!rowBuilder}
            onClose={() => setRowBuilder(null)}
            defaultMode={rowBuilder.mode}
            datasetId={rowBuilder.id}
            onCreated={(id) => navigate({ to: '/datasets/$datasetId', params: { datasetId: String(id) } })}
          />
        )}
        </Card>
    );
}
