import { useMemo, useRef, useState } from 'react';
import { ActionIcon, Badge, Button, Card, Checkbox, Group, Menu, Modal, MultiSelect, Stack, Switch, Text, Title, Tooltip, useComputedColorScheme } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import type { ColumnDef } from '@tanstack/react-table';
import { DataTable } from '../../components/DataTable';
import { useTraits, useCreateTrait, useDeleteTrait, useUpdateTrait, useTraitCategories, useToggleTraitActive, useImportTraitsCsv, triggerTraitsExport, triggerFilteredTraitsExport } from './hooks';
import { TraitModal } from './TraitModal';
import type { TraitItem } from './api';
import { IconList, IconPlus, IconDownload, IconUpload, IconFilter, IconCategory, IconMoodSmile, IconToggleLeft, IconDotsVertical, IconEdit, IconTrash, IconLink } from '@tabler/icons-react';

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
  const [activeFilter, setActiveFilter] = useState<string[]>([]);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [useFiltersForExport, setUseFiltersForExport] = useState(false);
  const colorScheme = useComputedColorScheme('light');
  const isDark = colorScheme === 'dark';

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

  const traitIdSorting: ColumnDef<TraitItem>['sortingFn'] = (rowA: any, rowB: any, columnId: any) => {
    const a = (rowA.getValue(columnId) ?? '') as string;
    const b = (rowB.getValue(columnId) ?? '') as string;
    return compareTraitIds(a, b);
  };

  // Filter data (sorting is now handled by the DataTable)
  const filteredData = useMemo(() => {
    return data.filter((item: TraitItem) => {
      if (categoryFilter.length && (!item.category || !categoryFilter.includes(item.category))) {
        return false;
      }
      if (valenceFilter.length) {
        const val = item.valence ?? null;
        if (val === null || !valenceFilter.includes(String(val))) {
          return false;
        }
      }
      if (activeFilter.length) {
        const isActive = item.is_active;
        if (!activeFilter.includes(isActive ? 'active' : 'inactive')) {
          return false;
        }
      }
      return true;
    });
  }, [data, categoryFilter, valenceFilter, activeFilter]);

  const columns: ColumnDef<TraitItem>[] = [
    { 
      header: 'ID', 
      accessorKey: 'id', 
      sortingFn: traitIdSorting,
      cell: ({ row }: any) => (
        <Badge variant="light" color="gray" size="sm">{row.original.id}</Badge>
      )
    },
    { 
      header: 'Adjektiv', 
      accessorKey: 'adjective',
      cell: ({ row }: any) => (
        <Text fw={500}>{row.original.adjective}</Text>
      )
    },
    { 
      header: 'Kategorie', 
      accessorKey: 'category',
      cell: ({ row }: any) => (
        <Badge variant="light" color="violet" size="sm">{row.original.category}</Badge>
      )
    },
    { 
      header: 'Valenz', 
      accessorKey: 'valence',
      cell: ({ row }: any) => {
        const val = row.original.valence;
        const color = val === 1 ? 'green' : val === -1 ? 'red' : 'gray';
        const label = val === 1 ? '+1' : val === -1 ? '−1' : '0';
        return <Badge variant="light" color={color} size="sm">{label}</Badge>;
      }
    },
    {
      header: 'Aktiv',
      accessorKey: 'is_active',
      cell: ({ row }: any) => (
        <Switch
          checked={row.original.is_active}
          onChange={(e: any) => {
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
          color="teal"
        />
      ),
    },
    { 
      header: 'Verknüpfte Ergebnisse', 
      accessorKey: 'linked_results_n',
      cell: ({ row }: any) => {
        const count = row.original.linked_results_n;
        if (count === 0) {
          return <Text size="sm" c="dimmed">0</Text>;
        }
        return (
          <Group gap={4}>
            <IconLink size={14} color={isDark ? '#909296' : '#868e96'} />
            <Text size="sm" fw={500}>{count.toLocaleString('de-DE')}</Text>
          </Group>
        );
      }
    },
    { 
      header: '', 
      accessorKey: 'actions', 
      cell: ({ row }: any) => (
        <Menu withinPortal position="bottom-end">
          <Menu.Target>
            <Tooltip label="Aktionen" withArrow>
              <ActionIcon variant="subtle" color="gray">
                <IconDotsVertical size={16} />
              </ActionIcon>
            </Tooltip>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Label>Aktionen</Menu.Label>
            <Menu.Item 
              leftSection={<IconEdit size={14} />}
              onClick={() => setModal({ mode: 'edit', row: row.original })}
            >
              Bearbeiten
            </Menu.Item>
            <Menu.Divider />
            <Menu.Item 
              color="red" 
              leftSection={<IconTrash size={14} />}
              disabled={row.original.linked_results_n > 0} 
              onClick={async () => {
                if (!confirm(`Trait ${row.original.id} wirklich löschen?`)) return;
                try { await deleteM.mutateAsync(row.original.id); } catch { /* handled globally */ }
              }}
            >
              Löschen
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>
      ) 
    },
  ];

  return (
    <Card>
      <Group justify="space-between" mb="lg">
        <Group gap="sm">
          <IconList size={28} color="#7950f2" />
          <Title order={2}>Traits</Title>
          <Badge variant="light" color="violet" size="lg">{data.length}</Badge>
        </Group>
        <Group gap="xs">
          <Button 
            variant="light" 
            color="teal"
            leftSection={<IconUpload size={16} />}
            onClick={() => setExportModalOpen(true)}
          >
            CSV exportieren
          </Button>
          <Button 
            variant="light" 
            color="blue"
            leftSection={<IconDownload size={16} />}
            onClick={() => fileInputRef.current?.click()} 
            loading={importCsvM.isPending}
          >
            CSV importieren
          </Button>
          <Button 
            color="violet"
            leftSection={<IconPlus size={16} />}
            onClick={() => setModal({ mode: 'create' })}
          >
            Trait hinzufügen
          </Button>
        </Group>
      </Group>
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,text/csv"
        style={{ display: 'none' }}
        onChange={async (e: any) => {
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
      
      {/* Filter Card */}
      <Card 
        withBorder 
        mb="lg" 
        padding="lg" 
        style={{ 
          background: isDark ? 'rgba(121, 80, 242, 0.08)' : 'rgba(121, 80, 242, 0.05)',
          borderColor: isDark ? 'rgba(121, 80, 242, 0.3)' : 'rgba(121, 80, 242, 0.2)'
        }}
      >
        <Group gap="xs" mb="md">
          <IconFilter size={18} color="#7950f2" />
          <Text fw={600} c="violet">Filter & Sortierung</Text>
        </Group>
        <Group gap="md" align="flex-end" wrap="wrap">
          <MultiSelect
            label="Kategorie"
            placeholder="Alle Kategorien"
            leftSection={<IconCategory size={14} />}
            data={categoryOptions.map((c: string) => ({ value: c, label: c }))}
            value={categoryFilter}
            onChange={setCategoryFilter}
            searchable
            clearable
            w={240}
          />
          <MultiSelect
            label="Valenz"
            placeholder="Alle"
            leftSection={<IconMoodSmile size={14} />}
            data={[
              { value: '1', label: 'Positiv (+1)' },
              { value: '0', label: 'Neutral (0)' },
              { value: '-1', label: 'Negativ (−1)' },
            ]}
            value={valenceFilter}
            onChange={setValenceFilter}
            clearable
            w={220}
          />
          <MultiSelect
            label="Status"
            placeholder="Alle"
            leftSection={<IconToggleLeft size={14} />}
            data={[
              { value: 'active', label: 'Aktiv' },
              { value: 'inactive', label: 'Inaktiv' },
            ]}
            value={activeFilter}
            onChange={setActiveFilter}
            clearable
            w={200}
          />
        </Group>
        <Text size="xs" c="dimmed" mt="sm">
          💡 Klicke auf eine Spaltenüberschrift zum Sortieren
        </Text>
      </Card>
      
      <Group mb="md" justify="space-between" align="center">
        <Group gap="sm">
          <Text size="sm" c="dimmed">
            {filteredData.length} von {data.length} Trait{data.length !== 1 ? 's' : ''} 
          </Text>
          {filteredData.length !== data.length && (
            <Badge variant="light" color="orange" size="sm">gefiltert</Badge>
          )}
        </Group>
      </Group>
      
      {isLoading || catsLoading ? (
        <Text c="dimmed" ta="center" py="xl">Traits werden geladen…</Text>
      ) : data.length === 0 ? (
        <Text c="dimmed" ta="center" py="xl">Keine Traits vorhanden. Importiere Traits via CSV oder lege neue an!</Text>
      ) : (
        <DataTable
          data={filteredData}
          columns={columns}
          getRowId={(row) => row.id}
          enableSorting
          initialSorting={[{ id: 'id', desc: false }]}
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

      <Modal
        opened={exportModalOpen}
        onClose={() => setExportModalOpen(false)}
        title="CSV exportieren"
      >
        <Stack gap="md">
          <Checkbox
            label="Filter und Reihenfolge verwenden"
            description="Exportiert nur die gefilterten und sortierten Traits in der aktuellen Reihenfolge"
            checked={useFiltersForExport}
            onChange={(e: any) => setUseFiltersForExport(e.currentTarget.checked)}
          />
          <Group justify="flex-end" gap="sm">
            <Button variant="default" onClick={() => setExportModalOpen(false)}>
              Abbrechen
            </Button>
            <Button onClick={async () => {
              try {
                if (useFiltersForExport) {
                  // Export mit Filtern: filteredData IDs an Backend senden
                  const traitIds = filteredData.map((trait: TraitItem) => trait.id);
                  await triggerFilteredTraitsExport(traitIds);
                } else {
                  // Standard-Export: alle Daten vom Server
                  await triggerTraitsExport();
                }
                setExportModalOpen(false);
                notifications.show({ 
                  color: 'green', 
                  title: 'Export erstellt', 
                  message: useFiltersForExport 
                    ? `${filteredData.length} gefilterte Traits wurden exportiert.`
                    : 'traits.csv wurde heruntergeladen.' 
                });
              } catch (err) {
                notifications.show({ color: 'red', title: 'Export fehlgeschlagen', message: String(err) });
              }
            }}>
              Exportieren
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Card>
  );
}
