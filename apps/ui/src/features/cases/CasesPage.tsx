import { useState } from 'react';
import { ActionIcon, Button, Card, Group, Menu, Title } from '@mantine/core';
import type { ColumnDef } from '@tanstack/react-table';
import { DataTable } from '../../components/DataTable';
import { useCases, useCreateCase, useDeleteCase, useUpdateCase } from './hooks';
import { CaseModal } from './CaseModal';
import type { CaseItem } from './api';

export function CasesPage() {
  const { data = [], isLoading } = useCases();
  const createM = useCreateCase();
  const updateM = useUpdateCase();
  const deleteM = useDeleteCase();
  const [modal, setModal] = useState<null | { mode: 'create' } | { mode: 'edit'; row: CaseItem }>(null);

  const columns: ColumnDef<CaseItem>[] = [
    { header: 'ID', accessorKey: 'id' },
    { header: 'Adjektiv', accessorKey: 'adjective' },
    { header: 'Case Template', accessorKey: 'case_template' },
    { header: 'Verknüpfte Ergebnisse', accessorKey: 'linked_results_n' },
    { header: '', accessorKey: 'actions', cell: ({ row }) => (
      <Menu withinPortal position="bottom-end">
        <Menu.Target>
          <ActionIcon variant="subtle">⋯</ActionIcon>
        </Menu.Target>
        <Menu.Dropdown>
          <Menu.Label>Aktionen</Menu.Label>
          <Menu.Item onClick={() => setModal({ mode: 'edit', row: row.original })}>Bearbeiten…</Menu.Item>
          <Menu.Divider />
          <Menu.Item color="red" disabled={row.original.linked_results_n > 0} onClick={async () => {
            if (!confirm(`Case ${row.original.id} wirklich löschen?`)) return;
            try { await deleteM.mutateAsync(row.original.id); } catch { /* handled globally */ }
          }}>Löschen…</Menu.Item>
        </Menu.Dropdown>
      </Menu>
    ) },
  ];

  return (
    <Card>
      <Group justify="space-between" mb="md">
        <Title order={2}>Cases</Title>
        <Button onClick={() => setModal({ mode: 'create' })}>Case hinzufügen</Button>
      </Group>
      {isLoading ? 'Laden…' : <DataTable data={data} columns={columns} />}

      {modal && modal.mode === 'create' && (
        <CaseModal
          opened
          onClose={() => setModal(null)}
          mode="create"
          initial={null}
          onSubmit={async (v) => { await createM.mutateAsync(v); }}
        />
      )}
      {modal && modal.mode === 'edit' && (
        <CaseModal
          opened
          onClose={() => setModal(null)}
          mode="edit"
          initial={modal.row}
          onSubmit={async (v) => { await updateM.mutateAsync({ id: modal.row.id, ...v }); }}
        />
      )}
    </Card>
  );
}

