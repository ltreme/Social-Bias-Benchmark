import { useMemo, useRef, useState } from 'react';
import { ActionIcon, Button, Card, Group, Menu, MultiSelect, Switch, Title } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import type { ColumnDef } from '@tanstack/react-table';
import { DataTable } from '../../components/DataTable';
import { useTraits, useCreateTrait, useDeleteTrait, useUpdateTrait, useTraitCategories, useToggleTraitActive, useImportTraitsCsv, triggerTraitsExport } from './hooks';
import { TraitModal } from './TraitModal';
import type { TraitItem } from './api';

export function TraitsPage() {
  const { data = [], isLoading } = useTraits();
  const { data: categories = [], isLoading: catsLoading } = useTraitCategories();
  const createM = useCreateTrait();
  const updateM = useUpdateTrait();
  const deleteM = useDeleteTrait();
  const toggleActiveM = useToggleTraitActive();
  const importCsvM = useImportTraitsCsv();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [modal, setModal] = useState<null | { mode: 'create' } | { mode: 'edit'; row: TraitItem }>(null);
  const [pendingToggleId, setPendingToggleId] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string[]>([]);
  const [valenceFilter, setValenceFilter] = useState<string[]>([]);
  const [sortOrder, setSortOrder] = useState<string[]>(['id']);

  const categoryOptions = useMemo(() => categories, [categories]);

  const compareTraitIds = (aId: string | undefined, bId: string | undefined) => {
    const parse = (val: string) => {
      const m = val?.match(/^([a-zA-Z]+)(\d+)$/);
      if (!m) return { prefix: val ?? '', num: Number.NaN };
      return { prefix: m[1], num: Number.parseInt(m[2], 10) };
    };
    const pa = parse(aId ?? '');
    const pb = parse(bId ?? '');
    if (pa.prefix !== pb.prefix) {
      return pa.prefix.localeCompare(pb.prefix);
    }
    if (!Number.isNaN(pa.num) && !Number.isNaN(pb.num)) {
      return pa.num - pb.num;
    }
    return (aId ?? '').localeCompare(bId ?? '');
  };

  const traitIdSorting: ColumnDef<TraitItem>['sortingFn'] = (rowA, rowB, columnId) => {
    const a = (rowA.getValue(columnId) ?? '') as string;
    const b = (rowB.getValue(columnId) ?? '') as string;
    return compareTraitIds(a, b);
  };

  const sortedData = useMemo(() => {
    const filtered = data.filter((item) => {
      if (categoryFilter.length && (!item.category || !categoryFilter.includes(item.category))) {
        return false;
      }
      if (valenceFilter.length) {
        const val = item.valence ?? null;
        if (val === null || !valenceFilter.includes(String(val))) {
          return false;
        }
      }
      return true;
    });
    const order = sortOrder.length ? sortOrder : ['id'];
    const compareByField = (field: string, a: TraitItem, b: TraitItem): number => {
      switch (field) {
        case 'category':
          if ((a.category ?? '') !== (b.category ?? '')) {
            return (a.category ?? '').localeCompare(b.category ?? '');
          }
          return 0;
        case 'adjective':
          if ((a.adjective ?? '') !== (b.adjective ?? '')) {
            return (a.adjective ?? '').localeCompare(b.adjective ?? '');
          }
          return 0;
        case 'valence':
          if ((a.valence ?? 0) !== (b.valence ?? 0)) {
            return (a.valence ?? 0) - (b.valence ?? 0);
          }
          return 0;
        case 'id':
        default:
          return compareTraitIds(a.id, b.id);
      }
    };
    return [...filtered].sort((a, b) => {
      for (const field of order) {
        const cmp = compareByField(field, a, b);
        if (cmp !== 0) return cmp;
      }
      return compareTraitIds(a.id, b.id);
    });
  }, [data, categoryFilter, valenceFilter, sortOrder]);

  const columns: ColumnDef<TraitItem>[] = [
    { header: 'ID', accessorKey: 'id', sortingFn: traitIdSorting },
    { header: 'Adjektiv', accessorKey: 'adjective' },
    { header: 'Kategorie', accessorKey: 'category' },
    { header: 'Valenz', accessorKey: 'valence' },
    {
      header: 'Aktiv',
      accessorKey: 'is_active',
      cell: ({ row }) => (
        <Switch
          checked={row.original.is_active}
          onChange={(e) => {
            setPendingToggleId(row.original.id);
            toggleActiveM.mutate(
              {
                id: row.original.id,
                is_active: e.currentTarget.checked,
              },
              {
                onSettled: () => setPendingToggleId(null),
              }
            );
          }}
          disabled={pendingToggleId === row.original.id}
          aria-label="Aktivstatus umschalten"
        />
      ),
    },
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
            if (!confirm(`Trait ${row.original.id} wirklich löschen?`)) return;
            try { await deleteM.mutateAsync(row.original.id); } catch { /* handled globally */ }
          }}>Löschen…</Menu.Item>
        </Menu.Dropdown>
      </Menu>
    ) },
  ];

  return (
    <Card>
      <Group justify="space-between" mb="md">
        <Title order={2}>Traits</Title>
        <Group gap="xs">
          <Button variant="light" onClick={async () => {
            try {
              await triggerTraitsExport();
              notifications.show({ color: 'green', title: 'Export erstellt', message: 'traits.csv wurde heruntergeladen.' });
            } catch (err) {
              notifications.show({ color: 'red', title: 'Export fehlgeschlagen', message: String(err) });
            }
          }}>CSV exportieren</Button>
          <Button variant="light" onClick={() => fileInputRef.current?.click()} loading={importCsvM.isPending}>CSV importieren</Button>
          <Button onClick={() => setModal({ mode: 'create' })}>Trait hinzufügen</Button>
        </Group>
      </Group>
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,text/csv"
        style={{ display: 'none' }}
        onChange={async (e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          try {
            const result = await importCsvM.mutateAsync(file);
            notifications.show({
              color: 'green',
              title: 'Import abgeschlossen',
              message: `Neu: ${result.inserted}, aktualisiert: ${result.updated}, übersprungen: ${result.skipped}`,
            });
          } catch (err) {
            notifications.show({ color: 'red', title: 'Import fehlgeschlagen', message: String(err) });
          } finally {
            e.target.value = '';
          }
        }}
      />
      <Group mb="md" gap="md" align="flex-end" wrap="wrap">
        <MultiSelect
          label="Kategorie filtern"
          placeholder="Alle Kategorien"
          data={categoryOptions.map((c) => ({ value: c, label: c }))}
          value={categoryFilter}
          onChange={setCategoryFilter}
          searchable
          clearable
          w={260}
        />
        <MultiSelect
          label="Valenz filtern"
          placeholder="Alle"
          data={[
            { value: '1', label: 'Positiv (+1)' },
            { value: '0', label: 'Neutral (0)' },
            { value: '-1', label: 'Negativ (-1)' },
          ]}
          value={valenceFilter}
          onChange={setValenceFilter}
          clearable
          w={240}
        />
        <MultiSelect
          label="Sortierreihenfolge"
          placeholder="Standard (ID)"
          data={[
            { value: 'id', label: 'ID' },
            { value: 'adjective', label: 'Adjektiv' },
            { value: 'category', label: 'Kategorie' },
            { value: 'valence', label: 'Valenz' },
          ]}
          value={sortOrder}
          onChange={(vals) => setSortOrder(vals.length ? vals : ['id'])}
          clearable
          w={300}
        />
      </Group>
      {isLoading || catsLoading ? 'Laden…' : (
        <DataTable
          data={sortedData}
          columns={columns}
          getRowId={(row) => row.id}
        />
      )}

      {modal && modal.mode === 'create' && (
        <TraitModal
          opened
          onClose={() => setModal(null)}
          mode="create"
          initial={null}
          categoryOptions={categoryOptions}
          onSubmit={async (v) => { await createM.mutateAsync(v); }}
        />
      )}
      {modal && modal.mode === 'edit' && (
        <TraitModal
          opened
          onClose={() => setModal(null)}
          mode="edit"
          initial={modal.row}
          categoryOptions={categoryOptions}
          onSubmit={async (v) => { await updateM.mutateAsync({ id: modal.row.id, ...v }); }}
        />
      )}
    </Card>
  );
}
