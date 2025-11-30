import { useMemo, useState } from 'react';
import { ActionIcon, Badge, Button, Card, Group, Menu, TextInput, Title, Tooltip } from '@mantine/core';
import { useNavigate } from '@tanstack/react-router';
import { useDatasets, useDeleteDataset, useDeleteStatus } from './hooks';
import { DataTable } from '../../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import type { Dataset } from './api';
import { DatasetBuilderModal } from './DatasetBuilderModal';
import { IconCornerDownRight, IconDatabase, IconDotsVertical, IconExternalLink, IconPlus, IconPlayerPlay, IconSearch, IconSitemap, IconUsers } from '@tabler/icons-react';

// Extended type with depth for hierarchical display
type DatasetWithDepth = Dataset & { _depth: number };

// Helper to format date nicely
function formatDate(dateStr?: string | null): string {
    if (!dateStr) return '–';
    const d = new Date(dateStr);
    return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

// Helper to format large numbers compactly (1K, 2M, etc.)
function formatCompactNumber(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n % 1_000_000 === 0 ? 0 : 1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(n % 1_000 === 0 ? 0 : 1)}K`;
    return String(n);
}

// Build hierarchical tree structure
function buildHierarchy(datasets: Dataset[]): DatasetWithDepth[] {
    const result: DatasetWithDepth[] = [];
    const byId = new Map(datasets.map(d => [d.id, d]));
    const childrenOf = new Map<number | null, Dataset[]>();
    
    // Group by parent
    for (const ds of datasets) {
        const parentId = ds.source_dataset_id ?? null;
        if (!childrenOf.has(parentId)) childrenOf.set(parentId, []);
        childrenOf.get(parentId)!.push(ds);
    }
    
    // Sort children by created_at desc
    for (const children of childrenOf.values()) {
        children.sort((a, b) => {
            const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
            const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
            return dateB - dateA;
        });
    }
    
    // Recursively add nodes
    function addNode(ds: Dataset, depth: number) {
        result.push({ ...ds, _depth: depth });
        const children = childrenOf.get(ds.id) || [];
        for (const child of children) {
            addNode(child, depth + 1);
        }
    }
    
    // Start with root nodes (no parent)
    const roots = childrenOf.get(null) || [];
    for (const root of roots) {
        addNode(root, 0);
    }
    
    return result;
}

// Map kind to icon and color
function kindBadge(kind: string) {
    switch (kind) {
        case 'pool':
            return <Badge leftSection={<IconDatabase size={12} />} variant="light" color="blue" size="sm">Pool</Badge>;
        case 'balanced':
            return <Badge leftSection={<IconSitemap size={12} />} variant="light" color="green" size="sm">Balanced</Badge>;
        case 'reality':
            return <Badge leftSection={<IconUsers size={12} />} variant="light" color="orange" size="sm">Reality</Badge>;
        default:
            return <Badge variant="light" color="gray" size="sm">{kind}</Badge>;
    }
}

export function DatasetsPage() {
    const [q, setQ] = useState<string | undefined>();
    const { data = [], isLoading } = useDatasets(q);
    const [builderOpen, setBuilderOpen] = useState(false);
    const [rowBuilder, setRowBuilder] = useState<{ mode: 'balanced' | 'reality' | 'counterfactuals'; id: number } | null>(null);
    const navigate = useNavigate();
    const delDs = useDeleteDataset();
    const [delJobId, setDelJobId] = useState<number | undefined>(undefined);
    const delStatus = useDeleteStatus(delJobId);

    // Build hierarchical data
    const hierarchicalData = useMemo(() => buildHierarchy(data), [data]);

    const columns: ColumnDef<DatasetWithDepth>[] = [
        { header: 'ID', accessorKey: 'id', cell: ({ row }) => <span style={{ color: '#868e96' }}>#{row.original.id}</span> },
        { 
            header: 'Name', 
            accessorKey: 'name', 
            cell: ({ row }) => (
                <Group gap={6} wrap="nowrap" style={{ paddingLeft: row.original._depth * 24 }}>
                    {row.original._depth > 0 && (
                        <IconCornerDownRight size={14} color="#adb5bd" style={{ flexShrink: 0 }} />
                    )}
                    <span style={{ fontWeight: 500 }}>{row.original.name}</span>
                </Group>
            ) 
        },
        { 
            header: 'Größe', 
            accessorKey: 'size', 
            cell: ({ row }) => (
                <Tooltip label={row.original.size.toLocaleString('de-DE')} withArrow>
                    <span>{formatCompactNumber(row.original.size)}</span>
                </Tooltip>
            )
        },
        { header: 'Art', accessorKey: 'kind', cell: ({ row }) => kindBadge(row.original.kind) },
        { 
            header: 'Runs', 
            accessorKey: 'runs_count', 
            cell: ({ row }) => {
                const runs = row.original.runs_count ?? 0;
                const models = row.original.models_count ?? 0;
                if (runs === 0) return <span style={{ color: '#adb5bd' }}>–</span>;
                return (
                    <Tooltip label={`${runs} Runs mit ${models} Modell${models !== 1 ? 'en' : ''}`} withArrow>
                        <Group gap={4} wrap="nowrap">
                            <IconPlayerPlay size={14} color="#228be6" />
                            <span>{runs}</span>
                            <span style={{ color: '#adb5bd' }}>/</span>
                            <span style={{ color: '#868e96' }}>{models}M</span>
                        </Group>
                    </Tooltip>
                );
            }
        },
        { 
            header: 'Erstellt', 
            accessorKey: 'created_at', 
            cell: ({ row }) => (
                <span style={{ color: '#495057' }}>{formatDate(row.original.created_at)}</span>
            )
        },
        { 
            header: 'Seed', 
            accessorKey: 'seed', 
            cell: ({ row }) => row.original.seed 
                ? <code style={{ fontSize: '0.85em', background: '#f1f3f5', padding: '2px 6px', borderRadius: 4 }}>{row.original.seed}</code>
                : <span style={{ color: '#adb5bd' }}>–</span>
        },
        { 
            header: '', 
            accessorKey: 'actions', 
            cell: ({ row }) => (
                <Group gap={4} wrap="nowrap">
                    <Tooltip label="Details anzeigen" withArrow>
                        <ActionIcon 
                            variant="light" 
                            onClick={() => navigate({ to: '/datasets/$datasetId', params: { datasetId: String(row.original.id) } })}
                        >
                            <IconExternalLink size={16} />
                        </ActionIcon>
                    </Tooltip>
                    <Menu withinPortal position="bottom-end">
                        <Menu.Target>
                            <ActionIcon variant="subtle" color="gray">
                                <IconDotsVertical size={18} />
                            </ActionIcon>
                        </Menu.Target>
                        <Menu.Dropdown>
                            <Menu.Label>Aktionen</Menu.Label>
                            <Menu.Item onClick={() => setRowBuilder({ mode: 'balanced', id: row.original.id })}>Balanced erstellen…</Menu.Item>
                            <Menu.Item onClick={() => setRowBuilder({ mode: 'reality', id: row.original.id })}>Subset erstellen…</Menu.Item>
                            <Menu.Divider />
                            <Menu.Item color="red" onClick={async () => {
                                if (!confirm(`Dataset "${row.original.name}" (#${row.original.id}) wirklich löschen?`)) return;
                                try {
                                    const r = await delDs.mutateAsync(row.original.id) as any;
                                    setDelJobId(Number(r.job_id));
                                } catch (e) { /* handled globally */ }
                            }}>Löschen…</Menu.Item>
                        </Menu.Dropdown>
                    </Menu>
                </Group>
            ) 
        },
    ];

    return (
        <>
        <Card>
        <Group justify="space-between" mb="md">
          <Title order={2}>Datasets</Title>
          <Group gap="sm">
            <TextInput
                placeholder="Suchen…"
                leftSection={<IconSearch size={16} />}
                onChange={(e) => setQ(e.target.value || undefined)}
                style={{ width: 220 }}
            />
            <Button leftSection={<IconPlus size={16} />} onClick={() => setBuilderOpen(true)}>Neuer Pool</Button>
          </Group>
        </Group>
        {isLoading ? 'Laden…' : <DataTable data={hierarchicalData} columns={columns} />}
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
        {delJobId && (
          <Card style={{ position: 'fixed', bottom: 20, right: 20, width: 320, zIndex: 1000 }} shadow="sm">
            <b>Dataset löschen…</b>
            <div>Status: {delStatus.data?.status || '…'}</div>
            {delStatus.data?.status === 'failed' && (<div style={{ color: '#d32f2f' }}>Fehler: {String(delStatus.data?.error || '')}</div>)}
            {delStatus.data?.status !== 'done' && delStatus.data?.status !== 'failed' && (
              <div style={{ fontSize: 12, color: '#666' }}>Bitte Tab offen lassen…</div>
            )}
            {(delStatus.data?.status === 'done' || delStatus.data?.status === 'failed') && (
              <Group justify="right" mt="sm">
                <Button size="xs" onClick={() => { setDelJobId(undefined); }}>Schließen</Button>
              </Group>
            )}
          </Card>
        )}
        </>
    );
}
